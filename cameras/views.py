import threading
import time
import logging
from typing import Optional
from urllib.parse import urlparse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.db.models import Avg, Max, Min, Count
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Camera, CameraPermission, HeadCountLog, HeadCountSession
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
    
    cameras = Camera.objects.all()
    teachers = User.objects.filter(userprofile__user_type='teacher')
    
    # Get permissions for each camera
    camera_permissions = {}
    for camera in cameras:
        camera_permissions[camera.id] = camera.get_authorized_teachers()
    
    context = {
        'cameras': cameras,
        'teachers': teachers,
        'camera_permissions': camera_permissions,
    }
    return render(request, 'cameras/admin_dashboard.html', context)

@login_required
def add_camera(request):
    if not is_admin(request.user):
        return redirect('login')
    
    if request.method == 'POST':
        # Check if RTSP URL is provided
        rtsp_url_input = request.POST.get('rtsp_url', '').strip()
        
        if rtsp_url_input:
            # Parse RTSP URL to extract components (ignore the path, we'll auto-detect)
            try:
                parsed = parse_rtsp_url(rtsp_url_input)
                name = request.POST.get('name') or f"Camera {parsed['ip_address']}"
                ip_address = parsed['ip_address']
                port = parsed['port']
                username = parsed['username']
                password = parsed['password']
            except Exception as e:
                return render(request, 'cameras/add_camera.html', {
                    'error': f'Invalid RTSP URL format: {str(e)}'
                })
        else:
            # Use manual input
            name = request.POST.get('name')
            ip_address = request.POST.get('ip_address')
            port = int(request.POST.get('port', 554))
            username = request.POST.get('username', '')
            password = request.POST.get('password', '')
        
        # ALWAYS auto-detect the correct RTSP path
        logger.info(f"Auto-detecting RTSP path for {ip_address}:{port}")
        detected_path, rtsp_url = test_rtsp_paths(ip_address, port, username, password)
        
        if detected_path:
            logger.info(f"Successfully detected path: {detected_path}")
            Camera.objects.create(
                name=name,
                rtsp_url=rtsp_url,
                ip_address=ip_address,
                port=port,
                username=username,
                password=password,
                stream_path=detected_path,
                is_active=True
            )
            return redirect('admin_dashboard')
        else:
            # If auto-detection fails, save with default path but mark as inactive
            logger.warning(f"Could not auto-detect path for {ip_address}:{port}")
            if username and password:
                from urllib.parse import quote
                safe_user = quote(username)
                safe_pass = quote(password)
                rtsp_url = f"rtsp://{safe_user}:{safe_pass}@{ip_address}:{port}/stream"
            else:
                rtsp_url = f"rtsp://{ip_address}:{port}/stream"
            
            Camera.objects.create(
                name=name,
                rtsp_url=rtsp_url,
                ip_address=ip_address,
                port=port,
                username=username,
                password=password,
                stream_path='/stream',
                is_active=False  # Mark as inactive if path not detected
            )
            return render(request, 'cameras/add_camera.html', {
                'error': 'Could not auto-detect camera path. Camera saved but marked as inactive. Please verify camera is online and accessible.'
            })
    
    return render(request, 'cameras/add_camera.html')

@login_required
def delete_camera(request, camera_id):
    """Delete a camera and stop its streamer"""
    if not is_admin(request.user):
        return redirect('login')
    
    camera = get_object_or_404(Camera, id=camera_id)
    camera.delete()
    return redirect('admin_dashboard')


class CameraStreamer:
    """Non-blocking camera streamer with automatic reconnection"""
    
    def __init__(self, camera_id, rtsp_url):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame: Optional[bytes] = None
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.last_access = time.time()
        self.connection_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2

    def start(self):
        """Start the background streaming thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._update, daemon=True)
            self.thread.start()
            logger.info(f"Started streamer for camera {self.camera_id}")

    def stop(self):
        """Stop the streaming thread"""
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        logger.info(f"Stopped streamer for camera {self.camera_id}")

    def _connect_camera(self):
        """Attempt to connect to the camera"""
        import cv2
        try:
            import os
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    self.connection_attempts = 0
                    logger.info(f"Connected to camera {self.camera_id}")
                    return cap
                cap.release()
            return None
        except Exception as e:
            logger.error(f"Error connecting camera {self.camera_id}: {e}")
            return None

    def _update(self):
        """Background thread to continuously read frames"""
        try:
            while self.running:
                # Stop if inactive for too long
                if time.time() - self.last_access > 90:
                    logger.info(f"Stopping camera {self.camera_id} due to inactivity")
                    break

                # Try to connect if not connected
                if self.cap is None:
                    if self.connection_attempts >= self.max_reconnect_attempts:
                        logger.warning(f"Camera {self.camera_id} is OFFLINE. Stopping live streamer.")
                        break
                    
                    self.connection_attempts += 1
                    logger.info(f"Connecting to camera {self.camera_id} (attempt {self.connection_attempts})")
                    self.cap = self._connect_camera()
                    
                    if self.cap is None:
                        time.sleep(self.reconnect_delay)
                        continue

                # Read frame from camera
                try:
                    import cv2
                    ret, frame = self.cap.read()
                    
                    if ret and frame is not None:
                        # PROCESS TRACKING on the live feed
                        try:
                            head_count, detections, annotated, avg_conf, tracked_persons = \
                                head_count_manager.detector.detect_heads(frame)
                            frame = annotated
                        except Exception as e:
                            logger.error(f"Tracking error in streamer: {e}")

                        # GPU-accelerated JPEG encode via OpenCL if available
                        try:
                            import cv2 as _cv2
                            if _cv2.ocl.useOpenCL():
                                umat = _cv2.UMat(frame)
                                ret, jpeg = _cv2.imencode('.jpg', umat,
                                    [_cv2.IMWRITE_JPEG_QUALITY, 75])
                            else:
                                ret, jpeg = _cv2.imencode('.jpg', frame,
                                    [_cv2.IMWRITE_JPEG_QUALITY, 75])
                        except Exception:
                            ret, jpeg = cv2.imencode('.jpg', frame,
                                [cv2.IMWRITE_JPEG_QUALITY, 75])

                        if ret:
                            with self.lock:
                                self.frame = jpeg.tobytes()
                        
                        # No fixed delay here - it helps drain the camera buffer faster
                        
                    else:
                        # Frame read failed - reconnect
                        logger.warning(f"Failed to read frame from camera {self.camera_id}, reconnecting...")
                        if self.cap is not None:
                            self.cap.release()
                        self.cap = None
                        time.sleep(self.reconnect_delay)
                        
                except Exception as e:
                    logger.error(f"Error reading from camera {self.camera_id}: {e}")
                    if self.cap is not None:
                        self.cap.release()
                    self.cap = None
                    time.sleep(self.reconnect_delay)
        finally:
            self.running = False
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            logger.info(f"Background thread stopped for camera {self.camera_id}")

    def get_frame(self):
        """Get the latest frame (thread-safe)"""
        self.last_access = time.time()
        with self.lock:
            return self.frame

class CameraManager:
    """Global manager for camera streamers - prevents duplicate connections"""
    
    _lock = threading.Lock()
    _streamers = {}

    @classmethod
    def get_streamer(cls, camera_id, rtsp_url):
        """Get or create a streamer for the given camera"""
        with cls._lock:
            try:
                camera = Camera.objects.get(id=camera_id)
                full_url = camera.get_full_rtsp_url()
                if camera_id not in cls._streamers or not cls._streamers[camera_id].running:
                    logger.info(f"Creating new streamer for camera {camera_id}")
                    streamer = CameraStreamer(camera_id, full_url)
                    streamer.start()
                    cls._streamers[camera_id] = streamer
                return cls._streamers[camera_id]
            except Camera.DoesNotExist:
                logger.warning(f"Camera {camera_id} not found, cannot create streamer.")
                return None
    
    @classmethod
    def stop_streamer(cls, camera_id):
        """Stop a specific camera streamer"""
        with cls._lock:
            if camera_id in cls._streamers:
                cls._streamers[camera_id].stop()
                del cls._streamers[camera_id]
    
    @classmethod
    def stop_all(cls):
        """Stop all camera streamers"""
        with cls._lock:
            for streamer in cls._streamers.values():
                streamer.stop()
            cls._streamers.clear()

@login_required
def camera_feed(request, camera_id):
    """
    Directly serve the camera feed with real-time tracking annotations.
    Uses the internal CameraManager and Streamer for high performance.
    """
    camera = get_object_or_404(Camera, id=camera_id)
    
    # Check permission
    if not can_view_camera(request.user, camera):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    rtsp_url = camera.get_full_rtsp_url()
    streamer = CameraManager.get_streamer(camera.id, rtsp_url)
    
    def generate():
        last_frame = None
        while True:
            try:
                frame = streamer.get_frame()
                if frame and frame != last_frame:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                    last_frame = frame
                else:
                    time.sleep(0.01)
            except GeneratorExit:
                logger.info(f"Client disconnected from camera feed {camera_id}")
                break
            except Exception as e:
                logger.error(f"Error in camera feed {camera_id}: {e}")
                time.sleep(0.1)
                
    response = StreamingHttpResponse(
        generate(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Accel-Buffering'] = 'no'
    return response

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
def view_camera(request, camera_id):
    """View a single camera feed"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    if not can_view_camera(request.user, camera):
        return redirect('login')
    
    return render(request, 'cameras/view_camera.html', {'camera': camera})

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
