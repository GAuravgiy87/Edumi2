"""
Core video editing views
"""
import os
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from videos.models import Video
from video_editing.models import VideoEditSession
from video_editing.views_logic.utils import process_video_edits


@login_required
def edit_video(request, video_id):
    """Show the video editing interface."""
    video = get_object_or_404(Video, id=video_id)

    # Get or create edit session
    session, created = VideoEditSession.objects.get_or_create(
        original_video=video,
        created_by=request.user,
        status='draft'
    )

    return render(request, 'video_editing/edit_video.html', {
        'video': video,
        'session': session,
        'actions': session.actions.all()
    })


@login_required
@require_http_methods(["POST"])
def process_edits(request, session_id):
    """Apply all edit actions and generate the final edited video."""
    session = get_object_or_404(VideoEditSession, id=session_id, created_by=request.user)
    session.status = 'processing'
    session.save()

    try:
        # Process the edits using FFmpeg
        edited_path = process_video_edits(session)

        # Save the edited video
        with open(edited_path, 'rb') as f:
            content = f.read()
            session.edited_video.save(f'edited_{session.id}.mp4', ContentFile(content))

        session.status = 'completed'
        session.save()

        # Clean up temp file
        if os.path.exists(edited_path):
            os.remove(edited_path)

        return JsonResponse({'status': 'success', 'session_id': session.id})
    except Exception as e:
        session.status = 'failed'
        session.save()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
