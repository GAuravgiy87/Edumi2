import os
import subprocess
import logging
from celery import shared_task
from django.conf import settings
from .models import CameraRecording

logger = logging.getLogger('cameras')

@shared_task
def process_recording_task(recording_id):
    """Background task to generate thumbnails and optimize video"""
    try:
        rec = CameraRecording.objects.get(id=recording_id)
        video_path = rec.video_file.path
        
        # 1. Generate Thumbnail
        thumbnail_filename = f"thumb_{rec.id}.jpg"
        thumbnail_dir = os.path.join(settings.MEDIA_ROOT, 'recordings', 'thumbnails')
        os.makedirs(thumbnail_dir, exist_ok=True)
        thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
        
        thumb_cmd = [
            'ffmpeg', '-y', '-i', video_path,
            '-ss', '00:00:02', '-vframes', '1',
            '-q:v', '2', thumbnail_path
        ]
        
        subprocess.run(thumb_cmd, capture_output=True)
        
        if os.path.exists(thumbnail_path):
            rec.thumbnail.name = os.path.join('recordings', 'thumbnails', thumbnail_filename).replace('\\', '/')

        # 2. Finalize
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
