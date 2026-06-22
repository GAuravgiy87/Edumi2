"""
mobile_cameras/views/camera_views.py
CRUD views: dashboard, add, delete, feed, view, live monitor, test.
"""
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse

from mobile_cameras.models import MobileCamera, MobileCameraPermission
from .utils import is_admin, can_view_mobile_camera, test_mobile_camera_paths, parse_camera_url

logger = logging.getLogger('mobile_cameras')


@login_required
def mobile_camera_dashboard(request):
    """Redirect to the unified camera dashboard."""
    return redirect('admin_dashboard')


@login_required
def add_mobile_camera(request):
    """Add a new mobile camera (admin only)."""
    if not is_admin(request.user):
        return redirect('login')

    if request.method == 'POST':
        camera_url = request.POST.get('camera_url', '').strip()
        if camera_url:
            try:
                parsed = parse_camera_url(camera_url)
                name = request.POST.get('name') or f"Camera {parsed['ip_address']}"
                camera_type, ip_address = parsed['camera_type'], parsed['ip_address']
                port, username, password = parsed['port'], parsed['username'], parsed['password']
            except Exception as e:
                return render(request, 'mobile_cameras/add_camera.html', {'error': f'Invalid URL format: {str(e)}'})
        else:
            name = request.POST.get('name')
            camera_type = request.POST.get('camera_type')
            ip_address = request.POST.get('ip_address')
            port = int(request.POST.get('port', 8080))
            username = request.POST.get('username', '')
            password = request.POST.get('password', '')

        detected_path, _ = test_mobile_camera_paths(ip_address, port, username, password)
        stream_path = detected_path or ('/mjpegfeed' if camera_type == 'droidcam' else '/video')

        MobileCamera.objects.create(
            name=name, camera_type=camera_type, ip_address=ip_address,
            port=port, username=username, password=password,
            stream_path=stream_path, is_active=True,
        )
        return redirect('mobile_cameras:dashboard')

    return render(request, 'mobile_cameras/add_camera.html')


@login_required
def delete_mobile_camera(request, mobile_camera_id):
    """Delete a mobile camera (admin only)."""
    if not is_admin(request.user):
        return redirect('login')
    mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
    mobile_camera.delete()
    return redirect('mobile_cameras:dashboard')


def mobile_camera_feed(request, mobile_camera_id):
    """Gateway — redirect to dedicated Camera Service on port 8003."""
    mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
    if not can_view_mobile_camera(request.user, mobile_camera):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    # In Docker, nginx handles routing. In dev, we use port 8003.
    url = f"http://{request.get_host().split(':')[0]}:8003/mobile-cameras/{mobile_camera_id}/feed/"
    return redirect(url)


@login_required
def view_mobile_camera(request, mobile_camera_id):
    """View a single mobile camera feed page."""
    mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
    if not can_view_mobile_camera(request.user, mobile_camera):
        return redirect('login')
    return render(request, 'mobile_cameras/view_camera.html', {'mobile_camera': mobile_camera})


@login_required
def live_monitor(request):
    """View all mobile cameras in a permission-filtered grid."""
    if is_admin(request.user):
        mobile_cameras = MobileCamera.objects.all()
    elif hasattr(request.user, 'userprofile'):
        utype = request.user.userprofile.user_type
        if utype == 'teacher':
            ids = MobileCameraPermission.objects.filter(teacher=request.user).values_list('mobile_camera_id', flat=True)
            mobile_cameras = MobileCamera.objects.filter(id__in=ids)
        elif utype == 'student':
            mobile_cameras = MobileCamera.objects.filter(is_active=True)
        else:
            mobile_cameras = MobileCamera.objects.none()
    else:
        mobile_cameras = MobileCamera.objects.none()
    return render(request, 'mobile_cameras/live_monitor.html', {'mobile_cameras': mobile_cameras})


@login_required
def test_mobile_camera(request, mobile_camera_id):
    """Test mobile camera HTTP connection and return status JSON."""
    import requests as req_lib
    mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
    try:
        url = mobile_camera.get_stream_url()
        resp = req_lib.get(url, timeout=5)
        if resp.status_code == 200:
            return JsonResponse({'status': 'success', 'message': 'Mobile camera is accessible', 'url': url})
        return JsonResponse({'status': 'error', 'message': f'HTTP {resp.status_code}'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'})
