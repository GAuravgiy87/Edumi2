from celery import shared_task
from django.shortcuts import get_object_or_404
from .models import VideoProject
from . import ffmpeg_utils
from .views import _apply_new_working_file
from .timeline_compiler import compile_timeline_to_ffmpeg
import logging

logger = logging.getLogger(__name__)

@shared_task
def export_video_task(project_id, timeline_json):
    """
    Background celery task that processes a JSON timeline export using FFmpeg.
    """
    try:
        project = VideoProject.objects.get(pk=project_id)
        project.status = "processing"
        project.save(update_fields=['status'])
        
        logger.info(f"Starting Celery video export for Project {project_id}")
        
        tmp_output_path = ffmpeg_utils._tmp_path(".mp4")
        compile_timeline_to_ffmpeg(project, timeline_json, tmp_output_path)
        
        # Apply the compiled file as the new working file
        _apply_new_working_file(project, tmp_output_path, "timeline_export", "Exported JSON Timeline")
        
        project.status = "ready"
        project.save(update_fields=['status'])
        logger.info(f"Successfully finished Celery video export for Project {project_id}")
        
    except VideoProject.DoesNotExist:
        logger.error(f"Celery task failed: VideoProject {project_id} not found.")
    except Exception as e:
        logger.error(f"Celery task failed for Project {project_id}: {str(e)}")
        # Try to save error to project
        try:
            project = VideoProject.objects.get(pk=project_id)
            project.status = "error"
            project.error_message = str(e)
            project.save(update_fields=['status', 'error_message'])
        except Exception:
            pass
