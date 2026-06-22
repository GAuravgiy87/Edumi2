
import requests
import logging
from django.shortcuts import render, redirect, get_object_or_404, reverse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from ..models import Camera, CameraRecording, CameraPermission
from .utils import is_admin, broadcast_live_status
from ..recording_engine import recording_engine

logger = logging.getLogger(__name__)

User = get_user_model()


@login_required
def mobile_mic(request, camera_id):
    """Dedicated page for using a mobile phone as a wireless microphone"""
    camera = get_object_or_404(Camera, id=camera_id)
    return render(request, 'cameras/mobile_mic.html', {
        'camera': camera,
        'user': request.user
    })


@login_required
def teacher_camera_dashboard(request):
    """Dashboard for teachers to see assigned cameras (RTSP and Mobile)"""
    from mobile_cameras.models import MobileCamera, MobileCameraPermission
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'teacher':
        return redirect('dashboard')

    # Get RTSP cameras
    camera_ids = CameraPermission.objects.filter(teacher=request.user).values_list('camera_id', flat=True)
    rtsp_cameras = list(Camera.objects.filter(id__in=camera_ids))
    for cam in rtsp_cameras:
        cam.is_mobile = False

    # Get Mobile cameras
    mobile_camera_ids = MobileCameraPermission.objects.filter(teacher=request.user).values_list('mobile_camera_id', flat=True)
    mobile_cameras = list(MobileCamera.objects.filter(id__in=mobile_camera_ids))
    for cam in mobile_cameras:
        cam.is_mobile = True

    # Combine lists
    all_cameras = rtsp_cameras + mobile_cameras

    # Get recent recordings by this teacher
    recent_recordings = CameraRecording.objects.filter(teacher=request.user).order_by('-created_at')[:5]

    return render(request, 'cameras/teacher_dashboard.html', {
        'cameras': all_cameras,
        'recent_recordings': recent_recordings
    })


@login_required
def teacher_control_room(request, camera_id):
    """Teacher control room for live streaming and recording"""
    camera = get_object_or_404(Camera, id=camera_id)

    # Check permission
    if not camera.has_permission(request.user):
        return redirect('dashboard')

    # We NO LONGER mark camera as live here.
    # It will be marked live only when the teacher explicitly clicks "Start Live Stream"

    # Get linked meeting if any (camera can be linked to a meeting for student tracking)
    linked_meeting = None
    student_count = 0
    active_participants = []
    if camera.livekit_room:
        try:
            from meetings.models import Meeting, MeetingParticipant
            linked_meeting = Meeting.objects.filter(meeting_code=camera.livekit_room).first()
            if linked_meeting:
                student_count = MeetingParticipant.objects.filter(meeting=linked_meeting, is_active=True).count()
                active_participants = list(linked_meeting.participants.filter(is_active=True).values_list('user__username', flat=True)[:10])
        except Exception as e:
            logger.warning(f"Error getting linked meeting participants: {e}")

    # Check if recording is in progress
    is_recording, recording_start_time = recording_engine.is_recording(camera.id, request.user.id)

    # Build the direct camera service URL for the browser.
    # The <img> tag must point here directly — Django's ASGI server (Daphne)
    # buffers StreamingHttpResponse so MJPEG never reaches the browser.
    from urllib.parse import urlparse
    from django.conf import settings as djsettings
    internal_url = getattr(djsettings, 'CAMERA_SERVICE_URL', 'http://localhost:8003')
    parsed = urlparse(internal_url)
    service_port = parsed.port or 8003
    request_host = request.get_host().split(':')[0]
    camera_feed_base = f'http://{request_host}:{service_port}/cameras/{camera.id}/feed/'

    context = {
        'camera': camera,
        'qualities': ['360p', '480p', '720p', '1080p', '4K'],
        'default_quality': '1080p',
        'linked_meeting': linked_meeting,
        'student_count': student_count,
        'active_participants': active_participants,
        'is_live': camera.is_live,
        'is_recording': is_recording,
        'recording_start_time': recording_start_time.isoformat() if recording_start_time else None,
        'camera_feed_base': camera_feed_base,
    }
    return render(request, 'cameras/teacher_control_room.html', context)


@login_required
def update_zoom(request, camera_id):
    """Proxy view to update camera zoom in the microservice"""
    camera = get_object_or_404(Camera, id=camera_id)
    if not camera.has_permission(request.user):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)

    zoom_level = request.GET.get('level', 1.0)
    x = request.GET.get('x', '')
    y = request.GET.get('y', '')

    try:
        # Forward request to camera microservice
        url = f'http://localhost:8003/cameras/{camera_id}/zoom/?level={zoom_level}'
        if x: url += f'&x={x}'
        if y: url += f'&y={y}'

        response = requests.get(url, timeout=5)
        return JsonResponse(response.json())
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def start_streaming(request, camera_id):
    """Teacher starts the live stream explicitly"""
    camera = get_object_or_404(Camera, id=camera_id)
    if not camera.has_permission(request.user):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})

    camera.is_live = True
    camera.live_teacher = request.user
    camera.save()

    # Broadcast status change
    broadcast_live_status(camera, 'started')

    return JsonResponse({'status': 'success', 'message': 'Live stream started'})


@login_required
def stop_streaming(request, camera_id):
    """Teacher stops the live stream"""
    camera = get_object_or_404(Camera, id=camera_id)
    if camera.live_teacher == request.user:
        camera.is_live = False
        camera.live_teacher = None
        camera.save()

        # Broadcast status change
        broadcast_live_status(camera, 'stopped')

        return JsonResponse({'status': 'success', 'message': 'Live stream stopped'})
    return JsonResponse({'status': 'error', 'message': 'Not the live teacher'})


@login_required
def live_participants(request, camera_id):
    """Get live participants for a camera's linked meeting"""
    camera = get_object_or_404(Camera, id=camera_id)

    # Check permission
    if not camera.has_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    if camera.livekit_room:
        try:
            from meetings.models import Meeting, MeetingParticipant
            meeting = Meeting.objects.filter(meeting_code=camera.livekit_room).first()
            if meeting:
                participants = meeting.participants.filter(is_active=True).select_related('user')
                participant_list = [
                    {'username': p.user.username, 'user_id': p.user.id}
                    for p in participants
                ]
                return JsonResponse({
                    'count': len(participant_list),
                    'participants': participant_list
                })
        except Exception as e:
            pass

    return JsonResponse({'count': 0, 'participants': []})


@login_required
def student_lecture_list(request):
    """List all available live sessions and recorded lectures for students"""
    from meetings.models import Meeting, ClassroomMembership

    query = request.GET.get('q', '')
    teacher_id = request.GET.get('teacher', '')

    # Get classrooms where user is an approved member
    my_classroom_ids = ClassroomMembership.objects.filter(
        student=request.user,
        status='approved'
    ).values_list('classroom_id', flat=True)

    # 1. Filter Live Cameras
    # We need to hide cameras that are linked to classrooms the student isn't in
    live_sessions = Camera.objects.filter(is_live=True).select_related('live_teacher')

    # Identify rooms that are linked to classrooms
    classroom_rooms = Meeting.objects.filter(
        classroom__isnull=False,
        status='live'
    ).values('meeting_code', 'classroom_id')

    room_to_classroom = {r['meeting_code']: r['classroom_id'] for r in classroom_rooms}

    filtered_live = []
    for cam in live_sessions:
        if cam.livekit_room in room_to_classroom:
            # This camera is in a classroom session
            if room_to_classroom[cam.livekit_room] in my_classroom_ids:
                filtered_live.append(cam)
        else:
            # Standalone camera or not linked to an active classroom meeting
            filtered_live.append(cam)

    # 2. Filter Recordings
    # recordings = CameraRecording.objects.filter(is_published=True).select_related('teacher', 'camera')
    # For recordings, if the camera used is traditionally for a classroom, should we hide it?
    # Usually recordings are published by teachers explicitly, but let's stick to the "meetings" logic.
    # If a recording's camera has a livekit_room that belongs to a classroom, maybe check?
    # For now, let's keep recordings as they are unless they have a direct classroom link (which they don't yet).
    recordings = CameraRecording.objects.filter(is_published=True).select_related('teacher', 'camera')

    if query:
        recordings = recordings.filter(
            Q(title__icontains=query) |
            Q(teacher__username__icontains=query) |
            Q(camera__name__icontains=query)
        )
        # Re-filter the filtered_live list for query
        filtered_live = [
            cam for cam in filtered_live
            if query.lower() in cam.name.lower() or
               (cam.live_teacher and query.lower() in cam.live_teacher.username.lower())
        ]

    if teacher_id:
        recordings = recordings.filter(teacher_id=teacher_id)
        filtered_live = [cam for cam in filtered_live if str(cam.live_teacher_id) == str(teacher_id)]

    # Get list of teachers for filtering
    teachers = User.objects.filter(userprofile__user_type='teacher')

    return render(request, 'cameras/student_lecture_list.html', {
        'live_sessions': filtered_live,
        'recordings': recordings,
        'teachers': teachers,
        'query': query,
        'selected_teacher': teacher_id
    })


@login_required
def watch_live(request, camera_id):
    """Watch a live lecture (Student View)"""
    # Allow admins to view any camera, even if not marked "live"
    if is_admin(request.user):
        camera = get_object_or_404(Camera, id=camera_id)
    else:
        camera = get_object_or_404(Camera, id=camera_id, is_live=True)

    # In a real app, we'd check if the student belongs to the teacher's class

    context = {
        'camera': camera,
        'teacher': camera.live_teacher if hasattr(camera, 'live_teacher') else None,
    }
    return render(request, 'cameras/watch_live.html', context)


@login_required
def start_camera_recording(request, camera_id):
    """Start recording a camera feed using FFmpeg engine"""
    camera = get_object_or_404(Camera, id=camera_id)
    if not camera.has_permission(request.user):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})

    quality = request.POST.get('quality', '720p')
    audio_source = request.POST.get('audio_source', 'pc')  # 'pc', 'remote', or 'camera'
    success, message = recording_engine.start_recording(camera, request.user, quality, audio_source)

    if success:
        return JsonResponse({'status': 'success', 'message': f'Recording started in {quality}'})
    else:
        return JsonResponse({'status': 'error', 'message': message})


@login_required
def stop_camera_recording(request, camera_id):
    """Stop recording and prepare for publishing"""
    camera = get_object_or_404(Camera, id=camera_id)
    success, recording_id = recording_engine.stop_recording(camera.id, request.user.id)

    if success:
        rec = None
        try:
            from .models import CameraRecording
            rec = CameraRecording.objects.filter(id=recording_id).first()
        except:
            pass
        
        video_url = None
        if rec:
            if rec.is_chunked:
                video_url = reverse('watch_recording', args=[rec.id])
            elif rec.video_file:
                video_url = rec.video_file.url

        return JsonResponse({
            'status': 'success',
            'recording_id': recording_id,
            'video_url': video_url,
            'message': 'Recording stopped and being processed'
        })
    else:
        return JsonResponse({'status': 'error', 'message': 'No active recording found'})


@login_required
def camera_feed_proxy(request, camera_id):
    """Proxy camera feed requests to the camera microservice"""
    camera = get_object_or_404(Camera, id=camera_id)
    if not camera.has_permission(request.user):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)

    # Get query params
    query_params = request.GET.urlencode()
    url = f'http://localhost:8003/cameras/{camera_id}/feed/'
    if query_params:
        url += f'?{query_params}'

    try:
        # Forward request to camera microservice
        response = requests.get(url, stream=True, timeout=30)
        # Return streaming response
        from django.http import HttpResponse
        return HttpResponse(
            streaming_content=response.iter_content(chunk_size=1024),
            content_type=response.headers.get('Content-Type', 'multipart/x-mixed-replace;boundary=frame')
        )
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def publish_recording(request):
    """Publish a finished recording with title and description"""
    if request.method == 'POST':
        recording_id = request.POST.get('recording_id')
        title = request.POST.get('title')
        description = request.POST.get('description')

        try:
            rec = CameraRecording.objects.get(id=recording_id, teacher=request.user)
            rec.title = title
            rec.description = description
            rec.is_published = True
            rec.save()
            return JsonResponse({'status': 'success', 'message': 'Lecture published successfully'})
        except CameraRecording.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Recording not found'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

