import threading
import time
import logging
import os
from typing import Optional
from urllib.parse import urlparse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.db.models import Avg, Max, Min, Count
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Camera, CameraPermission, HeadCountLog, HeadCountSession, LiveClass, LiveClassRecording
from mobile_cameras.models import MobileCamera, MobileCameraPermission
from .head_count_service import head_count_manager
from .utils import verify_stream_token, generate_stream_token, is_admin, auto_detect_stream_path, parse_stream_url, validate_rtsp_url

logger = logging.getLogger('cameras')

# Camera service base URL — configurable via env so docker-compose can override
CAMERA_SVC = os.environ.get('CAMERA_SERVICE_URL', '{CAMERA_SVC}')


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


# Removed redundant test_rtsp_paths and parse_rtsp_url (now in utils.py)

@login_required
def admin_dashboard(request):
    if not is_admin(request.user):
        return redirect('login')

    from django.core.paginator import Paginator

    camera_list = Camera.objects.all().order_by('-id')
    paginator = Paginator(camera_list, 20)
    page_number = request.GET.get('page')
    cameras = paginator.get_page(page_number)

    # Annotate each camera with teacher count and token
    from .utils import generate_stream_token
    for camera in cameras:
        camera.teacher_count = CameraPermission.objects.filter(camera=camera).count()
        camera.temp_token = generate_stream_token(request.user, camera.id)

    context = {
        'cameras': cameras,
        'csrf_token': request.META.get('CSRF_COOKIE', ''),
    }
    return render(request, 'cameras/admin_dashboard.html', context)

@login_required
def add_camera(request):
    if not is_admin(request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    if request.method != 'POST':
        return redirect('admin_dashboard')

    camera_type = request.POST.get('camera_type', 'rtsp')
    name = request.POST.get('name', '').strip()

    if not name:
        return JsonResponse({'error': 'Camera name is required.'}, status=400)

    # Duplicate name check
    if Camera.objects.filter(name__iexact=name).exists():
        return JsonResponse({'error': f'A camera named "{name}" already exists.'}, status=400)

    if camera_type == 'rtsp':
        rtsp_url_input = request.POST.get('rtsp_url', '').strip()
        if not rtsp_url_input:
            return JsonResponse({'error': 'RTSP URL is required.'}, status=400)
        if Camera.objects.filter(rtsp_url=rtsp_url_input).exists():
            return JsonResponse({'error': 'A camera with this RTSP URL already exists.'}, status=400)
        try:
            parsed = parse_stream_url(rtsp_url_input)
            ip_address = parsed['ip_address']
            port = parsed['port']
            username = parsed['username']
            password = parsed['password']
        except Exception as e:
            return JsonResponse({'error': f'Invalid RTSP URL: {str(e)}'}, status=400)
        protocol = 'rtsp'

    elif camera_type == 'rtsp_ip':
        # RTSP camera added by IP + port + credentials (no URL needed)
        ip_address = request.POST.get('ip_address', '').strip()
        if not ip_address:
            return JsonResponse({'error': 'IP address is required.'}, status=400)
        try:
            port = int(request.POST.get('port', '554').strip() or '554')
        except ValueError:
            return JsonResponse({'error': 'Port must be a number.'}, status=400)
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        protocol = 'rtsp'
        # Duplicate IP+port check
        if Camera.objects.filter(ip_address=ip_address, port=port).exists():
            return JsonResponse({'error': f'A camera at {ip_address}:{port} already exists.'}, status=400)

    elif camera_type in ('droidcam', 'ipwebcam'):
        ip_address = request.POST.get('ip_address', '').strip()
        if not ip_address:
            return JsonResponse({'error': 'IP address is required.'}, status=400)
        port = 4747 if camera_type == 'droidcam' else 8080
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        protocol = 'http'
        # Duplicate IP+port check
        if Camera.objects.filter(ip_address=ip_address, port=port).exists():
            return JsonResponse({'error': f'A camera at {ip_address}:{port} already exists.'}, status=400)
    else:
        return JsonResponse({'error': 'Unknown camera type.'}, status=400)

    logger.info(f"Auto-detecting path for {ip_address}:{port} ({camera_type})")
    detected_path, stream_url = auto_detect_stream_path(ip_address, port, username, password, protocol=protocol)

    if detected_path:
        Camera.objects.create(
            name=name,
            rtsp_url=stream_url,
            ip_address=ip_address,
            port=port,
            username=username,
            password=password,
            stream_path=detected_path,
            is_active=True
        )
        return JsonResponse({'success': True})
    else:
        return JsonResponse({
            'error': f'Could not connect to camera at {ip_address}:{port}. '
                     'Check the device is powered on, reachable on the network, and credentials are correct.'
        }, status=400)
    
@login_required
def edit_camera(request, camera_id):
    if not is_admin(request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    camera = get_object_or_404(Camera, id=camera_id)

    if request.method != 'POST':
        return redirect('admin_dashboard')

    name = request.POST.get('name', '').strip() or camera.name
    rtsp_url_input = request.POST.get('rtsp_url', '').strip()
    force_url = request.POST.get('force_url', '').strip()  # direct override, skip auto-detect

    # Duplicate name check (exclude self)
    if Camera.objects.filter(name__iexact=name).exclude(id=camera_id).exists():
        return JsonResponse({'error': f'A camera named "{name}" already exists.'}, status=400)

    # ── Force URL mode: user provides exact working URL, skip auto-detection ──
    if force_url:
        if Camera.objects.filter(rtsp_url=force_url).exclude(id=camera_id).exists():
            return JsonResponse({'error': 'A camera with this URL already exists.'}, status=400)
        # Validate it actually works
        is_valid, err = validate_rtsp_url(force_url, timeout=5)
        if not is_valid:
            return JsonResponse({
                'error': f'URL does not appear to serve a video stream: {err}. '
                         'If you are sure it works, the camera service may need to be running.'
            }, status=400)
        try:
            parsed = parse_stream_url(force_url)
            camera.name = name
            camera.rtsp_url = force_url
            camera.ip_address = parsed['ip_address']
            camera.port = parsed['port']
            camera.username = parsed['username']
            camera.password = parsed['password']
            camera.stream_path = parsed['stream_path']
            camera.is_active = True
            camera.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': f'Could not parse URL: {str(e)}'}, status=400)

    # ── Auto-detect mode ──────────────────────────────────────────────────────
    if rtsp_url_input:
        if Camera.objects.filter(rtsp_url=rtsp_url_input).exclude(id=camera_id).exists():
            return JsonResponse({'error': 'A camera with this RTSP URL already exists.'}, status=400)
        try:
            parsed = parse_stream_url(rtsp_url_input)
            ip_address = parsed['ip_address']
            port = parsed['port']
            username = parsed['username']
            password = parsed['password']
        except Exception as e:
            return JsonResponse({'error': f'Invalid URL: {str(e)}'}, status=400)
    else:
        ip_address = request.POST.get('ip_address') or camera.ip_address
        port = int(request.POST.get('port') or camera.port)
        username = request.POST.get('username', camera.username)
        password = request.POST.get('password', camera.password)

    logger.info(f"Auto-detecting path for {ip_address}:{port}")
    detected_path, stream_url = auto_detect_stream_path(ip_address, port, username, password, protocol='rtsp')

    if detected_path:
        camera.name = name
        camera.rtsp_url = stream_url
        camera.ip_address = ip_address
        camera.port = port
        camera.username = username
        camera.password = password
        camera.stream_path = detected_path
        camera.is_active = True
        camera.save()
        return JsonResponse({'success': True})
    else:
        return JsonResponse({
            'error': f'Auto-detection failed for {ip_address}:{port}. '
                     'If you know the exact stream URL, use the "Direct URL" field below to set it manually.'
        }, status=400)

@login_required
def delete_camera(request, camera_id):
    """Delete a camera"""
    if not is_admin(request.user):
        return redirect('login')
    if request.method != 'POST':
        return redirect('admin_dashboard')
    camera = get_object_or_404(Camera, id=camera_id)
    camera.delete()
    return redirect('admin_dashboard')



@login_required
def camera_feed(request, camera_id):
    """Proxy the HLS camera feed from the camera service, rewriting segment URLs."""
    import requests as req_lib
    from django.http import HttpResponse, StreamingHttpResponse

    token = request.GET.get('token')
    if not verify_stream_token(token, camera_id):
        return HttpResponse("Unauthorized: Invalid or expired token", status=403)

    filename = request.GET.get('file', 'stream.m3u8')
    is_mobile = request.GET.get('mobile', 'false') == 'true'

    # Permission check
    if is_mobile:
        camera = get_object_or_404(MobileCamera, id=camera_id)
        if not is_admin(request.user) and not MobileCameraPermission.objects.filter(
                mobile_camera=camera, teacher=request.user).exists():
            return HttpResponse("Forbidden", status=403)
        svc_feed_url = f'{CAMERA_SVC}/api/mobile-cameras/{camera_id}/feed/?file={filename}'
    else:
        camera = get_object_or_404(Camera, id=camera_id)
        if not can_view_camera(request.user, camera):
            return HttpResponse("Forbidden", status=403)
        svc_feed_url = f'{CAMERA_SVC}/api/cameras/{camera_id}/feed/?file={filename}'

    try:
        svc_resp = req_lib.get(svc_feed_url, stream=True, timeout=15)
    except req_lib.exceptions.ConnectionError:
        logger.error(f"Camera service not running on :8001 for camera {camera_id}")
        return JsonResponse({'error': 'Camera service not running on port 8001'}, status=503)
    except req_lib.exceptions.RequestException as e:
        logger.error(f"Error proxying feed for camera {camera_id}: {e}")
        return JsonResponse({'error': 'Proxy server unavailable'}, status=503)

    if svc_resp.status_code == 503:
        return JsonResponse({'error': 'Stream not ready yet. FFmpeg is connecting to the camera.'}, status=503)

    if svc_resp.status_code != 200:
        return HttpResponse(status=svc_resp.status_code)

    content_type = svc_resp.headers.get('Content-Type', 'application/octet-stream')

    # ── Rewrite .m3u8 manifest so segment URLs route back through this proxy ──
    # The camera service returns relative segment names (e.g. "segment_042.ts").
    # HLS.js resolves them against the manifest URL, which would produce wrong
    # paths. We rewrite each segment line to an absolute proxy URL with the
    # token so the browser fetches segments through this view.
    if filename.endswith('.m3u8'):
        manifest = svc_resp.content.decode('utf-8', errors='replace')
        proxy_base = request.build_absolute_uri(
            f'/cameras/camera-feed/{camera_id}/'
        )
        mobile_param = '&mobile=true' if is_mobile else ''
        rewritten_lines = []
        for line in manifest.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                # It's a segment filename — rewrite to absolute proxy URL
                seg_url = f'{proxy_base}?file={stripped}&token={token}{mobile_param}'
                rewritten_lines.append(seg_url)
            else:
                rewritten_lines.append(line)
        rewritten = '\n'.join(rewritten_lines) + '\n'
        response = HttpResponse(rewritten, content_type='application/vnd.apple.mpegurl')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Access-Control-Allow-Origin'] = '*'
        return response

    # ── Stream .ts segments straight through ──────────────────────────────────
    django_response = StreamingHttpResponse(
        svc_resp.iter_content(chunk_size=8192),
        content_type=content_type,
    )
    django_response['Access-Control-Allow-Origin'] = '*'
    if 'Cache-Control' in svc_resp.headers:
        django_response['Cache-Control'] = svc_resp.headers['Cache-Control']
    return django_response

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
    
    # Add tokens for each camera
    from .utils import generate_stream_token
    for camera in cameras:
        camera.temp_token = generate_stream_token(request.user, camera.id)
    for camera in mobile_cameras:
        camera.temp_token = generate_stream_token(request.user, camera.id)
    
    # Check if camera service is running
    import requests
    camera_service_running = False
    try:
        response = requests.get('{CAMERA_SVC}/api/cameras/', timeout=2)
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
def view_camera(request, camera_id):
    """View a single camera feed"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    if not can_view_camera(request.user, camera):
        return redirect('login')
    
    from .utils import generate_stream_token
    camera.temp_token = generate_stream_token(request.user, camera.id)
    camera.teacher_count = CameraPermission.objects.filter(camera=camera).count()
    return render(request, 'cameras/view_camera.html', {'camera': camera})

@login_required
def test_camera_connection(request, camera_id):
    """Test camera connection - uses camera service for diagnostics"""
    import requests
    camera = get_object_or_404(Camera, id=camera_id)
    
    try:
        # Use camera service for testing (it has better RTSP handling)
        camera_service_url = f'{CAMERA_SVC}/api/cameras/{camera_id}/test/'
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
def teacher_camera_dashboard(request):
    """Dashboard for teachers to manage their cameras and live classes"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'teacher':
        if not is_admin(request.user):
            return redirect('login')
    
    # 1. Show only assigned cameras (RTSP)
    camera_ids = CameraPermission.objects.filter(teacher=request.user).values_list('camera_id', flat=True)
    assigned_cameras = Camera.objects.filter(id__in=camera_ids, is_active=True)
    
    # 2. Show only assigned mobile cameras
    mobile_camera_ids = MobileCameraPermission.objects.filter(teacher=request.user).values_list('mobile_camera_id', flat=True)
    assigned_mobile_cameras = MobileCamera.objects.filter(id__in=mobile_camera_ids, is_active=True)
    
    # 3. Get active live class (if any)
    active_class = LiveClass.objects.filter(teacher=request.user, status='active').first()
    
    from .utils import generate_stream_token
    # Generate tokens for all cameras
    for cam in assigned_cameras:
        cam.temp_token = generate_stream_token(request.user, cam.id)
    for mcam in assigned_mobile_cameras:
        mcam.temp_token = generate_stream_token(request.user, mcam.id)
    if active_class:
        active_class.temp_token = generate_stream_token(request.user, active_class.stream_key)
    
    # 4. Recent recordings
    recent_recordings = LiveClassRecording.objects.filter(live_class__teacher=request.user).order_by('-created_at')[:5]
    
    context = {
        'cameras': assigned_cameras,
        'mobile_cameras': assigned_mobile_cameras,
        'active_class': active_class,
        'recent_recordings': recent_recordings,
    }
    return render(request, 'cameras/teacher_dashboard.html', context)

@login_required
def start_live_class(request):
    """Initialize a live class and start RTMP listener"""
    if request.method == 'POST':
        title = request.POST.get('title', 'Untitled Live Class')
        import uuid
        stream_key = str(uuid.uuid4())[:8]
        
        # Create LiveClass record
        live_class = LiveClass.objects.create(
            title=title,
            teacher=request.user,
            stream_key=stream_key,
            status='active'
        )
        
        # Notify camera service to start listening
        import requests
        try:
            requests.get(f'{CAMERA_SVC}/api/live-class/start/{stream_key}/', timeout=5)
        except:
            logger.error("Failed to connect to camera service for live class start")
            
        return redirect('teacher_camera_dashboard')
    
    return redirect('teacher_camera_dashboard')

@login_required
def stop_live_class(request, class_id):
    """End a live class and save recording metadata"""
    live_class = get_object_or_404(LiveClass, id=class_id, teacher=request.user)
    live_class.status = 'ended'
    live_class.ended_at = timezone.now()
    live_class.save()
    
    # Notify camera service to stop listening
    import requests
    try:
        requests.get(f'{CAMERA_SVC}/api/live-class/stop/{live_class.stream_key}/', timeout=5)
        
        # Scan for recording chunks
        # In a real setup, we'd wait a few seconds for FFmpeg to flush
        time.sleep(2)
        import os, tempfile
        rec_dir = os.path.join(tempfile.gettempdir(), 'edumi_recordings', f"live_{live_class.stream_key}")
        
        if os.path.exists(rec_dir):
            chunks = [f for f in os.listdir(rec_dir) if f.endswith('.mp4')]
            for i, chunk_file in enumerate(sorted(chunks)):
                file_path = os.path.join(rec_dir, chunk_file)
                file_size = os.path.getsize(file_path)
                LiveClassRecording.objects.get_or_create(
                    live_class=live_class,
                    chunk_index=i,
                    defaults={
                        'file_path': file_path,
                        'file_size_bytes': file_size,
                        'duration_seconds': 60.0 # Assumed based on segment_time
                    }
                )
    except Exception as e:
        logger.error(f"Error finishing live class: {e}")
        
    # Trigger background processing
    from .tasks import process_live_class_recording
    process_live_class_recording.delay(live_class.id)
        
    return redirect('teacher_camera_dashboard')

@login_required
def list_recordings(request):
    """View to list all processed camera recordings with caching and optimization"""
    from django.core.cache import cache
    
    query = request.GET.get('q', '')
    page_number = request.GET.get('page', 1)
    
    # Try to get from cache if no query
    cache_key = f'recordings_list_{request.user.id}_{page_number}'
    if not query:
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
            
    if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'teacher':
        base_recordings = ProcessedVideo.objects.filter(teacher=request.user)
    elif is_admin(request.user):
        base_recordings = ProcessedVideo.objects.all()
    else:
        base_recordings = ProcessedVideo.objects.filter(processing_status='completed')
        
    if query:
        from django.db.models import Q
        base_recordings = base_recordings.filter(
            Q(title__icontains=query) | Q(teacher__username__icontains=query)
        )
        
    recordings_list = base_recordings.order_by('-created_at')
    
    from django.core.paginator import Paginator
    paginator = Paginator(recordings_list, 12)
    recordings = paginator.get_page(page_number)
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        response = render(request, 'cameras/partials/recording_grid.html', {'recordings': recordings})
    else:
        response = render(request, 'cameras/list_recordings.html', {
            'recordings': recordings,
            'query': query
        })
        
    # Cache the result for 5 minutes if no search query
    if not query:
        cache.set(cache_key, response, 300)
        
    return response

@login_required
def view_recording(request, recording_id):
    """Player view for a processed recording with related suggestions"""
    recording = get_object_or_404(ProcessedVideo, id=recording_id)
    
    # Simple recommendation: same teacher or recent
    related = ProcessedVideo.objects.filter(
        processing_status='completed'
    ).exclude(id=recording_id).filter(
        Q(teacher=recording.teacher) | Q(title__icontains=recording.title[:5])
    ).order_by('-created_at')[:6]
    
    return render(request, 'cameras/view_recording.html', {
        'recording': recording,
        'related': related
    })

@login_required
def student_live_class(request, stream_key):
    """Student view for an active live class with token"""
    live_class = get_object_or_404(LiveClass, stream_key=stream_key, status='active')
    
    from .utils import generate_stream_token
    token = generate_stream_token(request.user, stream_key)
    
    return render(request, 'cameras/student_live_class.html', {
        'live_class': live_class,
        'token': token
    })

@login_required
def active_live_classes(request):
    """List all currently active live classes for students to join"""
    live_classes = LiveClass.objects.filter(status='active').order_by('-started_at')
    return render(request, 'cameras/active_live_classes.html', {'live_classes': live_classes})

@login_required
def live_class_feed(request, stream_key):
    """Proxy the live class HLS feed from the camera service with token validation"""
    import requests as req_lib
    from django.http import HttpResponse, StreamingHttpResponse

    token = request.GET.get('token')
    if not verify_stream_token(token, stream_key):
        return HttpResponse("Unauthorized: Invalid or expired token", status=403)

    filename = request.GET.get('file', 'stream.m3u8')
    svc_url = f'{CAMERA_SVC}/api/live/feed/{stream_key}/?file={filename}'

    try:
        svc_resp = req_lib.get(svc_url, stream=True, timeout=10)
    except Exception as e:
        logger.error(f"Error proxying live class feed: {e}")
        return JsonResponse({'error': 'Proxy server unavailable'}, status=503)

    if svc_resp.status_code != 200:
        return HttpResponse(status=svc_resp.status_code)

    content_type = svc_resp.headers.get('Content-Type', 'application/octet-stream')

    if filename.endswith('.m3u8'):
        manifest = svc_resp.content.decode('utf-8', errors='replace')
        proxy_base = request.build_absolute_uri(f'/cameras/live-class/feed/{stream_key}/')
        rewritten_lines = []
        for line in manifest.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                rewritten_lines.append(f'{proxy_base}?file={stripped}&token={token}')
            else:
                rewritten_lines.append(line)
        rewritten = '\n'.join(rewritten_lines) + '\n'
        response = HttpResponse(rewritten, content_type='application/vnd.apple.mpegurl')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Access-Control-Allow-Origin'] = '*'
        return response

    django_response = StreamingHttpResponse(
        svc_resp.iter_content(chunk_size=8192),
        content_type=content_type,
    )
    django_response['Access-Control-Allow-Origin'] = '*'
    if 'Cache-Control' in svc_resp.headers:
        django_response['Cache-Control'] = svc_resp.headers['Cache-Control']
    return django_response

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
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        camera = get_object_or_404(Camera, id=camera_id)
        teacher = get_object_or_404(User, id=teacher_id)
        
        CameraPermission.objects.filter(camera=camera, teacher=teacher).delete()
        
        return JsonResponse({'success': True, 'message': 'Permission revoked successfully'})
        
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def manage_permissions(request, camera_id):
    """Manage camera permissions"""
    if not is_admin(request.user):
        return redirect('login')

    camera = get_object_or_404(Camera, id=camera_id)
    authorized_teachers = camera.get_authorized_teachers()
    authorized_ids = set(authorized_teachers.values_list('id', flat=True))
    all_teachers = User.objects.filter(userprofile__user_type='teacher').order_by('first_name', 'username')
    unauthorized_teachers = all_teachers.exclude(id__in=authorized_ids)

    context = {
        'camera': camera,
        'authorized_teachers': authorized_teachers,
        'unauthorized_teachers': unauthorized_teachers,
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
    
    # Add session status and security tokens to cameras
    from .utils import generate_stream_token
    for camera in rtsp_cameras:
        camera.has_active_session = head_count_manager.is_session_active('rtsp', camera.id)
        camera.camera_type = 'rtsp'
        camera.temp_token = generate_stream_token(request.user, camera.id)
    
    for camera in mobile_cameras:
        camera.has_active_session = head_count_manager.is_session_active('mobile', camera.id)
        camera.camera_type = 'mobile'
        camera.temp_token = generate_stream_token(request.user, camera.id)
    
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
    """Start head counting session for a camera"""
    # Get camera details
    if camera_type == 'rtsp':
        camera = get_object_or_404(Camera, id=camera_id)
        stream_url = camera.get_full_rtsp_url()
        camera_name = camera.name
    elif camera_type == 'mobile':
        camera = get_object_or_404(MobileCamera, id=camera_id)
        stream_url = camera.get_stream_url()
        camera_name = camera.name
    else:
        return JsonResponse({'error': 'Invalid camera type'}, status=400)
    
    # Check permission
    if not can_view_camera(request.user, camera):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Check if already active
    if head_count_manager.is_session_active(camera_type, camera_id):
        return JsonResponse({'error': 'Session already active for this camera'}, status=400)
    
    # Get optional classroom
    classroom_id = request.POST.get('classroom_id') or request.GET.get('classroom_id')
    classroom = None
    if classroom_id:
        try:
            from meetings.models import Classroom
            classroom = Classroom.objects.get(id=classroom_id)
        except:
            pass
    
    # Get interval
    interval = int(request.POST.get('interval', 30))
    interval = max(10, min(300, interval))  # Clamp between 10-300 seconds
    
    # Start session
    success, result = head_count_manager.start_session(
        camera_type=camera_type,
        camera_id=camera_id,
        stream_url=stream_url,
        camera_name=camera_name,
        user=request.user,
        classroom=classroom,
        interval=interval
    )
    
    if success:
        return JsonResponse({'success': True, 'session_id': result})
    else:
        return JsonResponse({'error': result}, status=400)


@login_required
def stop_head_count(request, camera_type, camera_id):
    """Stop head counting session for a camera"""
    success, message = head_count_manager.stop_session(camera_type, camera_id)
    
    if success:
        return JsonResponse({'success': True, 'message': message})
    else:
        return JsonResponse({'error': message}, status=400)


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

@login_required
def test_camera_connection(request, camera_id):
    """AJAX view to test camera connection and update status"""
    if not is_admin(request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
        
    camera = get_object_or_404(Camera, id=camera_id)
    from .utils import validate_rtsp_url
    from .models import CameraLog
    
    is_valid, message = validate_rtsp_url(camera.get_full_rtsp_url())
    
    # Update camera status
    camera.status = 'online' if is_valid else 'offline'
    camera.last_seen = timezone.now() if is_valid else camera.last_seen
    camera.save()
    
    # Log the event
    CameraLog.objects.create(
        camera=camera,
        event_type='connectivity_test',
        message=f"Test result: {message}",
        level='info' if is_valid else 'error'
    )
    
    return JsonResponse({
        'status': camera.status,
        'message': message,
        'last_seen': camera.last_seen.strftime("%Y-%m-%d %H:%M") if camera.last_seen else "Never"
    })

@login_required
def view_camera_logs(request, camera_id):
    """View to see diagnostic logs for a specific camera"""
    if not is_admin(request.user):
        return redirect('teacher_camera_dashboard')
        
    camera = get_object_or_404(Camera, id=camera_id)
    logs = CameraLog.objects.filter(camera=camera).order_by('-timestamp')[:100]
    return render(request, 'cameras/diagnostics.html', {'camera': camera, 'logs': logs})

@login_required
def simulate_load(request):
    """Admin tool to simulate multiple streams for load testing"""
    if not is_admin(request.user):
        return redirect('teacher_camera_dashboard')
        
    if request.method == 'POST':
        count = int(request.POST.get('count', 5))
        test_url = "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4"
        
        import requests
        results = []
        for i in range(count):
            try:
                resp = requests.post('{CAMERA_SVC}/api/cameras/start/', json={
                    'camera_id': f'load_test_{i}',
                    'url': test_url
                })
                results.append(f"Stream {i}: {resp.status_code}")
            except Exception as e:
                results.append(f"Stream {i}: Failed - {str(e)}")
                
        return render(request, 'cameras/load_test_results.html', {'results': results})
        
    return render(request, 'cameras/simulate_load.html')


