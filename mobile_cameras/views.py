import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse
from django.contrib.auth.models import User
from .models import MobileCamera, MobileCameraPermission

logger = logging.getLogger('mobile_cameras')


def is_admin(user):
    """Check if user is admin"""
    if user.is_authenticated:
        if user.is_superuser:
            return True
    return False


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


def test_mobile_camera_paths(ip, port, username, password):
    """Test common mobile camera paths to find the working one"""
    import requests
    from requests.auth import HTTPBasicAuth
    
    common_paths = [
        '/video',           # DroidCam and IP Webcam both support this
        '/mjpegfeed',       # DroidCam alternative (but /video works better)
        '/videofeed',       # Alternative
        '/cam_1.mjpg',      # Some apps
        '/stream',          # Generic
        '/video.mjpg',      # MJPEG format
        '/video.cgi',       # CGI format
        '/',                # Root path
    ]
    
    for path in common_paths:
        if username and password:
            url = f"http://{username}:{password}@{ip}:{port}{path}"
            auth = HTTPBasicAuth(username, password)
        else:
            url = f"http://{ip}:{port}{path}"
            auth = None
        
        try:
            response = requests.get(url, timeout=3, stream=True, auth=auth)
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'image' in content_type or 'video' in content_type or 'multipart' in content_type:
                    return path, url
        except Exception:
            continue
    
    return None, None


def parse_camera_url(url):
    """Parse a camera URL to extract components"""
    from urllib.parse import urlparse
    
    parsed = urlparse(url)
    
    # Extract username and password
    username = parsed.username or ''
    password = parsed.password or ''
    
    # Extract IP and port
    ip_address = parsed.hostname
    port = parsed.port
    
    # Extract path
    stream_path = parsed.path or '/'
    
    # Determine camera type based on URL scheme and path
    camera_type = 'other'
    if parsed.scheme == 'rtsp':
        camera_type = 'other'  # RTSP cameras should use the cameras app
    elif '/video' in stream_path:
        camera_type = 'ip_webcam'
    elif '/mjpegfeed' in stream_path:
        camera_type = 'droidcam'
    
    # Set default port if not specified
    if not port:
        if parsed.scheme == 'rtsp':
            port = 554
        else:
            port = 8080
    
    return {
        'ip_address': ip_address,
        'port': port,
        'username': username,
        'password': password,
        'stream_path': stream_path,
        'camera_type': camera_type
    }


@login_required
def add_mobile_camera(request):
    """Add a new mobile camera"""
    if not is_admin(request.user):
        return redirect('login')
    
    if request.method == 'POST':
        # Check if URL is provided
        camera_url = request.POST.get('camera_url', '').strip()
        
        if camera_url:
            # Parse URL to extract components (ignore the path, we'll auto-detect)
            try:
                parsed = parse_camera_url(camera_url)
                name = request.POST.get('name') or f"Camera {parsed['ip_address']}"
                camera_type = parsed['camera_type']
                ip_address = parsed['ip_address']
                port = parsed['port']
                username = parsed['username']
                password = parsed['password']
            except Exception as e:
                return render(request, 'mobile_cameras/add_camera.html', {
                    'error': f'Invalid URL format: {str(e)}'
                })
        else:
            # Use manual input
            name = request.POST.get('name')
            camera_type = request.POST.get('camera_type')
            ip_address = request.POST.get('ip_address')
            port = int(request.POST.get('port', 8080))
            username = request.POST.get('username', '')
            password = request.POST.get('password', '')
        
        # ALWAYS auto-detect the path
        detected_path, detected_url = test_mobile_camera_paths(ip_address, port, username, password)
        
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
    """Proxy mobile camera feed from camera service on port 8001"""
    mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
    
    # Check permission
    if not can_view_mobile_camera(request.user, mobile_camera):
        return JsonResponse({'error': 'You do not have permission to view this camera'}, status=403)
    
    import requests
    
    def generate_frames():
        """Proxy frames from camera service"""
        try:
            camera_service_url = f'http://localhost:8001/api/mobile-cameras/{mobile_camera_id}/feed/'
            response = requests.get(camera_service_url, stream=True, timeout=30)
            
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk
                    
        except requests.exceptions.ConnectionError:
            logger.error(f"Camera service not running on port 8001")
            error_msg = (
                b'--frame\r\n'
                b'Content-Type: text/plain\r\n\r\n'
                b'ERROR: Camera service not running on port 8001.\r\n'
            )
            yield error_msg
        except requests.exceptions.RequestException as e:
            logger.error(f"Error proxying mobile camera {mobile_camera_id}: {e}")
        except GeneratorExit:
            logger.info(f"Client disconnected from mobile camera {mobile_camera_id}")

    response = StreamingHttpResponse(
        generate_frames(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


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
    
    import requests
    
    try:
        url = mobile_camera.get_stream_url()
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            return JsonResponse({
                'status': 'success',
                'message': f'Mobile camera is accessible',
                'url': url
            })
        return JsonResponse({
            'status': 'error',
            'message': f'HTTP {response.status_code}'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        })


@login_required
def mobile_camera_headcount_feed(request, mobile_camera_id):
    """Stream mobile camera feed with optimized face detection"""
    mobile_camera = get_object_or_404(MobileCamera, id=mobile_camera_id)
    
    # Check permission
    if not can_view_mobile_camera(request.user, mobile_camera):
        return JsonResponse({'error': 'You do not have permission to view this camera'}, status=403)
    
    import requests
    import cv2
    import numpy as np
    import time
    from collections import deque
    
    # Load face cascade once
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    # Add motion detection
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=25, detectShadows=True)
    
    def generate_frames():
        """Stream frames with fast face detection"""
        try:
            url = mobile_camera.get_stream_url()
            logger.info(f"Connecting to mobile camera headcount feed: {url}")
            
            response = requests.get(url, stream=True, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Failed to connect to mobile camera: HTTP {response.status_code}")
                yield (b'--frame\r\n'
                       b'Content-Type: text/plain\r\n\r\n'
                       b'ERROR: Cannot connect to mobile camera\r\n')
                return
            
            bytes_buffer = bytes()
            frame_count = 0
            last_faces = []
            last_count = 0
            detection_history = deque(maxlen=5)
            
            for chunk in response.iter_content(chunk_size=16384):  # Larger chunks
                bytes_buffer += chunk
                
                while True:
                    a = bytes_buffer.find(b'\xff\xd8')
                    b = bytes_buffer.find(b'\xff\xd9')
                    
                    if a == -1 or b == -1 or b <= a:
                        break
                    
                    jpg = bytes_buffer[a:b+2]
                    bytes_buffer = bytes_buffer[b+2:]
                    
                    try:
                        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            frame_count += 1
                            display_frame = frame.copy()
                            
                            # Run detection every 3rd frame
                            if frame_count % 3 == 0:
                                try:
                                    small_frame = cv2.resize(frame, (320, 240))
                                    gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
                                    
                                    # Face detection
                                    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=3, minSize=(30, 30))
                                    
                                    # Motion detection
                                    fg_mask = bg_subtractor.apply(small_frame)
                                    _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
                                    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                                    
                                    scale_x = frame.shape[1] / 320
                                    scale_y = frame.shape[0] / 240
                                    
                                    current_detections = []
                                    # Add faces
                                    for (x, y, w, h) in faces:
                                        current_detections.append({
                                            'bbox': (int(x*scale_x), int(y*scale_y), int(w*scale_x), int(h*scale_y)),
                                            'type': 'face'
                                        })
                                    
                                    # Add motion (if not overlapping with faces)
                                    for contour in contours:
                                        if cv2.contourArea(contour) > 300:
                                            mx, my, mw, mh = cv2.boundingRect(contour)
                                            # Simple overlap check would go here, but for mobile we'll show all significant motion
                                            current_detections.append({
                                                'bbox': (int(mx*scale_x), int(my*scale_y), int(mw*scale_x), int(mh*scale_y)),
                                                'type': 'motion'
                                            })
                                    
                                    # Detect heads
                                    head_count, detections, annotated, avg_conf, tracked_persons = \
                                        head_count_manager.detector.detect_heads(frame, track_movement=True)
                                    frame = annotated
                                    
                                    last_detections = detections # Assuming 'detections' from detect_heads is in the desired format
                                    raw_count = head_count # Use the head_count from the new detector
                                    detection_history.append(raw_count)
                                    last_count = int(np.median(list(detection_history))) if detection_history else raw_count
                                    
                                except Exception as e:
                                    logger.error(f"Detection error: {e}")
                            
                            # Draw detections
                            for det in last_detections:
                                x, y, w, h = det['bbox']
                                color = (0, 255, 0) if det['type'] == 'face' else (0, 255, 255) # Green for face, Yellow for motion
                                cv2.rectangle(display_frame, (x, y), (x + w, y + h), color, 2)
                            
                            # Optimized UI Overlay
                            overlay = display_frame.copy()
                            cv2.rectangle(overlay, (0, 0), (220, 50), (0, 0, 0), -1)
                            cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)
                            
                            cv2.putText(display_frame, f"HEADS: {last_count}", (10, 35),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                            
                            # LIVE indicator
                            cv2.circle(display_frame, (frame.shape[1] - 25, 25), 8, (0, 0, 255), -1)
                            cv2.putText(display_frame, "LIVE", (frame.shape[1] - 75, 32),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                            
                            # Fast encoding
                            ret, jpeg = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                            if ret:
                                yield (b'--frame\r\n'
                                       b'Content-Type: image/jpeg\r\n'
                                       b'\r\n' + jpeg.tobytes() + b'\r\n')
                    except Exception as e:
                        continue
                        
        except Exception as e:
            logger.error(f"Headcount feed error: {e}")
            yield (b'--frame\r\n'
                   b'Content-Type: text/plain\r\n\r\n'
                   b'ERROR: Stream error\r\n')
    
    response = StreamingHttpResponse(
        generate_frames(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


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
