import os
import subprocess
import tempfile
import logging
import shutil
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from .models import LiveClass, LiveClassRecording, ProcessedVideo

logger = logging.getLogger('cameras.tasks')

@shared_task
def process_live_class_recording(live_class_id):
    """
    Main task to process a live class recording:
    1. Merge chunks
    2. Transcode to multi-bitrate HLS
    3. Generate thumbnail
    4. Cleanup
    """
    try:
        live_class = LiveClass.objects.get(id=live_class_id)
        processed, created = ProcessedVideo.objects.get_or_create(
            live_class=live_class,
            defaults={
                'title': live_class.title,
                'teacher': live_class.teacher,
                'processing_status': 'processing'
            }
        )
        
        if not created:
            processed.processing_status = 'processing'
            processed.save()
            
        # 1. Prepare Workspace
        work_dir = os.path.join(tempfile.gettempdir(), f'processing_{live_class_id}')
        os.makedirs(work_dir, exist_ok=True)
        
        # 2. Concatenate Chunks
        chunks = LiveClassRecording.objects.filter(live_class=live_class).order_by('chunk_index')
        if not chunks.exists():
            logger.error(f"No chunks found for live class {live_class_id}")
            processed.processing_status = 'failed'
            processed.save()
            return
            
        concat_file = os.path.join(work_dir, 'chunks.txt')
        with open(concat_file, 'w') as f:
            for chunk in chunks:
                # FFmpeg concat demuxer needs absolute paths and escaped single quotes
                abs_path = os.path.abspath(chunk.file_path).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
        
        merged_file = os.path.join(work_dir, 'source.mp4')
        concat_cmd = [
            'ffmpeg', '-y', '-threads', '2', '-f', 'concat', '-safe', '0',
            '-i', concat_file, '-c', 'copy', merged_file
        ]
        subprocess.run(concat_cmd, check=True, capture_output=True)
        
        # 3. Multi-bitrate HLS Transcoding
        # Resolutions: 1080p, 720p, 480p, 360p, 240p, 144p
        output_dir = os.path.join(settings.MEDIA_ROOT, 'processed_recordings', str(live_class_id))
        os.makedirs(output_dir, exist_ok=True)
        
        master_playlist = os.path.join(output_dir, 'master.m3u8')
        
        # Complex FFmpeg command for adaptive HLS
        # We define map/filter for each resolution
        hls_cmd = [
            'ffmpeg', '-y', '-threads', '4', '-i', merged_file,
            # 1080p
            '-filter_complex', 
            '[0:v]split=6[v1080][v720][v480][v360][v240][v144];'
            '[v1080]scale=w=1920:h=1080[v1080out];'
            '[v720]scale=w=1280:h=720[v720out];'
            '[v480]scale=w=854:h=480[v480out];'
            '[v360]scale=w=640:h=360[v360out];'
            '[v240]scale=w=426:h=240[v240out];'
            '[v144]scale=w=256:h=144[v144out]',
            
            # Mapping
            '-map', '[v1080out]', '-c:v:0', 'libx264', '-b:v:0', '5000k', '-maxrate:v:0', '5350k', '-bufsize:v:0', '7500k',
            '-map', '[v720out]',  '-c:v:1', 'libx264', '-b:v:1', '2800k', '-maxrate:v:1', '2996k', '-bufsize:v:1', '4200k',
            '-map', '[v480out]',  '-c:v:2', 'libx264', '-b:v:2', '1400k', '-maxrate:v:2', '1498k', '-bufsize:v:2', '2100k',
            '-map', '[v360out]',  '-c:v:3', 'libx264', '-b:v:3', '800k',  '-maxrate:v:3', '856k',  '-bufsize:v:3', '1200k',
            '-map', '[v240out]',  '-c:v:4', 'libx264', '-b:v:4', '400k',  '-maxrate:v:4', '428k',  '-bufsize:v:4', '600k',
            '-map', '[v144out]',  '-c:v:5', 'libx264', '-b:v:5', '200k',  '-maxrate:v:5', '214k',  '-bufsize:v:5', '300k',
            
            # Audio (common)
            '-map', '0:a?', '-c:a', 'aac', '-b:a', '128k', '-ac', '2',
            
            # HLS Settings
            '-f', 'hls',
            '-hls_time', '6',
            '-hls_playlist_type', 'vod',
            '-hls_flags', 'independent_segments',
            '-hls_segment_type', 'mpegts',
            '-hls_segment_filename', os.path.join(output_dir, '%v/seg_%03d.ts'),
            '-master_pl_name', 'master.m3u8',
            '-var_stream_map', 'v:0,a:0 v:1,a:1 v:2,a:2 v:3,a:3 v:4,a:4 v:5,a:5',
            os.path.join(output_dir, '%v/index.m3u8')
        ]
        
        logger.info(f"Starting HLS transcoding for {live_class_id}")
        subprocess.run(hls_cmd, check=True, capture_output=True)
        
        # 4. Generate Thumbnail
        thumb_dir = os.path.join(settings.MEDIA_ROOT, 'thumbnails')
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_name = f'thumb_{live_class_id}.jpg'
        thumb_path = os.path.join(thumb_dir, thumb_name)
        
        thumb_cmd = [
            'ffmpeg', '-y', '-threads', '1', '-ss', '00:00:05', '-i', merged_file,
            '-vframes', '1', '-q:v', '2', thumb_path
        ]
        subprocess.run(thumb_cmd, check=False)
        
        # 5. Get Metadata
        duration_cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', merged_file
        ]
        duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
        duration = float(duration_result.stdout.strip()) if duration_result.stdout.strip() else 0.0
        
        # 6. Update Model
        processed.hls_manifest_path = f'processed_recordings/{live_class_id}/master.m3u8'
        processed.thumbnail = f'thumbnails/{thumb_name}'
        processed.duration_seconds = duration
        processed.processing_status = 'completed'
        processed.processed_at = timezone.now()
        
        # Calculate total size
        total_size = 0
        for root, dirs, files in os.walk(output_dir):
            for f in files:
                total_size += os.path.getsize(os.path.join(root, f))
        processed.total_size_bytes = total_size
        processed.save()
        
        # 7. Cleanup
        shutil.rmtree(work_dir, ignore_errors=True)
        # Optionally delete raw chunks to save space
        # LiveClassRecording.objects.filter(live_class=live_class).delete()
        
        logger.info(f"Successfully processed live class {live_class_id}")
        
    except Exception as e:
        logger.exception(f"Error processing recording for live class {live_class_id}: {e}")
        try:
            processed = ProcessedVideo.objects.get(live_class_id=live_class_id)
            processed.processing_status = 'failed'
            processed.save()
        except:
            pass
