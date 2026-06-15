"""
Download edited video view
"""
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse

from video_editing.models import VideoEditSession


@login_required
def download_edited_video(request, session_id):
    """Download the final edited video."""
    session = get_object_or_404(VideoEditSession, id=session_id, created_by=request.user)
    if session.edited_video:
        return FileResponse(
            session.edited_video.open('rb'),
            as_attachment=True,
            filename=f'edited_{session.original_video.title}.mp4'
        )
    return JsonResponse({'status': 'error', 'message': 'No edited video available'}, status=404)
