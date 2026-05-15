import os
import subprocess
import threading
import logging
import time
import signal
from django.conf import settings
from django.utils import timezone
from .models import Camera, CameraRecording

logger = logging.getLogger('cameras')

class RecordingEngine:
    """FFmpeg-based recording engine for high-quality AV synchronization"""
    
    _instances = {}
    _lock = threading.Lock()

    def __init__(self, camera_id, teacher_id):
        self.camera_id = camera_id
        self.teacher_id = teacher_id
        self.process = None
        self.output_path = None
        self.recording_id = None
        self.start_time = None

    @classmethod
    def start_recording(cls, camera, teacher, quality='720p'):
        with cls._lock:
            key = f"{camera.id}_{teacher.id}"
            if key in cls._instances:
                return False, "Recording already in progress"

            instance = cls(camera.id, teacher.id)
            success, msg = instance._start(camera, teacher, quality)
            if success:
                cls._instances[key] = instance
            return success, msg

    def _start(self, camera, teacher, quality):
        # Define output path
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"rec_{camera.id}_{timestamp}.mp4"
        relative_path = os.path.join('recordings', timezone.now().strftime('%Y/%m/%d'), filename)
        self.output_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        # Map quality to resolution
        quality_map = {
            '360p': '640x360',
            '480p': '854x480',
            '720p': '1280x720',
            '1080p': '1920x1080'
        }
        res = quality_map.get(quality, '1280x720')

        # FFmpeg command for RTSP to MP4 with A/V sync
        stream_url = camera.get_stream_url()
        
        # Base command
        cmd = ['ffmpeg', '-y']
        
        # Add RTSP transport if it's an RTSP stream
        if stream_url.startswith('rtsp'):
            cmd.extend(['-rtsp_transport', 'tcp'])
            
        cmd.extend([
            '-i', stream_url,
            '-s', res,
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            self.output_path
        ])

        try:
            # Create the Recording record
            rec = CameraRecording.objects.create(
                camera=camera,
                teacher=teacher,
                title=f"Recording {timestamp}",
                recording_status='recording'
            )
            self.recording_id = rec.id
            self.start_time = timezone.now()

            # Start FFmpeg as a background process
            # We use DEVNULL for stdout/stderr to prevent pipe overflow hangs
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            # Small delay to see if process crashes immediately
            time.sleep(1)
            if self.process.poll() is not None:
                # Process died immediately
                rec.recording_status = 'failed'
                rec.save()
                return False, "FFmpeg failed to start. Check camera stream URL."

            logger.info(f"Started FFmpeg recording for camera {camera.id} at {self.output_path}")
            return True, "Recording started"
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False, str(e)

    @classmethod
    def stop_recording(cls, camera_id, teacher_id):
        with cls._lock:
            key = f"{camera_id}_{teacher_id}"
            if key not in cls._instances:
                return False, "No active recording found"

            instance = cls._instances[key]
            success = instance._stop()
            del cls._instances[key]
            return success, instance.recording_id

    @classmethod
    def is_recording(cls, camera_id, teacher_id):
        with cls._lock:
            key = f"{camera_id}_{teacher_id}"
            if key in cls._instances:
                instance = cls._instances[key]
                return True, instance.start_time
            return False, None

    def _stop(self):
        if self.process:
            try:
                logger.info(f"Stopping recording for camera {self.camera_id}")
                
                # Gracefully stop FFmpeg (send 'q' or SIGTERM)
                if os.name == 'nt':
                    # On Windows, we send CTRL_BREAK to the process group
                    self.process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self.process.terminate()
                
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"FFmpeg did not stop gracefully for camera {self.camera_id}. Killing...")
                    self.process.kill()
                
                # Update database
                rec = CameraRecording.objects.get(id=self.recording_id)
                
                # Check if file exists and has size
                if os.path.exists(self.output_path):
                    file_size = os.path.getsize(self.output_path)
                    if file_size > 0:
                        rec.recording_status = 'processing'
                        rec.duration = timezone.now() - self.start_time
                        
                        # Set the file field
                        relative_path = os.path.relpath(self.output_path, settings.MEDIA_ROOT)
                        rec.video_file.name = relative_path.replace('\\', '/')
                        rec.file_size = file_size
                        rec.save()
                        
                        # Trigger background processing
                        try:
                            from .tasks import process_recording_task
                            process_recording_task.delay(rec.id)
                            logger.info(f"Recording {self.recording_id} stopped and sent to processing")
                        except Exception as e:
                            logger.error(f"Failed to trigger Celery task: {e}")
                            # Fallback: process manually if Celery fails
                            rec.recording_status = 'completed'
                            rec.save()
                        
                        return True
                    else:
                        logger.error(f"Recording file for camera {self.camera_id} is empty")
                        rec.recording_status = 'failed'
                        rec.save()
                        return False
                else:
                    logger.error(f"Recording file for camera {self.camera_id} does not exist at {self.output_path}")
                    rec.recording_status = 'failed'
                    rec.save()
                    return False
                    
            except Exception as e:
                logger.error(f"Error stopping recording: {e}")
                return False
        return False

recording_engine = RecordingEngine
