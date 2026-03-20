"""Camera streaming views - isolated service"""
import cv2
import threading
import time
import logging
import os
from typing import Optional
from django.http import StreamingHttpResponse, JsonResponse
import sys
from pathlib import Path

# Set FFmpeg environment variables for better RTSP handling
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'

# Import Camera model from main project
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from cameras.models import Camera
try:
    from cameras.head_count_service import head_count_manager
except ImportError:
    # If not in path, try adding it again carefully
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from cameras.head_count_service import head_count_manager

logger = logging.getLogger('camera_api')

# RTSP Connection Settings
RTSP_OPEN_TIMEOUT = 4000  # 4 seconds
RTSP_READ_TIMEOUT = 4000  # 4 seconds
RTSP_RECONNECT_DELAY = 2   # 2 seconds
RTSP_MAX_RECONNECT = 10    # Max reconnection attempts before giving up

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
        self.last_frame: Optional[np.ndarray] = None  # Store raw frame for adaptive encoding
        self.connection_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._update, daemon=True)
            self.thread.start()
            logger.info(f"Started streamer for camera {self.camera_id}")

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        logger.info(f"Stopped streamer for camera {self.camera_id}")

    def _connect_camera(self):
        """Connect to RTSP camera with multiple transport protocols"""
        # Try different RTSP transport protocols
        transport_options = [
            ('tcp', 'rtsp_transport;tcp'),      # TCP - most reliable
            ('udp', 'rtsp_transport;udp'),      # UDP - faster but less reliable
            ('http', 'rtsp_transport;http'),    # HTTP tunneling
        ]
        
        for transport_name, transport_opt in transport_options:
            cap = None  # Initialize cap for this iteration
            try:
                logger.info(f"Trying {transport_name.upper()} transport for camera {self.camera_id}")
                
                # Set environment variable for this attempt
                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = transport_opt
                
                cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, RTSP_OPEN_TIMEOUT)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, RTSP_READ_TIMEOUT)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FPS, 30)  # Request 30 FPS
                
                if cap.isOpened():
                    logger.info(f"Connection opened with {transport_name.upper()}, attempting to read frame...")
                    
                    # Try to read multiple frames (some cameras need a few frames to start)
                    for attempt in range(5):
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            self.connection_attempts = 0
                            logger.info(f"Successfully connected to camera {self.camera_id} via {transport_name.upper()} (attempt {attempt + 1})")
                            logger.info(f"Frame size: {frame.shape[1]}x{frame.shape[0]}")
                            return cap
                        time.sleep(0.2)
                    
                    logger.warning(f"{transport_name.upper()}: Opened but could not read frames")
                    cap.release()
                else:
                    logger.warning(f"{transport_name.upper()}: Failed to open connection")
                    
            except Exception as e:
                logger.error(f"{transport_name.upper()} transport error for camera {self.camera_id}: {e}")
                if cap is not None:
                    try:
                        cap.release()
                    except:
                        pass
        
        # If all transports fail, try without specific transport (default)
        cap = None
        try:
            logger.info(f"Trying default connection for camera {self.camera_id}")
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, RTSP_OPEN_TIMEOUT)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, RTSP_READ_TIMEOUT)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if cap.isOpened():
                for attempt in range(5):
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        self.connection_attempts = 0
                        logger.info(f"Connected to camera {self.camera_id} via default (attempt {attempt + 1})")
                        return cap
                    time.sleep(0.2)
                cap.release()
        except Exception as e:
            logger.error(f"Default connection error: {e}")
            if cap is not None:
                try:
                    cap.release()
                except:
                    pass
            
        return None

    def _update(self):
        while self.running:
            if time.time() - self.last_access > 90:
                logger.info(f"Stopping camera {self.camera_id} due to inactivity")
                break

            if self.cap is None:
                if self.connection_attempts >= RTSP_MAX_RECONNECT:
                    logger.error(f"Max reconnection attempts reached for camera {self.camera_id}")
                    time.sleep(10)
                    self.connection_attempts = 0
                    continue
                
                self.connection_attempts += 1
                logger.info(f"Reconnection attempt {self.connection_attempts}/{RTSP_MAX_RECONNECT} for camera {self.camera_id}")
                self.cap = self._connect_camera()
                if self.cap is None:
                    time.sleep(RTSP_RECONNECT_DELAY)
                    continue

            try:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    self.connection_attempts = 0  # Reset on successful frame
                    # Detect heads and draw annotations
                    try:
                        # Use the head_count_manager detector
                        # We pass track_movement=True as requested for "always track everything"
                        count, detections, annotated, avg_conf, tracked = \
                            head_count_manager.detector.detect_heads(frame, track_movement=True)
                        frame_to_stream = annotated
                    except Exception as e:
                        logger.error(f"Tracking error in microservice: {e}")
                        frame_to_stream = frame

                    # Store for adaptive encoding if needed
                    with self.lock:
                        self.last_frame = frame_to_stream.copy()
                    
                    # Store a default 'med' frame as fallback
                    frame_med = cv2.resize(frame_to_stream, (640, 360), interpolation=cv2.INTER_NEAREST)
                    ret_med, jpeg = cv2.imencode('.jpg', frame_med, [cv2.IMWRITE_JPEG_QUALITY, 60])
                    
                    if ret_med:
                        with self.lock:
                            self.frame = jpeg.tobytes()
                    
                    time.sleep(0.01)  # High capture rate, streaming will skip
                else:
                    logger.warning(f"Failed to read frame from camera {self.camera_id}, reconnecting...")
                    if self.cap is not None:
                        self.cap.release()
                    self.cap = None
                    time.sleep(RTSP_RECONNECT_DELAY)
            except Exception as e:
                logger.error(f"Error reading camera {self.camera_id}: {e}")
                if self.cap is not None:
                    try:
                        self.cap.release()
                    except:
                        pass
                self.cap = None
                time.sleep(RTSP_RECONNECT_DELAY)
        
        if self.cap is not None:
            self.cap.release()

    def get_frame(self):
        self.last_access = time.time()
        with self.lock:
            return self.frame

    def get_adaptive_frame(self, quality_level='med'):
        """Encodes frame based on requested quality level"""
        self.last_access = time.time()
        with self.lock:
            if self.last_frame is None:
                return self.frame
            frame = self.last_frame.copy()

        configs = {
            'high': {'res': (1280, 720), 'quality': 85},
            'med': {'res': (640, 360), 'quality': 60},
            'low': {'res': (480, 270), 'quality': 30}
        }
        config = configs.get(quality_level, configs['med'])
        
        try:
            frame = cv2.resize(frame, config['res'], interpolation=cv2.INTER_NEAREST)
            ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, config['quality']])
            return jpeg.tobytes() if ret else self.frame
        except Exception:
            return self.frame

class CameraManager:
    _lock = threading.Lock()
    _streamers = {}

    @classmethod
    def get_streamer(cls, camera_id, rtsp_url):
        with cls._lock:
            # Create new streamer if not exists or if existing one stopped
            if camera_id not in cls._streamers:
                logger.info(f"Creating new streamer for camera {camera_id}")
                streamer = CameraStreamer(camera_id, rtsp_url)
                streamer.start()
                cls._streamers[camera_id] = streamer
            elif not cls._streamers[camera_id].running:
                logger.info(f"Restarting stopped streamer for camera {camera_id}")
                streamer = CameraStreamer(camera_id, rtsp_url)
                streamer.start()
                cls._streamers[camera_id] = streamer
            return cls._streamers[camera_id]
    
    @classmethod
    def stop_streamer(cls, camera_id):
        with cls._lock:
            if camera_id in cls._streamers:
                cls._streamers[camera_id].stop()
                del cls._streamers[camera_id]

camera_manager = CameraManager()

def list_cameras(request):
    """List all active cameras"""
    try:
        cameras = Camera.objects.filter(is_active=True).values('id', 'name', 'is_active')
        return JsonResponse({'cameras': list(cameras)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def camera_feed(request, camera_id):
    """Stream camera feed with adaptive bitrate support"""
    quality = request.GET.get('q', 'med')
    
    try:
        camera = Camera.objects.get(id=camera_id)
        logger.info(f"=== FEED REQUEST for camera {camera_id} ===")
        full_url = camera.get_full_rtsp_url()
        logger.info(f"RTSP URL (Quoted): {full_url[:30]}...")
        streamer = camera_manager.get_streamer(camera.id, full_url)
        logger.info(f"Streamer running: {streamer.running}")
        
        def generate_frames():
            # Throttle based on quality
            throttles = {'high': 0.033, 'med': 0.05, 'low': 0.1}
            delay = throttles.get(quality, 0.05)
            
            # Wait for first frame (up to 30 seconds)
            wait_count = 0
            max_wait = 300  # 30 seconds at 0.1s intervals
            while streamer.get_frame() is None and wait_count < max_wait:
                time.sleep(0.1)
                wait_count += 1
                if wait_count % 10 == 0:
                    logger.info(f"Waiting for first frame from camera {camera_id}... ({wait_count/10:.0f}s)")
            
            first_frame = streamer.get_frame()
            if first_frame is None:
                logger.error(f"No frame received from camera {camera_id} after 30 seconds")
                yield (b'--frame\r\n'
                       b'Content-Type: text/plain\r\n\r\n'
                       b'ERROR: Could not get video frame from camera.\r\n'
                       b'Check RTSP URL and credentials.\r\n')
                return
            
            logger.info(f"=== STREAMING STARTED for camera {camera_id} ===")
            frame_count = 0
            
            try:
                while True:
                    frame = streamer.get_adaptive_frame(quality)
                    if frame:
                        frame_count += 1
                        if frame_count % 100 == 0:
                            logger.info(f"Camera {camera_id}: streamed {frame_count} frames")
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n'
                               b'Content-Length: ' + str(len(frame)).encode() + b'\r\n'
                               b'\r\n' + frame + b'\r\n')
                        time.sleep(delay)
                    else:
                        # Frame lost, wait briefly
                        time.sleep(0.01)
            except GeneratorExit:
                logger.info(f"Client disconnected from camera {camera_id} after {frame_count} frames")
            except Exception as e:
                logger.error(f"Error in streaming loop for camera {camera_id}: {e}")

        response = StreamingHttpResponse(
            generate_frames(),
            content_type='multipart/x-mixed-replace; boundary=frame'
        )
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['X-Accel-Buffering'] = 'no'
        return response
    except Camera.DoesNotExist:
        logger.error(f"Camera {camera_id} not found")
        return JsonResponse({'error': 'Camera not found'}, status=404)

def test_camera(request, camera_id):
    """Test camera connection with detailed diagnostics"""
    import subprocess
    
    try:
        camera = Camera.objects.get(id=camera_id)
        results = []
        
        # Log the RTSP URL (hide password)
        safe_url = camera.rtsp_url
        if '@' in safe_url:
            parts = safe_url.split('@')
            safe_url = parts[0].rsplit(':', 1)[0] + ':***@' + parts[1]
        logger.info(f"Testing camera {camera_id}: {safe_url}")
        
        # Check if FFmpeg is available
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
            ffmpeg_available = True
            ffmpeg_version = result.stdout.split('\n')[0] if result.stdout else 'Unknown'
        except:
            ffmpeg_available = False
            ffmpeg_version = 'Not installed'
        
        # Use encoded URL for all tests
        full_url = camera.get_full_rtsp_url()
        
        # Method 1: OpenCV with TCP
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'
        cap = cv2.VideoCapture(full_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
        
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                results.append({
                    'method': 'OpenCV TCP',
                    'status': 'success',
                    'frame_size': f"{frame.shape[1]}x{frame.shape[0]}"
                })
            else:
                results.append({'method': 'OpenCV TCP', 'status': 'opened_but_no_frame'})
            cap.release()
        else:
            results.append({'method': 'OpenCV TCP', 'status': 'failed_to_open'})
        
        # Method 2: OpenCV with UDP
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;udp'
        cap = cv2.VideoCapture(full_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
        
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                results.append({
                    'method': 'OpenCV UDP',
                    'status': 'success',
                    'frame_size': f"{frame.shape[1]}x{frame.shape[0]}"
                })
            else:
                results.append({'method': 'OpenCV UDP', 'status': 'opened_but_no_frame'})
            cap.release()
        else:
            results.append({'method': 'OpenCV UDP', 'status': 'failed_to_open'})
        
        # Method 3: FFprobe (if available)
        if ffmpeg_available:
            try:
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-rtsp_transport', 'tcp', 
                     '-i', full_url, '-show_entries', 'stream=width,height,codec_name',
                     '-of', 'json'],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    import json
                    probe_data = json.loads(result.stdout)
                    results.append({
                        'method': 'FFprobe',
                        'status': 'success',
                        'streams': probe_data.get('streams', [])
                    })
                else:
                    results.append({
                        'method': 'FFprobe',
                        'status': 'failed',
                        'error': result.stderr[:200] if result.stderr else 'Unknown error'
                    })
            except subprocess.TimeoutExpired:
                results.append({'method': 'FFprobe', 'status': 'timeout'})
            except Exception as e:
                results.append({'method': 'FFprobe', 'status': 'error', 'error': str(e)[:100]})
        
        # Determine overall status
        success_methods = [r for r in results if r['status'] == 'success']
        
        return JsonResponse({
            'camera_id': camera_id,
            'camera_name': camera.name,
            'rtsp_url': full_url,
            'ffmpeg_available': ffmpeg_available,
            'ffmpeg_version': ffmpeg_version,
            'results': results,
            'overall_status': 'success' if success_methods else 'failed',
            'working_methods': [r['method'] for r in success_methods]
        })
        
    except Camera.DoesNotExist:
        return JsonResponse({'error': 'Camera not found'}, status=404)
    except Exception as e:
        logger.error(f"Error testing camera {camera_id}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



# Mobile Camera Support
import requests
import numpy as np


class MobileCameraStreamer:
    """HTTP/MJPEG streamer for mobile cameras"""
    
    def __init__(self, mobile_camera_id, stream_url):
        self.mobile_camera_id = mobile_camera_id
        self.stream_url = stream_url
        self.frame: Optional[bytes] = None
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.last_access = time.time()
        self.last_frame: Optional[np.ndarray] = None

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._update, daemon=True)
            self.thread.start()
            logger.info(f"Started mobile camera streamer {self.mobile_camera_id}")

    def stop(self):
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        logger.info(f"Stopped mobile camera streamer {self.mobile_camera_id}")

    def _update(self):
        """Background thread to fetch frames from mobile camera"""
        while self.running:
            if time.time() - self.last_access > 90:
                logger.info(f"Stopping mobile camera {self.mobile_camera_id} due to inactivity")
                break

            try:
                response = requests.get(self.stream_url, stream=True, timeout=5)
                
                if response.status_code == 200:
                    logger.info(f"Connected to mobile camera {self.mobile_camera_id}")
                    bytes_data = bytes()
                    
                    for chunk in response.iter_content(chunk_size=1024):
                        if not self.running:
                            break
                            
                        bytes_data += chunk
                        a = bytes_data.find(b'\xff\xd8')  # JPEG start
                        b = bytes_data.find(b'\xff\xd9')  # JPEG end
                        
                        if a != -1 and b != -1:
                            jpg = bytes_data[a:b+2]
                            bytes_data = bytes_data[b+2:]
                            
                            try:
                                # Decode
                                img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                                if img is not None:
                                    try:
                                        # Inject tracking into mobile stream
                                        count, detections, annotated, avg_conf, tracked = \
                                            head_count_manager.detector.detect_heads(img, track_movement=True)
                                        img_to_stream = annotated
                                    except Exception as e:
                                        logger.error(f"Mobile tracking error in microservice: {e}")
                                        img_to_stream = img

                                    with self.lock:
                                        self.last_frame = img_to_stream.copy()
                                        
                                    # Fallback med frame
                                    img_med = cv2.resize(img_to_stream, (640, 360), interpolation=cv2.INTER_NEAREST)
                                    ret, jpeg = cv2.imencode('.jpg', img_med, [cv2.IMWRITE_JPEG_QUALITY, 60])
                                    if ret:
                                        with self.lock:
                                            self.frame = jpeg.tobytes()
                            except Exception as e:
                                logger.error(f"Error processing mobile frame: {e}")
                                continue
                else:
                    logger.error(f"HTTP {response.status_code} from mobile camera {self.mobile_camera_id}")
                    time.sleep(5)
                    
            except Exception as e:
                logger.error(f"Error streaming mobile camera {self.mobile_camera_id}: {e}")
                time.sleep(5)

    def get_frame(self):
        self.last_access = time.time()
        with self.lock:
            return self.frame

    def get_adaptive_frame(self, quality_level='med'):
        """Encodes mobile frame based on requested quality level"""
        self.last_access = time.time()
        with self.lock:
            if self.last_frame is None:
                return self.frame
            frame = self.last_frame.copy()

        configs = {
            'high': {'res': (1280, 720), 'quality': 85},
            'med': {'res': (640, 360), 'quality': 60},
            'low': {'res': (480, 270), 'quality': 30}
        }
        config = configs.get(quality_level, configs['med'])
        
        try:
            frame = cv2.resize(frame, config['res'], interpolation=cv2.INTER_NEAREST)
            ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, config['quality']])
            return jpeg.tobytes() if ret else self.frame
        except Exception:
            return self.frame


class MobileCameraManager:
    _lock = threading.Lock()
    _streamers = {}

    @classmethod
    def get_streamer(cls, mobile_camera_id, stream_url):
        with cls._lock:
            if mobile_camera_id not in cls._streamers or not cls._streamers[mobile_camera_id].running:
                streamer = MobileCameraStreamer(mobile_camera_id, stream_url)
                streamer.start()
                cls._streamers[mobile_camera_id] = streamer
            return cls._streamers[mobile_camera_id]
    
    @classmethod
    def stop_streamer(cls, mobile_camera_id):
        with cls._lock:
            if mobile_camera_id in cls._streamers:
                cls._streamers[mobile_camera_id].stop()
                del cls._streamers[mobile_camera_id]


mobile_camera_manager = MobileCameraManager()


def mobile_camera_feed(request, mobile_camera_id):
    """Stream mobile camera feed with adaptive bitrate support"""
    from mobile_cameras.models import MobileCamera
    quality = request.GET.get('q', 'med')
    
    try:
        mobile_camera = MobileCamera.objects.get(id=mobile_camera_id)
        if not mobile_camera.is_active:
            return JsonResponse({'error': 'Camera is paused'}, status=503)
        
        stream_url = mobile_camera.get_stream_url()
        streamer = mobile_camera_manager.get_streamer(mobile_camera.id, stream_url)
        
        def generate_frames():
            throttles = {'high': 0.033, 'med': 0.05, 'low': 0.1}
            delay = throttles.get(quality, 0.05)
            
            try:
                while True:
                    frame = streamer.get_adaptive_frame(quality)
                    if frame:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n'
                               b'Content-Length: ' + str(len(frame)).encode() + b'\r\n'
                               b'\r\n' + frame + b'\r\n')
                        time.sleep(delay)
                    else:
                        time.sleep(0.1)
            except GeneratorExit:
                logger.info(f"Disconnected from mobile camera {mobile_camera_id}")

        response = StreamingHttpResponse(
            generate_frames(),
            content_type='multipart/x-mixed-replace; boundary=frame'
        )
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['X-Accel-Buffering'] = 'no'
        return response
    except Exception as e:
        logger.error(f"Error in mobile_camera_feed: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def test_mobile_camera(request, mobile_camera_id):
    """Test mobile camera connection"""
    from mobile_cameras.models import MobileCamera
    
    try:
        mobile_camera = MobileCamera.objects.get(id=mobile_camera_id)
        
        # Check if camera is active (not paused)
        if not mobile_camera.is_active:
            return JsonResponse({
                'status': 'error',
                'message': 'Camera is paused'
            })
        
        stream_url = mobile_camera.get_stream_url()
        
        response = requests.get(stream_url, timeout=5)
        
        if response.status_code == 200:
            return JsonResponse({
                'status': 'success',
                'message': 'Mobile camera accessible',
                'url': stream_url
            })
        return JsonResponse({
            'status': 'error',
            'message': f'HTTP {response.status_code}'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
