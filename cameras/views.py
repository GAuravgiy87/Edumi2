import cv2
import threading
import time
import logging
from typing import Optional
from urllib.parse import urlparse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse
from django.contrib.auth.models import User
from .models import Camera, CameraPermission
from mobile_cameras.models import MobileCamera, MobileCameraPermission

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
    
    for path in common_paths:
        if username and password:
            rtsp_url = f"rtsp://{username}:{password}@{ip}:{port}{path}"
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
    """Parse an RTSP URL to extract components"""
    parsed = urlparse(url)
    
    # Extract username and password
    username = parsed.username or ''
    password = parsed.password or ''
    
    # Extract IP and port
    ip_address = parsed.hostname
    port = parsed.port or 554  # Default RTSP port
    
    # Extract path
    stream_path = parsed.path or '/stream'
    
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
                rtsp_url = f"rtsp://{username}:{password}@{ip_address}:{port}/stream"
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
        try:
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
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
        while self.running:
            # Stop if inactive for too long
            if time.time() - self.last_access > 90:
                logger.info(f"Stopping camera {self.camera_id} due to inactivity")
                break

            # Try to connect if not connected
            if self.cap is None:
                if self.connection_attempts >= self.max_reconnect_attempts:
                    time.sleep(10)  # Wait longer before trying again
                    self.connection_attempts = 0
                    continue
                
                self.connection_attempts += 1
                logger.info(f"Connecting to camera {self.camera_id} (attempt {self.connection_attempts})")
                self.cap = self._connect_camera()
                
                if self.cap is None:
                    time.sleep(self.reconnect_delay)
                    continue

            # Read frame from camera
            try:
                ret, frame = self.cap.read()
                
                if ret and frame is not None:
                    # Resize for efficient streaming
                    frame = cv2.resize(frame, (960, 540))
                    
                    # Encode to JPEG with compression
                    ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    
                    if ret:
                        with self.lock:
                            self.frame = jpeg.tobytes()
                    
                    # Small delay to control frame rate (~25 FPS)
                    time.sleep(0.04)
                    
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
        
        # Cleanup
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
            if camera_id not in cls._streamers or not cls._streamers[camera_id].running:
                logger.info(f"Creating new streamer for camera {camera_id}")
                streamer = CameraStreamer(camera_id, rtsp_url)
                streamer.start()
                cls._streamers[camera_id] = streamer
            return cls._streamers[camera_id]
    
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

def camera_feed(request, camera_id):
    """Proxy camera feed from camera service on port 8001"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    # Check permission
    if not can_view_camera(request.user, camera):
        return JsonResponse({'error': 'You do not have permission to view this camera'}, status=403)
    
    import requests
    
    def generate_frames():
        """Proxy frames from camera service"""
        try:
            camera_service_url = f'http://localhost:8001/api/cameras/{camera_id}/feed/'
            logger.info(f"Proxying camera {camera_id} from {camera_service_url}")
            
            response = requests.get(camera_service_url, stream=True, timeout=None)
            response.raise_for_status()
            
            # Stream the response directly
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
                    
        except requests.exceptions.ConnectionError as e:
            # Camera service is not running
            logger.error(f"Camera service not running on port 8001: {e}")
            error_msg = (
                b'--frame\r\n'
                b'Content-Type: text/plain\r\n\r\n'
                b'ERROR: Camera service not running on port 8001.\r\n'
            )
            yield error_msg
        except requests.exceptions.RequestException as e:
            logger.error(f"Error proxying camera {camera_id}: {e}")
            error_msg = (
                b'--frame\r\n'
                b'Content-Type: text/plain\r\n\r\n'
                b'ERROR: ' + str(e).encode() + b'\r\n'
            )
            yield error_msg
        except GeneratorExit:
            logger.info(f"Client disconnected from camera {camera_id}")
        except Exception as e:
            logger.error(f"Unexpected error proxying camera {camera_id}: {e}")


    response = StreamingHttpResponse(
        generate_frames(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Accel-Buffering'] = 'no'
    response['Connection'] = 'keep-alive'
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
    """Test camera connection"""
    camera = get_object_or_404(Camera, id=camera_id)
    
    try:
        cap = cv2.VideoCapture(camera.rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
        
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            
            if ret and frame is not None:
                return JsonResponse({
                    'status': 'success',
                    'message': f'Camera is accessible. Frame size: {frame.shape}'
                })
            return JsonResponse({
                'status': 'error',
                'message': 'Camera opened but could not read frames'
            })
        
        cap.release()
        return JsonResponse({
            'status': 'error',
            'message': 'Could not open camera connection'
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
