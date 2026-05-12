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
        # Uses 'copy' codec for video if possible to save CPU, or libx264 for resizing
        stream_url = camera.get_stream_url()
        
        cmd = [
            'ffmpeg', '-y',
            '-rtsp_transport', 'tcp',
            '-i', stream_url,
            '-s', res,
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            self.output_path
        ]

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
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
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

    def _stop(self):
        if self.process:
            try:
                # Gracefully stop FFmpeg (send 'q' or SIGTERM)
                if os.name == 'nt':
                    self.process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self.process.terminate()
                
                self.process.wait(timeout=5)
                
                # Update database
                rec = CameraRecording.objects.get(id=self.recording_id)
                rec.recording_status = 'processing'
                rec.duration = timezone.now() - self.start_time
                
                # Set the file field
                relative_path = os.path.relpath(self.output_path, settings.MEDIA_ROOT)
                rec.video_file.name = relative_path.replace('\\', '/')
                
                # Check file size
                if os.path.exists(self.output_path):
                    rec.file_size = os.path.getsize(self.output_path)
                
                rec.save()
                
                # Trigger background processing ( Celery task )
                from .tasks import process_recording_task
                process_recording_task.delay(rec.id)
                
                return True
            except Exception as e:
                logger.error(f"Error stopping recording: {e}")
                return False
        return False

recording_engine = RecordingEngine
