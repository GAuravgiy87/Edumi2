import os
import subprocess
import logging
from celery import shared_task
from django.conf import settings
from .models import CameraRecording

logger = logging.getLogger('cameras')

@shared_task
def process_recording_task(recording_id):
    """Background task to remux MKV to MP4, generate thumbnails and optimize video"""
    try:
        rec = CameraRecording.objects.get(id=recording_id)
        current_path = rec.video_file.path
        
        # 1. Remux MKV to MP4 if needed (for VLC/Web compatibility)
        if current_path.endswith('.mkv'):
            mp4_path = current_path.replace('.mkv', '.mp4')
            logger.info(f"Background remuxing {current_path} to {mp4_path}...")
            
            remux_cmd = [
                'ffmpeg', '-y', '-i', current_path,
                '-c', 'copy', # Copy streams without re-encoding
                '-movflags', '+faststart', # Move MOOV atom for web playback
                mp4_path
            ]
            
            try:
                # No timeout here as it's a background task
                subprocess.run(remux_cmd, check=True, capture_output=True)
                
                # Update record with new path
                old_mkv_path = current_path
                relative_path = os.path.relpath(mp4_path, settings.MEDIA_ROOT)
                rec.video_file.name = relative_path.replace('\\', '/')
                rec.file_size = os.path.getsize(mp4_path)
                rec.save()
                
                # Now use the new path for thumbnail generation
                video_path = mp4_path
                
                # Delete old MKV to save space
                try: os.remove(old_mkv_path)
                except: pass
            except Exception as e:
                logger.error(f"Background remuxing failed for {recording_id}: {e}")
                video_path = current_path # Fallback to original
        else:
            video_path = current_path
        
        # 2. Generate Thumbnail
        thumbnail_filename = f"thumb_{rec.id}.jpg"
        thumbnail_dir = os.path.join(settings.MEDIA_ROOT, 'recordings', 'thumbnails')
        os.makedirs(thumbnail_dir, exist_ok=True)
        thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
        
        # Try to get frame at 1 second, or 0 if it fails
        thumb_cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-ss', '00:00:01', '-vframes', '1',
            '-q:v', '2', thumbnail_path
        ]
        
        subprocess.run(thumb_cmd, capture_output=True)
        
        if not os.path.exists(thumbnail_path):
            # Fallback to start of video
            thumb_cmd[4] = '00:00:00'
            subprocess.run(thumb_cmd, capture_output=True)
        
        if os.path.exists(thumbnail_path):
            rec.thumbnail.name = os.path.join('recordings', 'thumbnails', thumbnail_filename).replace('\\', '/')

        # 3. Finalize
        rec.recording_status = 'completed'
        rec.save()
        
        logger.info(f"Processed recording {recording_id} successfully")
        return True
    except Exception as e:
        logger.error(f"Error processing recording {recording_id}: {e}")
        try:
            rec = CameraRecording.objects.get(id=recording_id)
            rec.recording_status = 'failed'
            rec.save()
        except: pass
        return False

@shared_task
def camera_health_check_task():
    """Background task to check if cameras are online"""
    from .models import Camera
    import cv2
    
    cameras = Camera.objects.all()
    for camera in cameras:
        url = camera.get_stream_url()
        cap = cv2.VideoCapture(url)
        is_online = cap.isOpened()
        if is_online:
            ret, _ = cap.read()
            is_online = ret
        cap.release()
        
        if camera.is_active != is_online:
            camera.is_active = is_online
            camera.save()
            logger.info(f"Camera {camera.name} status changed to {'Online' if is_online else 'Offline'}")
