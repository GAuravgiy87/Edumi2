
import os
import re
from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
from ..models import Camera, CameraRecording, RecordingChunk
from .utils import get_video_stream, is_admin
from mobile_cameras.models import MobileCamera, MobileCameraPermission


@login_required
def stream_video(request, recording_id):
    """View to serve video files in chunks (YouTube style) - Optimized for 4hr+ videos"""
    recording = get_object_or_404(CameraRecording, id=recording_id)

    # Check permissions
    if not (request.user.is_superuser or
            recording.teacher == request.user or
            (recording.is_published and hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'student')):
        return HttpResponse("Unauthorized", status=403)

    file_path = recording.video_file.path
    if not os.path.exists(file_path):
        return HttpResponse("Video file not found", status=404)

    size = os.path.getsize(file_path)
    range_header = request.META.get('HTTP_RANGE', None)

    content_type = 'video/mp4'
    if file_path.endswith('.mkv'):
        content_type = 'video/x-matroska'
    elif file_path.endswith('.webm'):
        content_type = 'video/webm'

    if range_header:
        # Standard Range request parsing
        match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else size - 1

            # Ensure boundaries
            start = max(0, min(start, size - 1))
            end = max(start, min(end, size - 1))

            content_length = end - start + 1

            response = StreamingHttpResponse(
                get_video_stream(file_path, start, end),
                status=206,
                content_type=content_type
            )
            response['Content-Range'] = f'bytes {start}-{end}/{size}'
            response['Accept-Ranges'] = 'bytes'
            response['Content-Length'] = str(content_length)
            return response

    # Default to full file streaming if no range or invalid range
    response = StreamingHttpResponse(get_video_stream(file_path, 0, size - 1), content_type=content_type)
    response['Accept-Ranges'] = 'bytes'
    response['Content-Length'] = str(size)
    return response


@login_required
def upload_video(request):
    """View for teachers to upload video lectures"""
    if not (request.user.is_superuser or (hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'teacher')):
        return redirect('dashboard')

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        video_file = request.FILES.get('video_file')
        camera_id = request.POST.get('camera')

        if not video_file:
            return render(request, 'cameras/upload_video.html', {'error': 'Please select a video file.'})

        camera = None
        if camera_id:
            camera = Camera.objects.filter(id=camera_id).first()

        recording = CameraRecording.objects.create(
            teacher=request.user,
            camera=camera,
            title=title,
            description=description,
            video_file=video_file,
            recording_status='completed',
            is_published=False  # Teacher must manually publish
        )

        return redirect('manage_recordings')

    cameras = Camera.objects.all() if request.user.is_superuser else Camera.objects.filter(camerapermission__teacher=request.user)
    return render(request, 'cameras/upload_video.html', {'cameras': cameras})


@login_required
def recordings_folder(request):
    """View to show recordings organized in a folder-like structure with date subfolders"""
    from django.utils.text import slugify

    if request.user.is_superuser:
        # Only show recordings that actually have a file
        recordings = CameraRecording.objects.exclude(video_file='').order_by('-created_at')
    else:
        recordings = CameraRecording.objects.filter(teacher=request.user).exclude(video_file='').order_by('-created_at')

    # Group by camera, then by date
    from collections import defaultdict
    folders = defaultdict(lambda: defaultdict(list))

    for rec in recordings:
        camera_name = rec.camera.name if rec.camera else "Uploaded Videos"
        date_str = rec.created_at.strftime('%Y-%m-%d')
        folders[camera_name][date_str].append(rec)

    # Convert to a regular dict with slugified IDs for the template
    processed_folders = []
    for cam_name, dates in folders.items():
        processed_folders.append({
            'name': cam_name,
            'id': slugify(cam_name),
            'dates': dict(dates),
            'count': sum(len(v) for v in dates.values())
        })

    context = {
        'folders': processed_folders,
        'total_count': recordings.count(),
    }
    return render(request, 'cameras/recordings_folder.html', context)


@login_required
def manage_recordings(request):
    """View for teachers to manage their recordings and uploads"""
    if not (request.user.is_superuser or (hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'teacher')):
        return redirect('dashboard')

    recordings = CameraRecording.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'cameras/manage_recordings.html', {'recordings': recordings})


@login_required
def toggle_recording_publish(request, recording_id):
    """Toggle the published status of a recording"""
    recording = get_object_or_404(CameraRecording, id=recording_id)

    if not (request.user.is_superuser or recording.teacher == request.user):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    recording.is_published = not recording.is_published
    recording.save()

    return JsonResponse({
        'status': 'success',
        'is_published': recording.is_published,
        'message': f'Recording {"published" if recording.is_published else "hidden"}'
    })


@login_required
def watch_recording(request, recording_id):
    """Watch a recorded lecture"""
    recording = get_object_or_404(CameraRecording, id=recording_id)

    # Check permissions: owner or published
    if not (recording.is_published or recording.teacher == request.user or request.user.is_superuser):
        return HttpResponse("Unauthorized", status=403)

    # Recommended videos (same teacher or same camera)
    recommended = CameraRecording.objects.filter(
        is_published=True
    ).exclude(id=recording_id).filter(
        Q(teacher=recording.teacher) | Q(camera=recording.camera)
    ).order_by('-created_at')[:5]

    context = {
        'recording': recording,
        'recommended': recommended
    }

    if recording.is_chunked:
        context['playlist_url'] = reverse('recording_playlist', args=[recording.id])

    return render(request, 'cameras/watch_recording.html', context)


@login_required
def stream_recording_chunk(request, recording_id, sequence):
    """Serve a specific video chunk from the database"""
    chunk = get_object_or_404(RecordingChunk, recording_id=recording_id, sequence=sequence)

    # Check permission for the recording
    recording = chunk.recording
    if not (recording.is_published or recording.teacher == request.user or request.user.is_superuser):
        return HttpResponse("Unauthorized", status=403)

    return HttpResponse(chunk.data, content_type='video/mp2t')


@login_required
def recording_playlist(request, recording_id):
    """Generate HLS playlist for a chunked recording"""
    recording = get_object_or_404(CameraRecording, id=recording_id)

    if not (recording.is_published or recording.teacher == request.user or request.user.is_superuser):
        return HttpResponse("Unauthorized", status=403)

    chunks = RecordingChunk.objects.filter(recording=recording).order_by('sequence')

    playlist = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        "#EXT-X-TARGETDURATION:10",
        "#EXT-X-MEDIA-SEQUENCE:0",
        "#EXT-X-PLAYLIST-TYPE:VOD"
    ]

    for chunk in chunks:
        playlist.append(f"#EXTINF:{chunk.duration},")
        chunk_url = reverse('stream_chunk', args=[recording.id, chunk.sequence])
        playlist.append(chunk_url)

    playlist.append("#EXT-X-ENDLIST")

    return HttpResponse("\n".join(playlist), content_type='application/vnd.apple.mpegurl')


@login_required
def teacher_profile(request, teacher_id):
    """Show all lectures and live status for a specific teacher"""
    teacher = get_object_or_404(User, id=teacher_id)

    live_cameras = Camera.objects.filter(live_teacher=teacher, is_live=True)
    recordings = CameraRecording.objects.filter(teacher=teacher, is_published=True).order_by('-created_at')

    return render(request, 'cameras/teacher_profile.html', {
        'target_teacher': teacher,
        'live_cameras': live_cameras,
        'recordings': recordings
    })

