
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib.auth import get_user_model
from ..models import Camera, CameraPermission
from .utils import is_admin, test_rtsp_paths

logger = logging.getLogger('cameras')

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
        stream_path = request.POST.get('stream_path', None)

        if camera_type == 'rtsp':
            if not stream_path:
                # Try auto-detect path, but if that fails use default
                try:
                    detected_path, _ = test_rtsp_paths(ip_address, port, username, password)
                    stream_path = detected_path if detected_path else '/stream'
                except Exception:
                    stream_path = '/stream'
            is_active = True  # Assume active, user can test later
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

    try:
        camera = get_object_or_404(Camera, id=camera_id)
        logger.info(f"edit_camera called for camera {camera_id}, method: {request.method}")
        if request.method == 'POST':
            logger.info(f"POST data keys: {list(request.POST.keys())}")
            # Check if we are updating camera details or just permissions
            # If 'name' is in POST, we are updating details
            if 'name' in request.POST:
                logger.info("Updating camera details")
                camera.name = request.POST.get('name')
                camera.camera_type = request.POST.get('camera_type')
                camera.ip_address = request.POST.get('ip_address')
                port_val = request.POST.get('port')
                if port_val:
                    camera.port = int(port_val)
                camera.username = request.POST.get('username', '')
                camera.password = request.POST.get('password', '')
                # Allow manual stream_path input
                stream_path = request.POST.get('stream_path', None)

                if camera.camera_type == 'rtsp':
                    if stream_path:
                        camera.stream_path = stream_path
                    else:
                        # Try re-detect path if no manual path provided, but don't fail
                        try:
                            detected_path, _ = test_rtsp_paths(camera.ip_address, camera.port, camera.username, camera.password)
                            if detected_path:
                                camera.stream_path = detected_path
                        except Exception as e:
                            logger.warning(f"Path detection failed: {e}")
                            pass  # Keep existing stream_path if detection fails
                else:
                    # Mobile cameras have fixed paths
                    camera.stream_path = '/video' if camera.camera_type == 'ip_webcam' else '/mjpegfeed'
                camera.is_active = True  # Assume active
                camera.save()
                logger.info("Camera details saved")

            # Always handle teacher assignments if 'teachers' is in POST or if it's the assignment form
            # The assignment form has a hidden input 'camera_id' and a list of 'teachers'
            if 'teachers' in request.POST or ('name' not in request.POST and 'camera_id' in request.POST):
                teacher_ids = request.POST.getlist('teachers')
                logger.info(f"Updating permissions for camera {camera_id}. Teacher IDs: {teacher_ids}")
                # Clear old permissions
                CameraPermission.objects.filter(camera=camera).delete()
                # Add new permissions
                for t_id in teacher_ids:
                    try:
                        t_id_int = int(t_id)
                        teacher = User.objects.get(id=t_id_int)
                        CameraPermission.objects.create(camera=camera, teacher=teacher, granted_by=request.user)
                        logger.info(f"Granted permission to teacher {teacher.username} for camera {camera.name}")
                    except (ValueError, User.DoesNotExist) as e:
                        logger.warning(f"Teacher with ID {t_id} does not exist or invalid: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Error granting permission: {e}", exc_info=True)
                        continue
                logger.info("Permissions updated")

            return JsonResponse({'status': 'success', 'message': 'Camera updated successfully'})

        # Return camera data for modal
        assigned_teachers = list(camera.get_authorized_teachers().values_list('id', flat=True))
        logger.info(f"Returning camera data: assigned teachers {assigned_teachers}")
        return JsonResponse({
            'id': camera.id,
            'name': camera.name,
            'camera_type': camera.camera_type,
            'ip_address': camera.ip_address,
            'port': camera.port,
            'username': camera.username,
            'password': camera.password,
            'stream_path': camera.stream_path,
            'assigned_teachers': assigned_teachers
        })
    except Exception as e:
        logger.error(f"Critical error in edit_camera: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


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


# @login_required  — permission enforced inside via can_view_camera
@login_required
def camera_feed(request, camera_id):
    """
    HTTPS-safe MJPEG proxy for the Camera Service.

    The Camera Service (Waitress) only speaks plain HTTP on port 8003 — it cannot
    serve TLS. When the main app is on HTTPS, any direct browser redirect to
    http://host:8003 triggers a Mixed-Content block.

    Solution: proxy the MJPEG stream through Django (server → server is fine over
    plain HTTP on localhost) and stream it back to the browser over the existing
    HTTPS connection. The browser never touches port 8003 directly.
    """
    import requests as req_lib
    from django.conf import settings
    from .utils import can_view_camera

    camera = get_object_or_404(Camera, id=camera_id)

    # Admins and authorized teachers can always view; students need is_live
    if not can_view_camera(request.user, camera):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    internal_url = getattr(settings, 'CAMERA_SERVICE_URL', 'http://localhost:8003')
    query_params = request.GET.urlencode()
    feed_url = f'{internal_url}/cameras/{camera_id}/feed/'
    if query_params:
        feed_url += f'?{query_params}'

    try:
        upstream = req_lib.get(feed_url, stream=True, timeout=10)
        content_type = upstream.headers.get('Content-Type', 'multipart/x-mixed-replace; boundary=frame')

        def stream():
            try:
                for chunk in upstream.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            except Exception:
                pass
            finally:
                upstream.close()

        response = StreamingHttpResponse(stream(), content_type=content_type)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['X-Accel-Buffering'] = 'no'
        return response

    except req_lib.exceptions.ConnectionError:
        # Camera service offline — fall back to in-process streamer
        logger.warning(f"Camera service offline for camera {camera_id}, falling back to in-process streamer")
        from .streaming_views import camera_manager, _generate_frames
        quality = request.GET.get('q', 'med')
        quality_map = {'4k': '4k', 'high': 'high', '1080p': 'high', '720p': 'med', '480p': 'med', '360p': 'low'}
        quality = quality_map.get(quality, quality)
        full_url = camera.get_full_rtsp_url()
        streamer = camera_manager.get_streamer(camera.id, full_url)
        response = StreamingHttpResponse(
            _generate_frames(streamer, camera, full_url, quality, camera_id),
            content_type='multipart/x-mixed-replace; boundary=frame',
        )
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['X-Accel-Buffering'] = 'no'
        return response
    except Exception as e:
        logger.error(f"camera_feed proxy error for camera {camera_id}: {e}")
        return JsonResponse({'error': str(e)}, status=500)


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
def test_feed_page(request):
    """Simple test page for camera feed"""
    return render(request, 'test_feed.html')

