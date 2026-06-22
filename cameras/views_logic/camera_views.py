
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from ..models import Camera, CameraPermission
from .utils import is_admin, test_rtsp_paths

User = get_user_model()


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
        # Check if we are updating camera details or just permissions
        # If 'name' is in POST, we are updating details
        if 'name' in request.POST:
            camera.name = request.POST.get('name')
            camera.camera_type = request.POST.get('camera_type')
            camera.ip_address = request.POST.get('ip_address')
            port_val = request.POST.get('port')
            if port_val:
                camera.port = int(port_val)
            camera.username = request.POST.get('username', '')
            camera.password = request.POST.get('password', '')

            # If RTSP and details changed, re-detect path
            if camera.camera_type == 'rtsp':
                detected_path, _ = test_rtsp_paths(camera.ip_address, camera.port, camera.username, camera.password)
                if detected_path:
                    camera.stream_path = detected_path
                    camera.is_active = True

            camera.save()

        # Always handle teacher assignments if 'teachers' is in POST or if it's the assignment form
        # The assignment form has a hidden input 'camera_id' and a list of 'teachers'
        if 'teachers' in request.POST or ('name' not in request.POST and 'camera_id' in request.POST):
            teacher_ids = request.POST.getlist('teachers')
            logger.info(f"Updating permissions for camera {camera_id}. Teachers: {teacher_ids}")
            # Clear old permissions
            CameraPermission.objects.filter(camera=camera).delete()
            # Add new permissions
            for t_id in teacher_ids:
                try:
                    teacher = User.objects.get(id=t_id)
                    CameraPermission.objects.create(camera=camera, teacher=teacher, granted_by=request.user)
                    logger.info(f"Granted permission to teacher {teacher.username} for camera {camera.name}")
                except User.DoesNotExist:
                    logger.warning(f"Teacher with ID {t_id} does not exist")
                    continue
                except Exception as e:
                    logger.error(f"Error granting permission: {e}")
                    continue

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
def delete_camera(request, camera_id):
    if not is_admin(request.user):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})

    if request.method == 'POST':
        camera = get_object_or_404(Camera, id=camera_id)
        try:
            camera.delete()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Error deleting camera {camera_id}: {e}")
            # Fallback for SQLite ghost constraints
            from django.db import connection
            try:
                with connection.cursor() as cursor:
                    cursor.execute('PRAGMA foreign_keys = OFF;')
                    camera.delete()
                    cursor.execute('PRAGMA foreign_keys = ON;')
                return JsonResponse({'status': 'success'})
            except Exception as e2:
                return JsonResponse({'status': 'error', 'message': str(e2)}, status=500)
    return redirect('admin_dashboard')


@login_required
def camera_feed(request, camera_id):
    """
    Gateway to the dedicated Camera Service.
    Redirects the browser directly to the camera service MJPEG feed URL.
    This is necessary because Daphne (ASGI) buffers StreamingHttpResponse,
    preventing MJPEG frames from reaching the browser in real-time.
    """
    from django.conf import settings
    from django.http import HttpResponseRedirect
    from urllib.parse import urlparse
    from .utils import can_view_camera

    camera = get_object_or_404(Camera, id=camera_id)

    # Check permission
    if not can_view_camera(request.user, camera):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    # Build a browser-reachable URL to the camera service.
    # Use the same host the browser used to reach us, but swap the port to 8003.
    internal_url = getattr(settings, 'CAMERA_SERVICE_URL', 'http://localhost:8003')
    parsed = urlparse(internal_url)
    service_port = parsed.port or 8003
    request_host = request.get_host().split(':')[0]  # e.g. 'localhost' or '10.7.11.141'

    query_params = request.GET.urlencode()
    feed_url = f'http://{request_host}:{service_port}/cameras/{camera_id}/feed/'
    if query_params:
        feed_url += f'?{query_params}'

    return HttpResponseRedirect(feed_url)


@login_required
def test_camera(request, camera_id):
    """Test camera connection - uses camera service for diagnostics"""
    import requests
    if not is_admin(request.user):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})

    camera = get_object_or_404(Camera, id=camera_id)

    try:
        from django.conf import settings
        internal_url = getattr(settings, 'CAMERA_SERVICE_URL', 'http://localhost:8003')
        # Use camera service for testing (it has better RTSP handling)
        camera_service_url = f'{internal_url}/cameras/{camera_id}/test/'
        response = requests.get(camera_service_url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            return JsonResponse(data)
        else:
            return JsonResponse({
                'status': 'error',
                'message': f'Camera service error: HTTP {response.status_code}',
                'hint': 'Make sure camera service is running on port 8003'
            })
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            'status': 'error',
            'message': 'Camera service not running on port 8003',
            'hint': 'Start camera service: cd camera_service && python manage.py runserver 8003'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        })


@login_required
def live_monitor(request):
    """View to see all live camera feeds in a grid"""
    import requests
    from mobile_cameras.models import MobileCamera, MobileCameraPermission
    if not request.user.is_authenticated:
        return redirect('login')

    # Filter RTSP cameras based on user permissions
    if is_admin(request.user):
        cameras = Camera.objects.all()
        mobile_cameras = MobileCamera.objects.all()
    elif hasattr(request.user, 'userprofile'):
        if request.user.userprofile.user_type == 'teacher':
            # Teachers see all cameras they have permission for, even if offline
            camera_ids = CameraPermission.objects.filter(teacher=request.user).values_list('camera_id', flat=True)
            cameras = Camera.objects.filter(id__in=camera_ids)

            mobile_camera_ids = MobileCameraPermission.objects.filter(teacher=request.user).values_list('mobile_camera_id', flat=True)
            mobile_cameras = MobileCamera.objects.filter(id__in=mobile_camera_ids)
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
    camera_service_running = False
    try:
        from django.conf import settings
        internal_url = getattr(settings, 'CAMERA_SERVICE_URL', 'http://localhost:8003')
        response = requests.get(f'{internal_url}/cameras/', timeout=2)
        camera_service_running = response.status_code == 200
    except Exception as e:
        logger.warning(f"Camera service is offline: {e}")

    context = {
        'cameras': cameras,
        'mobile_cameras': mobile_cameras,
        'camera_service_running': camera_service_running,
    }
    return render(request, 'cameras/live_monitor.html', context)


@login_required
def test_feed_page(request):
    """Simple test page for camera feed"""
    return render(request, 'test_feed.html')

