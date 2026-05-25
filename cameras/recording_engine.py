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
    _lock = threading.RLock()

    def __init__(self, camera_id, teacher_id, audio_path=None):
        self.camera_id = camera_id
        self.teacher_id = teacher_id
        self.process = None
        self.output_path = None
        self.audio_path = audio_path # External audio file from browser
        self.recording_id = None
        self.start_time = None
        self.finalized = False
        self.lock = threading.RLock() # Use RLock to prevent re-entrant deadlocks during monitor callback

    @classmethod
    def start_recording(cls, camera, teacher, quality='1080p', audio_source='pc'):
        with cls._lock:
            key = f"{camera.id}_{teacher.id}"
            
            # 1. Check if ANYONE is already recording this camera
            for k, existing in cls._instances.items():
                if k.startswith(f"{camera.id}_"):
                    if existing.process and existing.process.poll() is None:
                        return False, "This camera is already being recorded by another session"
                    else:
                        logger.warning(f"Found stale recording instance for {k}, cleaning up.")
                        del cls._instances[k]
                        break

            # 2. Check DB for orphaned 'recording' status on this camera
            from .models import CameraRecording
            orphaned = CameraRecording.objects.filter(camera=camera, recording_status='recording')
            if orphaned.exists():
                logger.warning(f"Found orphaned DB records for camera {camera.id}, marking as failed before starting new.")
                orphaned.update(recording_status='failed')

            final_audio_path = None
            
            if audio_source == 'camera':
                # Use built-in camera audio, no external path needed
                logger.info(f"Using IP Camera built-in audio for recording")
            elif audio_source == 'remote':
                # Force mobile mic
                mobile_audio_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'audio_{camera.id}_{teacher.id}_mobile.webm')
                if os.path.exists(mobile_audio_path):
                    final_audio_path = mobile_audio_path
                    logger.info(f"Using REMOTE mobile mic for recording: {mobile_audio_path}")
            else:
                # Default to PC mic or auto-detect
                mobile_audio_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'audio_{camera.id}_{teacher.id}_mobile.webm')
                pc_audio_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'audio_{camera.id}_{teacher.id}.webm')
                
                # Auto-detect logic
                if os.path.exists(mobile_audio_path) and (time.time() - os.path.getmtime(mobile_audio_path)) < 60:
                    final_audio_path = mobile_audio_path
                elif os.path.exists(pc_audio_path) and (time.time() - os.path.getmtime(pc_audio_path)) < 60:
                    final_audio_path = pc_audio_path

            instance = cls(camera.id, teacher.id, audio_path=final_audio_path)
            success, msg = instance._start(camera, teacher, quality)
            if success:
                cls._instances[key] = instance
            return success, msg

    def _start(self, camera, teacher, quality):
        # Define output path with structured hierarchy: recordings/Camera_Name/YYYY/MM/DD/
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        safe_camera_name = "".join([c if c.isalnum() else "_" for c in camera.name])
        date_path = timezone.now().strftime('%Y/%m/%d')
        filename = f"rec_{camera.id}_{timestamp}.mkv" # Record to MKV for crash resilience
        
        relative_path = os.path.join('recordings', safe_camera_name, date_path, filename)
        self.output_path = os.path.join(settings.MEDIA_ROOT, relative_path)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        # Map quality to resolution
        quality_map = {
            '360p': '640x360',
            '480p': '854x480',
            '720p': '1280x720',
            '1080p': '1920x1080',
            '4K': '3840x2160'
        }
        res = quality_map.get(quality, '1280x720')

        # FFmpeg command for RTSP to MP4 with A/V sync
        stream_url = camera.get_stream_url()
        
        # Determine encoder: Use h264_amf for AMD GPU if available, else libx264
        # We'll try to detect if h264_amf is supported by running a quick check
        encoder = 'h264_amf'
        try:
            # Simple check to see if amf is available
            test_cmd = ['ffmpeg', '-hide_banner', '-encoders']
            res_encoders = subprocess.check_output(test_cmd).decode()
            if 'h264_amf' not in res_encoders:
                encoder = 'libx264'
                logger.warning("h264_amf encoder not found, falling back to libx264")
        except:
            encoder = 'libx264'
            logger.warning("Failed to check for h264_amf, using libx264")

        # Base command with global sync settings
        cmd = [
            'ffmpeg', '-y',
            '-hide_banner',
            '-loglevel', 'warning', 
            '-probesize', '15M', '-analyzeduration', '15M', # Increased for better stream detection
            '-hwaccel', 'd3d11va' if encoder == 'h264_amf' else 'auto', 
            '-thread_queue_size', '8192', # Increased buffer for better sync
            '-use_wallclock_as_timestamps', '1',
            '-fflags', '+genpts+discardcorrupt+igndts', # Advanced sync flags
        ]
        
        # Add RTSP transport if it's an RTSP stream
        if stream_url.startswith('rtsp'):
            cmd.extend(['-rtsp_transport', 'tcp', '-fflags', '+nobuffer'])
            
        cmd.extend(['-i', stream_url])

        # Add external audio input if provided
        if self.audio_path and os.path.exists(self.audio_path):
            # Tell ffmpeg to read the external file carefully
            # We add a small offset to the audio input to match RTSP latency (approx 1.2s)
            cmd.extend([
                '-itsoffset', '1.2', 
                '-probesize', '10M', '-analyzeduration', '10M', 
                '-i', self.audio_path
            ])

        cmd.extend([
            '-s', res,
            '-c:v', encoder,
        ])
        
        if encoder == 'h264_amf':
            cmd.extend([
                '-quality', 'quality', 
                '-rc', 'cbr', 
                '-b:v', '6M' if quality == '4K' else '4M',
                '-profile', 'main',
                '-level', '4.1' if quality != '4K' else '5.1',
            ])
        else:
            cmd.extend(['-preset', 'faster', '-crf', '20', '-profile:v', 'main'])
            
        cmd.extend(['-pix_fmt', 'yuv420p'])

        # Audio Configuration: Advanced Filtering to remove "bharrrr" static and noise
        # 1. aresample: Sync audio with video using async and hard compensation
        # 2. highpass/lowpass: Filter extreme frequencies
        # 3. afftdn: FFT-based noise reduction
        # 4. speechnorm: Enhance human voice
        # 5. agate: Noise gate
        # 6. adelay: Fine-tune sync for external mics (delaying audio to match RTSP lag)
        # 7. volume: Apply 20x gain for low-sensitivity IP camera mics
        sync_delay = '1200' if self.audio_path else '0'
        audio_filters = (
            f'aresample=async=1000:min_hard_comp=0.05:first_pts=0,'
            f'adelay={sync_delay}|{sync_delay},' # Delay audio to match RTSP latency
            'highpass=f=150,lowpass=f=14000,' # Optimized for human speech
            'volume=20.0,' # 20x gain boost
            'afftdn=nf=-35,' # Noise reduction
            'speechnorm=e=4:p=0.5,'
            'agate=threshold=0.01:range=0:attack=50:release=200,'
            'dynaudnorm=p=0.9:m=60.0:s=5,' # Maximum normalization
            'aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo'
        )

        if self.audio_path:
            cmd.extend([
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-c:a', 'aac', '-b:a', '192k', '-ar', '44100',
                '-af', audio_filters,
            ])
        else:
            # Map all audio streams from the camera if they exist
            cmd.extend([
                '-map', '0:v:0',
                '-map', '0:a?',
                '-c:a', 'aac', '-b:a', '192k', '-ar', '44100',
                '-af', audio_filters,
            ])

        cmd.extend([
            '-vsync', 'cfr', # Force Constant Frame Rate for better A/V alignment
            '-f', 'matroska', # Explicitly use MKV format for recording
            self.output_path
        ])

        try:
            # Create the Recording record
            rec = CameraRecording.objects.create(
                camera=camera,
                teacher=teacher,
                title=f"Recording - {camera.name} - {timestamp}",
                recording_status='recording',
                video_file=relative_path.replace('\\', '/') # Set path immediately for recovery
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
            
            # Start monitoring thread for auto-save on crash
            threading.Thread(target=self._monitor_process, daemon=True).start()
            
            return True, "Recording started"
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False, str(e)

    def _monitor_process(self):
        """Monitor the FFmpeg process and auto-save if it stops unexpectedly"""
        # Wait for the process to exit
        self.process.wait()
        
        # If the process exited and we haven't finalized yet, it's a crash or disconnect
        # IMPORTANT: Only cleanup if it's NOT a deliberate manual stop
        
        # We use a slight delay to ensure file handles are released before finalization
        time.sleep(1)
        
        should_cleanup = False
        with self.lock:
            if not self.finalized:
                logger.warning(f"FFmpeg process for camera {self.camera_id} stopped unexpectedly. Auto-saving...")
                self._stop(auto_save=True)
                should_cleanup = True
            else:
                # Deliberate stop handled it, but we still need to ensure cleanup
                should_cleanup = True
        
        if should_cleanup:
            # Remove from active instances OUTSIDE the instance lock to prevent AB-BA deadlock
            key = f"{self.camera_id}_{self.teacher_id}"
            with RecordingEngine._lock:
                if RecordingEngine._instances.get(key) == self:
                    del RecordingEngine._instances[key]

    @classmethod
    def stop_recording(cls, camera_id, teacher_id):
        with cls._lock:
            # 1. First, always check DB for an active recording record on this camera
            from .models import CameraRecording
            active_rec = CameraRecording.objects.filter(
                camera_id=camera_id, 
                recording_status='recording'
            ).last()

            # 2. Check memory for an instance
            key = f"{camera_id}_{teacher_id}"
            instance = cls._instances.get(key)
            
            # 3. If no exact match, look for any instance for this camera
            if not instance:
                for k, v in cls._instances.items():
                    if k.startswith(f"{camera_id}_"):
                        instance = v
                        key = k
                        break
            
        # If we have an instance, stop it OUTSIDE the class lock to avoid deadlocks with monitor thread
        if instance:
            try:
                logger.info(f"Stop requested for memory instance {key}")
                instance._stop(auto_save=False)
                
                # Re-acquire class lock briefly for cleanup
                with cls._lock:
                    if key in cls._instances:
                        del cls._instances[key]
                return True, instance.recording_id
            except Exception as e:
                logger.error(f"Error stopping memory instance: {e}")
                with cls._lock:
                    if key in cls._instances:
                        del cls._instances[key]
                # Don't return yet, try DB fallback below
        
        # 4. If no instance in memory but DB record exists, finalize it
        with cls._lock:
            if active_rec:
                logger.warning(f"Stop requested: Found DB record {active_rec.id} for camera {camera_id} without memory instance. Finalizing.")
                active_rec.recording_status = 'processing'
                active_rec.save()
                try:
                    from .tasks import process_recording_task
                    process_recording_task.delay(active_rec.id)
                except: pass
                return True, active_rec.id
            
            logger.error(f"Stop requested but NO active recording found in memory or DB for camera {camera_id}")
            return False, "No active recording found"

    @classmethod
    def is_recording(cls, camera_id, teacher_id):
        with cls._lock:
            # 1. Check memory for ANY instance on this camera
            for k, instance in cls._instances.items():
                if k.startswith(f"{camera_id}_"):
                    if instance.process and instance.process.poll() is None:
                        return True, instance.start_time
                    else:
                        # Clean up stale instance
                        del cls._instances[k]
                        break
            
            # 2. Fallback to DB check for this camera
            from .models import CameraRecording
            active_rec = CameraRecording.objects.filter(
                camera_id=camera_id, 
                recording_status='recording'
            ).last()
            if active_rec:
                return True, active_rec.created_at
                
            return False, None

    def _stop(self, auto_save=False):
        with self.lock:
            if self.finalized:
                return True
            
            if self.process:
                try:
                    logger.info(f"Finalizing recording for camera {self.camera_id} (Auto-save: {auto_save})")
                    
                    # If manual stop, terminate the process gracefully
                    if not auto_save and self.process.poll() is None:
                        logger.info(f"Sending termination signal to FFmpeg (PID: {self.process.pid})")
                        try:
                            if os.name == 'nt':
                                import signal
                                os.kill(self.process.pid, signal.CTRL_BREAK_EVENT)
                            else:
                                self.process.terminate()
                            
                            # Wait for process to exit and flush headers (blocking for up to 5s)
                            try:
                                self.process.wait(timeout=5)
                                logger.info("FFmpeg process terminated gracefully and flushed headers.")
                            except subprocess.TimeoutExpired:
                                logger.warning("FFmpeg did not exit in time, forcing kill...")
                                self.process.kill()
                        except Exception as e:
                            logger.error(f"Error terminating FFmpeg: {e}")
                            try: self.process.kill()
                            except: pass
                    
                    # Update database logic stays the same but without waiting for process
                    try:
                        rec = CameraRecording.objects.get(id=self.recording_id)
                    except CameraRecording.DoesNotExist:
                        logger.error(f"Recording record {self.recording_id} not found during stop")
                        self.finalized = True
                        return False
                    
                    if auto_save:
                        rec.title = f"[AUTO-SAVED] {rec.title}"
                    
                    # Check if file exists and has size
                    if os.path.exists(self.output_path):
                        file_size = os.path.getsize(self.output_path)
                        if file_size > 0:
                            # Mark as processing and return quickly
                            # Remuxing and thumbnails will happen in the background task
                            rec.recording_status = 'processing'
                            rec.duration = timezone.now() - self.start_time
                            
                            # Set the file field (currently .mkv)
                            relative_path = os.path.relpath(self.output_path, settings.MEDIA_ROOT)
                            rec.video_file.name = relative_path.replace('\\', '/')
                            rec.file_size = file_size
                            rec.save()
                            
                            # Trigger background processing (includes MKV -> MP4 remuxing)
                            try:
                                from .tasks import process_recording_task
                                process_recording_task.delay(rec.id)
                                logger.info(f"Recording {self.recording_id} stop requested, sent to background processing")
                            except Exception as e:
                                logger.error(f"Failed to trigger Celery task: {e}")
                                # Fallback: mark as completed if Celery fails
                                rec.recording_status = 'completed'
                                rec.save()
                            
                            self.finalized = True
                            return True
                        else:
                            logger.error(f"Recording file for camera {self.camera_id} is empty")
                            rec.recording_status = 'failed'
                            rec.save()
                            self.finalized = True
                            return False
                    else:
                        logger.error(f"Recording file for camera {self.camera_id} does not exist at {self.output_path}")
                        rec.recording_status = 'failed'
                        rec.save()
                        self.finalized = True
                        return False
                        
                except Exception as e:
                    logger.error(f"Error stopping recording: {e}")
                    self.finalized = True
                    return False
            return False

recording_engine = RecordingEngine

def cleanup_orphaned_recordings():
    """Find recordings stuck in 'recording' state and mark as failed or recover if file exists"""
    from .models import CameraRecording
    orphaned = CameraRecording.objects.filter(recording_status='recording')
    for rec in orphaned:
        # If it's more than 5 minutes old and not in our active instances, it's orphaned
        rec_time = rec.created_at
        if (timezone.now() - rec_time).total_seconds() > 300:
            logger.warning(f"Found orphaned recording {rec.id}. Attempting recovery...")
            # Check if file exists in media
            if rec.video_file and os.path.exists(rec.video_file.path):
                rec.recording_status = 'completed'
                rec.title = f"[RECOVERED] {rec.title}"
            else:
                # Try to find the file manually if field is empty
                # Look for .mkv or .mp4 files that might match
                rec.recording_status = 'failed'
            rec.save()
