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
            try:
                # 1. Wait for file to be released (if FFmpeg is still closing it)
                # On Windows, we check if we can open the file for writing
                import time
                max_retries = 10
                for i in range(max_retries):
                    try:
                        with open(current_path, 'rb+') as f:
                            break
                    except IOError:
                        logger.info(f"File {current_path} is locked, waiting... ({i+1}/{max_retries})")
                        time.sleep(2)
                
                # 2. Remux MKV to MP4 for browser compatibility
                # We use -movflags +faststart to make it playable before full download
                # We also ensure AAC audio and H264 video for maximum browser support
                output_path = current_path.replace('.mkv', '.mp4')
                cmd = [
                    'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                    '-i', current_path,
                    '-c:v', 'copy',
                    '-c:a', 'aac', '-b:a', '128k', # Ensure audio is AAC for browser playback
                    '-movflags', '+faststart',
                    output_path
                ]
                
                logger.info(f"Remuxing {current_path} to {output_path}...")
                subprocess.run(cmd, check=True)
                
                # If successful, update path and delete original MKV
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    # Update record with new path
                    relative_path = os.path.relpath(output_path, settings.MEDIA_ROOT)
                    rec.video_file.name = relative_path.replace('\\', '/')
                    rec.file_size = os.path.getsize(output_path)
                    rec.save()
                    
                    # Remove original MKV
                    try: os.remove(current_path)
                    except: pass
                    
                    video_path = output_path
                    logger.info(f"Remuxing successful: {video_path}")
                else:
                    logger.error("Remuxing failed: Output file is empty or missing")
                    video_path = current_path
            except Exception as e:
                logger.error(f"Background remuxing failed for {recording_id}: {e}")
                video_path = current_path # Fallback to original MKV (might not play in browser)
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
