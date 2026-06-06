"""
Core video management views
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from videos.models import Video
from videos.views_logic.utils import process_video_sync


@login_required
def video_list(request):
    """List all uploaded videos."""
    videos = Video.objects.all().select_related('uploaded_by')
    return render(request, 'videos/video_list.html', {'videos': videos})


@login_required
def video_detail(request, video_id):
    """Show video detail page with player and quality selector."""
    video = get_object_or_404(Video, id=video_id)
    return render(request, 'videos/video_detail.html', {'video': video})


@login_required
@require_http_methods(["POST"])
def upload_video(request):
    """Handle video upload and start processing."""
    if request.method == 'POST' and request.FILES.get('video'):
        title = request.POST.get('title', 'Untitled Video')
        description = request.POST.get('description', '')
        video_file = request.FILES['video']

        # Create video object
        video = Video.objects.create(
            title=title,
            description=description,
            original_file=video_file,
            uploaded_by=request.user,
            file_size=video_file.size,
            mime_type=video_file.content_type,
        )

        # Start processing asynchronously
        try:
            process_video.delay(video.id)
        except Exception:
            # Fallback to sync processing if Celery not available
            process_video_sync(video.id)

        return JsonResponse({'status': 'success', 'video_id': video.id})

    return JsonResponse({'status': 'error', 'message': 'No video file provided'}, status=400)
