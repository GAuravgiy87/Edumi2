import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse
from django.contrib.auth.models import User
from .models import MobileCamera, MobileCameraPermission

logger = logging.getLogger('mobile_cameras')


from cameras.utils import is_admin, auto_detect_stream_path, parse_stream_url, validate_rtsp_url


def can_view_mobile_camera(user, mobile_camera):
    """Check if user can view a specific mobile camera"""
    if is_admin(user):
        return True
    # Teachers can view mobile cameras they have permission for
    if hasattr(user, 'userprofile') and user.userprofile.user_type == 'teacher':
        return mobile_camera.has_permission(user)
    # Students can view all active mobile cameras
    if hasattr(user, 'userprofile') and user.userprofile.user_type == 'student':
        return mobile_camera.is_active
    return False


@login_required
def mobile_camera_dashboard(request):
    """Dashboard for managing mobile cameras"""
    if not is_admin(request.user):
        return redirect('login')
    
    mobile_cameras = MobileCamera.objects.all()
    teachers = User.objects.filter(userprofile__user_type='teacher')
    
    # Get permissions for each mobile camera
    mobile_camera_permissions = {}
    for mobile_camera in mobile_cameras:
        mobile_camera_permissions[mobile_camera.id] = mobile_camera.get_authorized_teachers()
    
    context = {
        'mobile_cameras': mobile_cameras,
        'teachers': teachers,
        'mobile_camera_permissions': mobile_camera_permissions,
    }
    return render(request, 'mobile_cameras/dashboard.html', context)


# Removed redundant test_mobile_camera_paths and parse_camera_url (now in utils.py)


@login_required
def add_mobile_camera(request):
    """Add a new mobile camera"""
    if not is_admin(request.user):
        return redirect('login')
    
    if request.method == 'POST':
        # Check if URL is provided
        camera_url = request.POST.get('camera_url', '').strip()
        
        if camera_url:
            # Parse URL using unified utility
            parsed = parse_stream_url(camera_url)
            ip_address = parsed['ip_address']
            port = parsed['port']
            username = parsed['username']
            password = parsed['password']
        else:
            ip_address = request.POST.get('ip_address')
            port = request.POST.get('port', 8080)
            username = request.POST.get('username', '')
            password = request.POST.get('password', '')

        # Use unified auto-detection
        logger.info(f"Auto-detecting path for mobile camera at {ip_address}:{port}")
        detected_path, stream_url = auto_detect_stream_path(ip_address, port, username, password, protocol='http')
        
        name = request.POST.get('name') or f"Mobile Camera {ip_address}"
        camera_type = request.POST.get('camera_type', 'droidcam')

        if detected_path:
            stream_path = detected_path
        else:
            # Use default based on camera type if auto-detection fails
            if camera_type == 'droidcam':
                stream_path = '/mjpegfeed'
            else:
                stream_path = '/video'
        
        # Create mobile camera
        MobileCamera.objects.create(
            name=name,
            camera_type=camera_type,
            ip_address=ip_address,
            port=port,
            username=username,
            password=password,
            stream_path=stream_path,
            is_active=True
        )
        return redirect('mobile_cameras:dashboard')
    
    return render(request, 'mobile_cameras/add_camera.html')


@login_required
def delete_mobile_camera(request, mobile_camera_id):
    """Delete a mobile camera"""
    if not is_admin(request.user):
        return redirect('login')
    
    mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
    mobile_camera.delete()
    return redirect('mobile_cameras:dashboard')


def mobile_camera_feed(request, mobile_camera_id):
    """Proxy mobile camera HLS feed from camera service on port 8001"""
    mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
    
    # Check permission
    if not can_view_mobile_camera(request.user, mobile_camera):
        return JsonResponse({'error': 'You do not have permission to view this camera'}, status=403)
    
    import requests
    from django.http import HttpResponse, StreamingHttpResponse
    
    filename = request.GET.get('file', 'stream.m3u8')
    camera_service_url = f'http://localhost:8001/api/mobile-cameras/{mobile_camera_id}/feed/?file={filename}'
    
    try:
        response = requests.get(camera_service_url, stream=True, timeout=10)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', 'application/octet-stream')
            django_response = StreamingHttpResponse(
                response.iter_content(chunk_size=8192),
                content_type=content_type
            )
            if 'Cache-Control' in response.headers:
                django_response['Cache-Control'] = response.headers['Cache-Control']
            django_response['Access-Control-Allow-Origin'] = '*'
            return django_response
        else:
            return HttpResponse(status=response.status_code)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error proxying HLS feed for mobile camera {mobile_camera_id}: {e}")
        return JsonResponse({'error': 'Proxy server unavailable'}, status=503)


@login_required
def view_mobile_camera(request, mobile_camera_id):
    """View a single mobile camera feed"""
    mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
    
    if not can_view_mobile_camera(request.user, mobile_camera):
        return redirect('login')
    
    return render(request, 'mobile_cameras/view_camera.html', {'mobile_camera': mobile_camera})


@login_required
def live_monitor(request):
    """View all mobile camera feeds in a grid"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Filter mobile cameras based on user permissions
    if is_admin(request.user):
        mobile_cameras = MobileCamera.objects.filter(is_active=True)
    elif hasattr(request.user, 'userprofile'):
        if request.user.userprofile.user_type == 'teacher':
            mobile_camera_ids = MobileCameraPermission.objects.filter(teacher=request.user).values_list('mobile_camera_id', flat=True)
            mobile_cameras = MobileCamera.objects.filter(id__in=mobile_camera_ids, is_active=True)
        elif request.user.userprofile.user_type == 'student':
            mobile_cameras = MobileCamera.objects.filter(is_active=True)
        else:
            mobile_cameras = MobileCamera.objects.none()
    else:
        mobile_cameras = MobileCamera.objects.none()
    
    context = {
        'mobile_cameras': mobile_cameras,
    }
    return render(request, 'mobile_cameras/live_monitor.html', context)


@login_required
def test_mobile_camera(request, mobile_camera_id):
    """Test mobile camera connection"""
    mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
    
    try:
        url = mobile_camera.get_stream_url()
        is_valid, message = validate_rtsp_url(url, timeout=5)
        
        if is_valid:
            return JsonResponse({
                'status': 'success',
                'message': 'Mobile camera is accessible',
                'url': url
            })
        return JsonResponse({
            'status': 'error',
            'message': message
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        })



@login_required
def grant_permission(request, mobile_camera_id):
    """Grant a teacher permission to view a mobile camera"""
    if not is_admin(request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
        teacher_id = request.POST.get('teacher_id')
        teacher = get_object_or_404(User, id=teacher_id)
        
        MobileCameraPermission.objects.get_or_create(
            mobile_camera=mobile_camera,
            teacher=teacher,
            defaults={'granted_by': request.user}
        )
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def revoke_permission(request, mobile_camera_id, teacher_id):
    """Revoke a teacher's permission to view a mobile camera"""
    if not is_admin(request.user):
        return redirect('login')
    
    mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
    teacher = get_object_or_404(User, id=teacher_id)
    
    MobileCameraPermission.objects.filter(mobile_camera=mobile_camera, teacher=teacher).delete()
    
    return redirect('mobile_cameras:manage_permissions', mobile_camera_id=mobile_camera_id)


@login_required
def manage_permissions(request, mobile_camera_id):
    """Manage mobile camera permissions"""
    if not is_admin(request.user):
        return redirect('login')
    
    mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
    teachers = User.objects.filter(userprofile__user_type='teacher')
    authorized_teachers = mobile_camera.get_authorized_teachers()
    
    context = {
        'mobile_camera': mobile_camera,
        'teachers': teachers,
        'authorized_teachers': authorized_teachers,
    }
    return render(request, 'mobile_cameras/manage_permissions.html', context)
