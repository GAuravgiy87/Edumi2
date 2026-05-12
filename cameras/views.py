import threading
import time
import logging
from typing import Optional
from urllib.parse import urlparse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.db.models import Avg, Max, Min, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Camera, CameraPermission, HeadCountLog, HeadCountSession, CameraRecording
from .recording_engine import recording_engine
from mobile_cameras.models import MobileCamera, MobileCameraPermission
from .head_count_service import head_count_manager

logger = logging.getLogger('cameras')

def is_admin(user):
    """Check if user is admin"""
    if user.is_authenticated:
        if user.is_superuser:
            return True
    return False


def can_manage_camera(user, camera):
    """Check if user can manage a camera (admin only)"""
    return is_admin(user)


def can_view_camera(user, camera):
    """Check if user can view a camera"""
    if is_admin(user):
        return True
    # Teachers can view cameras they have permission for
    if hasattr(user, 'userprofile') and user.userprofile.user_type == 'teacher':
        return camera.has_permission(user)
    # Students can view all active cameras
    if hasattr(user, 'userprofile') and user.userprofile.user_type == 'student':
        return camera.is_active
    return False


def test_rtsp_paths(ip, port, username, password):
    """Test common RTSP paths to find the working one"""
    import cv2
    common_paths = [
        '/live',
        '/stream',
        '/h264',
        '/video',
        '/cam/realmonitor',
        '/Streaming/Channels/101',
        '/1',
        '/11',
        '/av0_0',
        '/mpeg4',
        '/media/video1',
        '/onvif1',
        '/ch0',
        '/ch01.264',
        '/',
    ]
    
    from urllib.parse import quote
    for path in common_paths:
        if username and password:
            safe_user = quote(username)
            safe_pass = quote(password)
            rtsp_url = f"rtsp://{safe_user}:{safe_pass}@{ip}:{port}{path}"
        else:
            rtsp_url = f"rtsp://{ip}:{port}{path}"
        
        try:
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000)
            
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                
                if ret and frame is not None:
                    return path, rtsp_url
            else:
                cap.release()
        except Exception as e:
            continue
    
    return None, None


def parse_rtsp_url(url):
    """
    Robustly parse an RTSP URL to extract components.
    Handles complex passwords with multiple '@' symbols.
    """
    if not url.startswith('rtsp://'):
        raise ValueError("URL must start with rtsp://")
    
    # Remove prefix
    temp = url[7:]
    
    # Standard format: [user[:pass]@]host[:port][/path]
    # Split at the LAST '@' to separate userinfo from host/path
    if '@' in temp:
        userinfo, rest = temp.rsplit('@', 1)
        # Split userinfo at the FIRST ':' to handle '@' in password
        if ':' in userinfo:
            username, password = userinfo.split(':', 1)
        else:
            username = userinfo
            password = ''
    else:
        username = ''
        password = ''
        rest = temp
    
    # Now 'rest' is host[:port][/path]
    if '/' in rest:
        hostport, stream_path = rest.split('/', 1)
        stream_path = '/' + stream_path
    else:
        hostport = rest
        stream_path = '/'
    
    if ':' in hostport:
        ip_address, port = hostport.split(':', 1)
        try:
            port = int(port)
        except ValueError:
            port = 554
    else:
        ip_address = hostport
        port = 554
    
    return {
        'ip_address': ip_address,
        'port': port,
        'username': username,
        'password': password,
        'stream_path': stream_path
    }

@login_required
def admin_dashboard(request):
    if not is_admin(request.user):
        return redirect('login')
    
    cameras = Camera.objects.all().order_by('-created_at')
    teachers = User.objects.filter(userprofile__user_type='teacher')
    
    context = {
        'cameras': cameras,
        'teachers': teachers,
    }
    return render(request, 'cameras/admin_dashboard.html', context)

@login_required
def add_camera(request):
    if not is_admin(request.user):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    if request.method == 'POST':
        name = request.POST.get('name')
        camera_type = request.POST.get('camera_type')
        ip_address = request.POST.get('ip_address')
        port = int(request.POST.get('port', 554))
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        
        if camera_type == 'rtsp':
            # Auto-detect path
            detected_path, _ = test_rtsp_paths(ip_address, port, username, password)
            stream_path = detected_path if detected_path else '/stream'
            is_active = True if detected_path else False
        else:
            # Mobile cameras have fixed paths
            stream_path = '/video' if camera_type == 'ip_webcam' else '/mjpegfeed'
            is_active = True
            
        camera = Camera.objects.create(
            name=name,
            camera_type=camera_type,
            ip_address=ip_address,
            port=port,
            username=username,
            password=password,
            stream_path=stream_path,
            is_active=is_active
        )
        
        return JsonResponse({
            'status': 'success', 
            'message': 'Camera added successfully',
            'is_active': is_active
        })
    
    return redirect('admin_dashboard')

@login_required
def edit_camera(request, camera_id):
    if not is_admin(request.user):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    camera = get_object_or_404(Camera, id=camera_id)
    
    if request.method == 'POST':
        camera.name = request.POST.get('name')
        camera.camera_type = request.POST.get('camera_type')
        camera.ip_address = request.POST.get('ip_address')
        camera.port = int(request.POST.get('port'))
        camera.username = request.POST.get('username', '')
        camera.password = request.POST.get('password', '')
        
        # If RTSP and details changed, re-detect path
        if camera.camera_type == 'rtsp':
            detected_path, _ = test_rtsp_paths(camera.ip_address, camera.port, camera.username, camera.password)
            if detected_path:
                camera.stream_path = detected_path
                camera.is_active = True
        
        # Assign teachers
        teacher_ids = request.POST.getlist('teachers')
        # Clear old permissions
        CameraPermission.objects.filter(camera=camera).delete()
        # Add new permissions
        for t_id in teacher_ids:
            teacher = User.objects.get(id=t_id)
            CameraPermission.objects.create(camera=camera, teacher=teacher, granted_by=request.user)
            
        camera.save()
        return JsonResponse({'status': 'success', 'message': 'Camera updated successfully'})
    
    # Return camera data for modal
    assigned_teachers = list(camera.get_authorized_teachers().values_list('id', flat=True))
    return JsonResponse({
        'id': camera.id,
        'name': camera.name,
        'camera_type': camera.camera_type,
        'ip_address': camera.ip_address,
        'port': camera.port,
        'username': camera.username,
        'password': camera.password,
        'assigned_teachers': assigned_teachers
    })

@login_required
def camera_live_view(request, camera_id):
    if not is_admin(request.user):
        return redirect('login')
    
    camera = get_object_or_404(Camera, id=camera_id)
    
    # Get active session if any
    active_session = HeadCountSession.objects.filter(
        camera_id=camera.id, 
        camera_type='rtsp' if camera.camera_type == 'rtsp' else 'mobile',
        status='active'
    ).first()
    
    # In a real app, you'd track who is watching. 
    # For now we'll pass some mock/calculated data.
    context = {
        'camera': camera,
        'active_session': active_session,
        'watching_teachers': [camera.get_authorized_teachers().first()], # Mock
        'start_time': active_session.started_at if active_session else timezone.now(),
        'total_students': 0, # Placeholder
    }
    return render(request, 'cameras/camera_live_view.html', context)


@login_required
def delete_camera(request, camera_id):
    if not is_admin(request.user):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    if request.method == 'POST':
        camera = get_object_or_404(Camera, id=camera_id)
        camera.delete()
        return JsonResponse({'status': 'success'})
    return redirect('admin_dashboard')


@login_required
def camera_feed(request, camera_id):
    """
    Gateway to the dedicated Camera Service.
    Checks permissions before redirecting to the streaming microservice.
    """
    camera = get_object_or_404(Camera, id=camera_id)
    
    # Check permission
    if not can_view_camera(request.user, camera):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Redirect to dedicated camera service (port 8001)
    # We pass the same quality parameter if present
    quality = request.GET.get('q', 'med')
    camera_service_url = f"http://{request.get_host().split(':')[0]}:8001/cameras/{camera_id}/feed/?q={quality}"
    
    return redirect(camera_service_url)

@login_required
def test_camera(request, camera_id):
    """Redirect camera testing to the dedicated service"""
    if not is_admin(request.user):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    camera = get_object_or_404(Camera, id=camera_id)
    camera_service_url = f"http://{request.get_host().split(':')[0]}:8001/cameras/{camera_id}/test/"
    
    return redirect(camera_service_url)

@login_required
def live_monitor(request):
    """View to see all live camera feeds in a grid"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Filter RTSP cameras based on user permissions
    if is_admin(request.user):
        cameras = Camera.objects.filter(is_active=True)
        mobile_cameras = MobileCamera.objects.filter(is_active=True)
    elif hasattr(request.user, 'userprofile'):
        if request.user.userprofile.user_type == 'teacher':
            # Teachers see cameras they have permission for
            camera_ids = CameraPermission.objects.filter(teacher=request.user).values_list('camera_id', flat=True)
            cameras = Camera.objects.filter(id__in=camera_ids, is_active=True)
            
            mobile_camera_ids = MobileCameraPermission.objects.filter(teacher=request.user).values_list('mobile_camera_id', flat=True)
            mobile_cameras = MobileCamera.objects.filter(id__in=mobile_camera_ids, is_active=True)
        elif request.user.userprofile.user_type == 'student':
            # Students see all active cameras
            cameras = Camera.objects.filter(is_active=True)
            mobile_cameras = MobileCamera.objects.filter(is_active=True)
        else:
            cameras = Camera.objects.none()
            mobile_cameras = MobileCamera.objects.none()
    else:
        cameras = Camera.objects.none()
        mobile_cameras = MobileCamera.objects.none()
    
    # Check if camera service is running
    import requests
    camera_service_running = False
    try:
        response = requests.get('http://localhost:8001/api/cameras/', timeout=2)
        camera_service_running = response.status_code == 200
    except:
        pass
    
    context = {
        'cameras': cameras,
        'mobile_cameras': mobile_cameras,
        'camera_service_running': camera_service_running,
    }
    return render(request, 'cameras/live_monitor.html', context)

@login_required
def teacher_camera_dashboard(request):
    """Dashboard for teachers to see assigned cameras"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'teacher':
        return redirect('dashboard')
        
    camera_ids = CameraPermission.objects.filter(teacher=request.user).values_list('camera_id', flat=True)
    cameras = Camera.objects.filter(id__in=camera_ids, is_active=True)
    
    # Get recent recordings by this teacher
    recent_recordings = CameraRecording.objects.filter(teacher=request.user).order_by('-created_at')[:5]
    
    return render(request, 'cameras/teacher_dashboard.html', {
        'cameras': cameras,
        'recent_recordings': recent_recordings
    })

@login_required
def teacher_control_room(request, camera_id):
    """Teacher control room for live streaming and recording"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    # Check permission
    if not camera.has_permission(request.user):
        return redirect('dashboard')
    
    # Mark camera as live when teacher enters
    camera.is_live = True
    camera.live_teacher = request.user
    camera.save()
        
    context = {
        'camera': camera,
        'qualities': ['360p', '480p', '720p', '1080p'],
        'default_quality': '720p'
    }
    return render(request, 'cameras/teacher_control_room.html', context)

@login_required
def stop_streaming(request, camera_id):
    """Teacher leaves control room or stops streaming"""
    camera = get_object_or_404(Camera, id=camera_id)
    if camera.live_teacher == request.user:
        camera.is_live = False
        camera.live_teacher = None
        camera.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Not the live teacher'})

@login_required
def student_lecture_list(request):
    """List all available live sessions and recorded lectures for students"""
    query = request.GET.get('q', '')
    teacher_id = request.GET.get('teacher', '')
    
    # Get all live cameras
    live_sessions = Camera.objects.filter(is_live=True).select_related('live_teacher')
    
    # Get all published recordings
    recordings = CameraRecording.objects.filter(is_published=True).select_related('teacher', 'camera')
    
    if query:
        recordings = recordings.filter(
            Q(title__icontains=query) | 
            Q(teacher__username__icontains=query) |
            Q(camera__name__icontains=query)
        )
        live_sessions = live_sessions.filter(
            Q(name__icontains=query) | 
            Q(live_teacher__username__icontains=query)
        )
        
    if teacher_id:
        recordings = recordings.filter(teacher_id=teacher_id)
        live_sessions = live_sessions.filter(live_teacher_id=teacher_id)

    # Get list of teachers for filtering
    teachers = User.objects.filter(userprofile__user_type='teacher')

    return render(request, 'cameras/student_lecture_list.html', {
        'live_sessions': live_sessions,
        'recordings': recordings,
        'teachers': teachers,
        'query': query,
        'selected_teacher': teacher_id
    })

@login_required
def watch_live(request, camera_id):
    """Watch a live lecture (Student View)"""
    camera = get_object_or_404(Camera, id=camera_id, is_live=True)
    
    # In a real app, we'd check if the student belongs to the teacher's class
    
    context = {
        'camera': camera,
        'teacher': camera.live_teacher,
    }
    return render(request, 'cameras/watch_live.html', context)

@login_required
def watch_recording(request, recording_id):
    """Watch a recorded lecture (Student View)"""
    recording = get_object_or_404(CameraRecording, id=recording_id, is_published=True)
    
    # Recommended videos (same teacher or same camera)
    recommended = CameraRecording.objects.filter(
        is_published=True
    ).exclude(id=recording_id).filter(
        Q(teacher=recording.teacher) | Q(camera=recording.camera)
    ).order_by('-created_at')[:5]
    
    return render(request, 'cameras/watch_recording.html', {
        'recording': recording,
        'recommended': recommended
    })

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

@login_required
def start_camera_recording(request, camera_id):
    """Start recording a camera feed using FFmpeg engine"""
    camera = get_object_or_404(Camera, id=camera_id)
    if not camera.has_permission(request.user):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
        
    quality = request.POST.get('quality', '720p')
    success, message = recording_engine.start_recording(camera, request.user, quality)
    
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
        return JsonResponse({
            'status': 'success', 
            'recording_id': recording_id,
            'message': 'Recording stopped and being processed'
        })
    else:
        return JsonResponse({'status': 'error', 'message': 'No active recording found'})

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

@login_required
def test_camera(request, camera_id):
    """Test camera connection - uses camera service for diagnostics"""
    import requests
    camera = get_object_or_404(Camera, id=camera_id)
    
    try:
        # Use camera service for testing (it has better RTSP handling)
        camera_service_url = f'http://localhost:8001/api/cameras/{camera_id}/test/'
        response = requests.get(camera_service_url, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return JsonResponse(data)
        else:
            return JsonResponse({
                'status': 'error',
                'message': f'Camera service error: HTTP {response.status_code}',
                'hint': 'Make sure camera service is running on port 8001'
            })
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            'status': 'error',
            'message': 'Camera service not running on port 8001',
            'hint': 'Start camera service: cd camera_service && python manage.py runserver 8001'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        })

@login_required
def test_feed_page(request):
    """Simple test page for camera feed"""
    return render(request, 'test_feed.html')

@login_required
def grant_permission(request, camera_id):
    """Grant a teacher permission to view a camera"""
    if not is_admin(request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        camera = get_object_or_404(Camera, id=camera_id)
        teacher_id = request.POST.get('teacher_id')
        teacher = get_object_or_404(User, id=teacher_id)
        
        CameraPermission.objects.get_or_create(
            camera=camera,
            teacher=teacher,
            defaults={'granted_by': request.user}
        )
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def revoke_permission(request, camera_id, teacher_id):
    """Revoke a teacher's permission to view a camera"""
    if not is_admin(request.user):
        return redirect('login')
    
    camera = get_object_or_404(Camera, id=camera_id)
    teacher = get_object_or_404(User, id=teacher_id)
    
    CameraPermission.objects.filter(camera=camera, teacher=teacher).delete()
    
    return redirect('manage_permissions', camera_id=camera_id)

@login_required
def manage_permissions(request, camera_id):
    """Manage camera permissions"""
    if not is_admin(request.user):
        return redirect('login')
    
    camera = get_object_or_404(Camera, id=camera_id)
    teachers = User.objects.filter(userprofile__user_type='teacher')
    authorized_teachers = camera.get_authorized_teachers()
    
    context = {
        'camera': camera,
        'teachers': teachers,
        'authorized_teachers': authorized_teachers,
    }
    return render(request, 'cameras/manage_permissions.html', context)


# ─────────────────────────────────────────────────────────────
# HEAD COUNTING VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
def head_count_dashboard(request):
    """Dashboard for head counting - shows all cameras with head count capability"""
    # Get cameras based on user role
    if is_admin(request.user):
        rtsp_cameras = Camera.objects.filter(is_active=True)
        mobile_cameras = MobileCamera.objects.filter(is_active=True)
    elif hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'teacher':
        # Teachers see cameras they have permission for
        camera_ids = CameraPermission.objects.filter(teacher=request.user).values_list('camera_id', flat=True)
        rtsp_cameras = Camera.objects.filter(id__in=camera_ids, is_active=True)
        
        mobile_camera_ids = MobileCameraPermission.objects.filter(teacher=request.user).values_list('mobile_camera_id', flat=True)
        mobile_cameras = MobileCamera.objects.filter(id__in=mobile_camera_ids, is_active=True)
    else:
        rtsp_cameras = Camera.objects.none()
        mobile_cameras = MobileCamera.objects.none()
    
    # Check active sessions
    active_sessions = head_count_manager.get_active_sessions()
    
    # Add session status to cameras
    for camera in rtsp_cameras:
        camera.has_active_session = head_count_manager.is_session_active('rtsp', camera.id)
        camera.camera_type = 'rtsp'
    
    for camera in mobile_cameras:
        camera.has_active_session = head_count_manager.is_session_active('mobile', camera.id)
        camera.camera_type = 'mobile'
    
    # Get recent head count logs
    recent_logs = HeadCountLog.objects.all()[:10]
    
    context = {
        'rtsp_cameras': rtsp_cameras,
        'mobile_cameras': mobile_cameras,
        'active_sessions': active_sessions,
        'recent_logs': recent_logs,
    }
    return render(request, 'cameras/head_count_dashboard.html', context)


@login_required
def start_head_count(request, camera_type, camera_id):
    """Start head counting session - proxies request to dedicated camera service"""
    import requests
    
    # Check permissions first
    if camera_type == 'rtsp':
        camera = get_object_or_404(Camera, id=camera_id)
    elif camera_type == 'mobile':
        camera = get_object_or_404(MobileCamera, id=camera_id)
    else:
        return JsonResponse({'error': 'Invalid camera type'}, status=400)
    
    if not can_view_camera(request.user, camera):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Prepare parameters for the microservice
    classroom_id = request.POST.get('classroom_id') or request.GET.get('classroom_id') or ''
    interval = request.POST.get('interval') or request.GET.get('interval') or '30'
    
    try:
        service_url = f'http://localhost:8001/head-count/start/{camera_type}/{camera_id}/'
        params = {
            'user_id': request.user.id,
            'classroom_id': classroom_id,
            'interval': interval
        }
        response = requests.get(service_url, params=params, timeout=10)
        return JsonResponse(response.json(), status=response.status_code)
    except Exception as e:
        return JsonResponse({'error': f'Camera service error: {str(e)}'}, status=500)


@login_required
def stop_head_count(request, camera_type, camera_id):
    """Stop head counting session - proxies request to dedicated camera service"""
    import requests
    try:
        service_url = f'http://localhost:8001/head-count/stop/{camera_type}/{camera_id}/'
        response = requests.get(service_url, timeout=10)
        return JsonResponse(response.json(), status=response.status_code)
    except Exception as e:
        return JsonResponse({'error': f'Camera service error: {str(e)}'}, status=500)


@login_required
def head_count_logs(request):
    """View head count logs with filtering"""
    logs = HeadCountLog.objects.all()
    
    # Filter by camera type
    camera_type = request.GET.get('camera_type')
    if camera_type:
        logs = logs.filter(camera_type=camera_type)
    
    # Filter by camera
    camera_id = request.GET.get('camera_id')
    if camera_id:
        logs = logs.filter(camera_id=camera_id)
    
    # Filter by classroom
    classroom_id = request.GET.get('classroom')
    if classroom_id:
        logs = logs.filter(classroom_id=classroom_id)
    
    # Filter by date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        logs = logs.filter(date__gte=date_from)
    if date_to:
        logs = logs.filter(date__lte=date_to)
    
    # Filter by hour
    hour = request.GET.get('hour')
    if hour:
        logs = logs.filter(hour=int(hour))
    
    # Calculate statistics
    stats = logs.aggregate(
        total_records=Count('id'),
        avg_head_count=Avg('head_count'),
        max_head_count=Max('head_count'),
        min_head_count=Min('head_count'),
        avg_confidence=Avg('confidence_score')
    )
    
    # Group by date for chart data
    date_stats = logs.values('date').annotate(
        avg_count=Avg('head_count'),
        max_count=Max('head_count'),
        total=Count('id')
    ).order_by('-date')[:30]
    
    # Group by hour for time-wise analysis
    hour_stats = logs.values('hour').annotate(
        avg_count=Avg('head_count'),
        total=Count('id')
    ).order_by('hour')
    
    # Get classrooms for filter dropdown
    from meetings.models import Classroom
    classrooms = Classroom.objects.all()
    
    context = {
        'logs': logs[:100],  # Limit to 100 records
        'stats': stats,
        'date_stats': date_stats,
        'hour_stats': hour_stats,
        'classrooms': classrooms,
        'filter_params': request.GET,
    }
    return render(request, 'cameras/head_count_logs.html', context)


@login_required
def head_count_log_detail(request, log_id):
    """View details of a specific head count log"""
    log = get_object_or_404(HeadCountLog, id=log_id)
    
    context = {
        'log': log,
    }
    return render(request, 'cameras/head_count_log_detail.html', context)


@login_required
def head_count_session_history(request):
    """View history of head counting sessions"""
    sessions = HeadCountSession.objects.all()
    
    # Filter by status
    status = request.GET.get('status')
    if status:
        sessions = sessions.filter(status=status)
    
    # Filter by date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        sessions = sessions.filter(started_at__date__gte=date_from)
    if date_to:
        sessions = sessions.filter(started_at__date__lte=date_to)
    
    context = {
        'sessions': sessions[:50],
    }
    return render(request, 'cameras/head_count_sessions.html', context)


@login_required
def head_count_api(request, camera_type, camera_id):
    """API endpoint to get current head count for a camera"""
    current_count = head_count_manager.get_current_count(camera_type, camera_id)
    is_active = head_count_manager.is_session_active(camera_type, camera_id)
    
    return JsonResponse({
        'camera_type': camera_type,
        'camera_id': camera_id,
        'is_active': is_active,
        'current_count': current_count,
    })


@login_required
def head_count_report(request):
    """Generate head count reports - class-wise, day-wise, time-wise"""
    # Get filter parameters
    report_type = request.GET.get('report_type', 'daily')
    classroom_id = request.GET.get('classroom')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    logs = HeadCountLog.objects.all()
    
    # Apply filters
    if classroom_id:
        logs = logs.filter(classroom_id=classroom_id)
    if date_from:
        logs = logs.filter(date__gte=date_from)
    if date_to:
        logs = logs.filter(date__lte=date_to)
    
    report_data = {}
    
    if report_type == 'class_wise':
        # Group by classroom
        report_data = logs.values(
            'classroom__title', 'classroom_id'
        ).annotate(
            total_records=Count('id'),
            avg_head_count=Avg('head_count'),
            max_head_count=Max('head_count'),
            min_head_count=Min('head_count'),
        ).order_by('-total_records')
        
    elif report_type == 'day_wise':
        # Group by date
        report_data = logs.values('date').annotate(
            total_records=Count('id'),
            avg_head_count=Avg('head_count'),
            max_head_count=Max('head_count'),
            min_head_count=Min('head_count'),
        ).order_by('-date')
        
    elif report_type == 'time_wise':
        # Group by hour
        report_data = logs.values('hour').annotate(
            total_records=Count('id'),
            avg_head_count=Avg('head_count'),
            max_head_count=Max('head_count'),
        ).order_by('hour')
        
    elif report_type == 'camera_wise':
        # Group by camera
        report_data = logs.values(
            'camera_type', 'camera_id', 'camera_name'
        ).annotate(
            total_records=Count('id'),
            avg_head_count=Avg('head_count'),
            max_head_count=Max('head_count'),
        ).order_by('-total_records')
    
    # Get classrooms for filter
    from meetings.models import Classroom
    classrooms = Classroom.objects.all()
    
    context = {
        'report_type': report_type,
        'report_data': report_data,
        'classrooms': classrooms,
        'filter_params': request.GET,
    }
    return render(request, 'cameras/head_count_report.html', context)


@login_required
def export_head_count_csv(request):
    """Export head count logs as CSV"""
    import csv
    
    logs = HeadCountLog.objects.all()
    
    # Apply filters
    camera_type = request.GET.get('camera_type')
    if camera_type:
        logs = logs.filter(camera_type=camera_type)
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        logs = logs.filter(date__gte=date_from)
    if date_to:
        logs = logs.filter(date__lte=date_to)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="head_count_logs.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Time', 'Camera Type', 'Camera Name', 
        'Classroom', 'Head Count', 'Confidence', 'Notes'
    ])
    
    for log in logs:
        writer.writerow([
            log.date,
            log.timestamp.strftime('%H:%M:%S'),
            log.get_camera_type_display(),
            log.camera_name,
            log.classroom.title if log.classroom else 'N/A',
            log.head_count,
            f"{log.confidence_score:.2f}",
            log.notes
        ])
    
    return response
