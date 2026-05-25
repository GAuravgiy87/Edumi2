"""Camera streaming views - isolated service"""
import cv2
import numpy as np
import threading
import time
import logging
import os
from typing import Optional
from django.http import StreamingHttpResponse, JsonResponse
import sys
from pathlib import Path

logger = logging.getLogger('camera_api')

# Set FFmpeg environment variables for better RTSP handling and GPU acceleration
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'
# Enable OpenCL for hardware-accelerated image processing (resizing/filtering)
cv2.ocl.setUseOpenCL(True)
if cv2.ocl.haveOpenCL():
    logger.info("OpenCL Hardware Acceleration ENABLED for OpenCV")
else:
    logger.warning("OpenCL Hardware Acceleration NOT available for OpenCV")

# Import Camera model from main project
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from cameras.models import Camera
try:
    from cameras.head_count_service import head_count_manager
except ImportError:
    # If not in path, try adding it again carefully
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from cameras.head_count_service import head_count_manager

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
        self.last_frame_time = 0 # Timestamp of last successful frame
        self.connection_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2
        self.zoom_level = 1.0  # 1.0 to 5.0 (Digital zoom)
        self.zoom_center_x = 0.5  # 0.0 to 1.0 (Center of zoom)
        self.zoom_center_y = 0.5  # 0.0 to 1.0 (Center of zoom)

    def set_zoom(self, level, x=None, y=None):
        """Update the digital zoom level and optional center point safely"""
        try:
            level = float(level)
            # Limit zoom between 1.0x and 5.0x
            self.zoom_level = max(1.0, min(5.0, level))
            
            if x is not None:
                self.zoom_center_x = max(0.0, min(1.0, float(x)))
            if y is not None:
                self.zoom_center_y = max(0.0, min(1.0, float(y)))
                
            logger.info(f"Camera {self.camera_id} zoom set to {self.zoom_level}x at ({self.zoom_center_x}, {self.zoom_center_y})")
            return True
        except:
            return False

    def _apply_zoom(self, frame):
        """Applies digital zoom by cropping around a target point and resizing back"""
        if self.zoom_level <= 1.0:
            return frame
        
        h, w = frame.shape[:2]
        
        # Calculate crop dimensions
        crop_w = int(w / self.zoom_level)
        crop_h = int(h / self.zoom_level)
        
        # Calculate center point in pixels
        center_x = int(w * self.zoom_center_x)
        center_y = int(h * self.zoom_center_y)
        
        # Calculate crop boundaries (clamped to frame edges)
        x1 = max(0, min(w - crop_w, center_x - crop_w // 2))
        y1 = max(0, min(h - crop_h, center_y - crop_h // 2))
        x2 = x1 + crop_w
        y2 = y1 + crop_h
        
        # Crop the frame
        cropped = frame[y1:y2, x1:x2]
        
        # Resize back to original dimensions using GPU (OpenCL) if available
        # Using INTER_LINEAR for zoom instead of LANCZOS4 for massive speed gain
        if cv2.ocl.useOpenCL():
            try:
                gpu_frame = cv2.UMat(cropped)
                gpu_resized = cv2.resize(gpu_frame, (w, h), interpolation=cv2.INTER_LINEAR)
                return gpu_resized.get()
            except Exception as e:
                logger.warning(f"GPU Resize failed, falling back to CPU: {e}")
        
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

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
                
                # Set environment variable for this attempt with hardware decoding support
                # Using d3d11va for RX 550 and increasing buffer for stability
                # stimeout is in microseconds (4s = 4000000)
                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = f'{transport_opt};hwaccel;d3d11va;stimeout;4000000'
                
                cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, RTSP_OPEN_TIMEOUT)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, RTSP_READ_TIMEOUT)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Small buffer for lowest latency and freeze prevention
                cap.set(cv2.CAP_PROP_FPS, 30)
                
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
                    self.last_frame_time = time.time() # Track freshness

                    # Apply digital zoom BEFORE AI processing
                    frame = self._apply_zoom(frame)

                    # Store RAW FULL-RES frame for adaptive encoding (4K support)
                    # Use a non-blocking lock check to avoid stalling capture
                    if self.lock.acquire(blocking=False):
                        try:
                            self.last_frame = frame.copy()
                            
                            # Fast downscale for standard stream (1080p fallback instead of 4K)
                            # Use GPU if available
                            frame_med = None
                            if cv2.ocl.useOpenCL():
                                try:
                                    gpu_frame = cv2.UMat(frame)
                                    gpu_resized = cv2.resize(gpu_frame, (1280, 720), interpolation=cv2.INTER_LINEAR) # Faster interpolation
                                    frame_med = gpu_resized.get()
                                except Exception: pass
                            
                            if frame_med is None:
                                frame_med = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_LINEAR)
                                
                            ret_med, jpeg = cv2.imencode('.jpg', frame_med, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            if ret_med:
                                self.frame = jpeg.tobytes()
                        finally:
                            self.lock.release()
                    
                    # Only run heavy AI every N frames to save CPU/GPU for streaming
                    if self.connection_attempts % 3 == 0:
                        # Detect heads in background or periodically
                        # For now, let's keep the capture loop as fast as possible
                        pass

                    time.sleep(0.001)  # Minimal sleep to prevent CPU pegging but stay fast
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
        """Encodes frame based on requested quality level with high fidelity"""
        self.last_access = time.time()
        with self.lock:
            if self.last_frame is None:
                return self.frame
            frame = self.last_frame.copy()

        configs = {
            '4k': {'res': (3840, 2160), 'quality': 98},  # Ultra High Fidelity
            'high': {'res': (1920, 1080), 'quality': 95}, # Full HD
            'med': {'res': (1280, 720), 'quality': 85},   # HD
            'low': {'res': (640, 360), 'quality': 60}     # SD
        }
        config = configs.get(quality_level, configs['med'])
        
        try:
            # Use GPU-accelerated resizing (OpenCL) if available
            res_frame = None
            if cv2.ocl.useOpenCL():
                try:
                    gpu_frame = cv2.UMat(frame)
                    # Use INTER_AREA or INTER_LINEAR for faster processing during streaming
                    interp = cv2.INTER_LINEAR if quality_level in ['4k', 'high'] else cv2.INTER_AREA
                    gpu_resized = cv2.resize(gpu_frame, config['res'], interpolation=interp)
                    res_frame = gpu_resized.get()
                except Exception as e:
                    logger.warning(f"GPU Adaptive Resize failed: {e}")
            
            if res_frame is None:
                res_frame = cv2.resize(frame, config['res'], interpolation=cv2.INTER_LINEAR)
            
            # Reduce quality slightly for 4K to save bandwidth and encoding time
            jpg_quality = config['quality']
            if quality_level == '4k': jpg_quality = 90 # Still very high but less taxing
            
            ret, jpeg = cv2.imencode('.jpg', res_frame, [cv2.IMWRITE_JPEG_QUALITY, jpg_quality])
            return jpeg.tobytes() if ret else self.frame
        except Exception:
            return self.frame

class CameraManager:
    _lock = threading.Lock()
    _streamers = {}

    @classmethod
    def get_streamer(cls, camera_id, rtsp_url, force_restart=False):
        with cls._lock:
            # Create new streamer if not exists or if existing one stopped/stale
            should_create = False
            if camera_id not in cls._streamers:
                should_create = True
            elif force_restart:
                logger.info(f"Forcing restart for camera {camera_id}")
                cls._streamers[camera_id].stop()
                should_create = True
            elif not cls._streamers[camera_id].running:
                should_create = True
            
            if should_create:
                logger.info(f"Creating/Restarting streamer for camera {camera_id}")
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
            # Throttle based on quality (4k/high = 30fps, med = 20fps, low = 10fps)
            throttles = {'4k': 0.033, 'high': 0.033, 'med': 0.05, 'low': 0.1}
            delay = throttles.get(quality, 0.05)
            
            # Wait for first frame (up to 15 seconds)
            wait_count = 0
            max_wait = 150  # 15 seconds at 0.1s intervals
            while streamer.get_frame() is None and wait_count < max_wait:
                time.sleep(0.1)
                wait_count += 1
                if wait_count % 10 == 0:
                    logger.info(f"Waiting for first frame from camera {camera_id}... ({wait_count/10:.0f}s)")
            
            if streamer.get_frame() is None:
                logger.error(f"No frame received from camera {camera_id} after 15 seconds")
                # Force restart for next attempt
                camera_manager.get_streamer(camera.id, full_url, force_restart=True)
                return # This will trigger img.onerror in the browser
            
            logger.info(f"=== STREAMING STARTED for camera {camera_id} ===")
            frame_count = 0
            
            try:
                while True:
                    # Check for streamer health
                    stale_time = time.time() - streamer.last_frame_time
                    if stale_time > 10.0: # If no frame for 10 seconds, it's frozen
                        logger.warning(f"Camera {camera_id} stream is frozen ({stale_time:.1f}s). Terminating response.")
                        # Force restart for next client
                        camera_manager.get_streamer(camera.id, full_url, force_restart=True)
                        break # Terminate current response to trigger browser retry

                    if stale_time > 4.0:
                        # Stream is lagging, wait briefly and retry
                        time.sleep(0.5)
                        continue

                    frame = streamer.get_adaptive_frame(quality)
                    if frame:
                        frame_count += 1
                        if frame_count % 100 == 0:
                            logger.info(f"Camera {camera_id}: streamed {frame_count} frames")
                        
                        # Use a simpler, more robust MJPEG boundary
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
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

def update_camera_zoom(request, camera_id):
    """Endpoint to update digital zoom level for a camera"""
    zoom_level = request.GET.get('level', 1.0)
    x = request.GET.get('x')
    y = request.GET.get('y')
    try:
        camera = Camera.objects.get(id=camera_id)
        full_url = camera.get_full_rtsp_url()
        streamer = camera_manager.get_streamer(camera.id, full_url)
        
        if streamer.set_zoom(zoom_level, x, y):
            return JsonResponse({
                'status': 'success', 
                'zoom': streamer.zoom_level,
                'x': streamer.zoom_center_x,
                'y': streamer.zoom_center_y
            })
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid zoom level'}, status=400)
    except Camera.DoesNotExist:
        return JsonResponse({'error': 'Camera not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def test_camera(request, camera_id):
    """Test camera connection with detailed diagnostics"""
    import subprocess
    
    try:
        camera = Camera.objects.get(id=camera_id)
        results = []
        
        # Log the RTSP URL (hide password)
        safe_url = camera.get_full_rtsp_url()
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

# ─────────────────────────────────────────────────────────────
# HEAD COUNTING API (Microservice implementation)
# ─────────────────────────────────────────────────────────────

def start_head_count(request, camera_type, camera_id):
    """Start head counting session in the dedicated service"""
    from django.contrib.auth.models import User
    from meetings.models import Classroom
    
    # Get camera details
    if camera_type == 'rtsp':
        camera = Camera.objects.get(id=camera_id)
        stream_url = camera.get_full_rtsp_url()
        camera_name = camera.name
    elif camera_type == 'mobile':
        from mobile_cameras.models import MobileCamera
        camera = MobileCamera.objects.get(id=camera_id)
        stream_url = camera.get_stream_url()
        camera_name = camera.name
    else:
        return JsonResponse({'error': 'Invalid camera type'}, status=400)
    
    # Get optional metadata from request
    user_id = request.GET.get('user_id')
    user = User.objects.get(id=user_id) if user_id else None
    
    classroom_id = request.GET.get('classroom_id')
    classroom = Classroom.objects.get(id=classroom_id) if classroom_id else None
    
    interval = int(request.GET.get('interval', 30))
    
    # Start session in the singleton head_count_manager
    success, result = head_count_manager.start_session(
        camera_type=camera_type,
        camera_id=camera_id,
        stream_url=stream_url,
        camera_name=camera_name,
        user=user,
        classroom=classroom,
        interval=interval
    )
    
    if success:
        return JsonResponse({'success': True, 'session_id': result})
    else:
        return JsonResponse({'error': result}, status=400)

def stop_head_count(request, camera_type, camera_id):
    """Stop head counting session in the dedicated service"""
    success, message = head_count_manager.stop_session(camera_type, camera_id)
    
    if success:
        return JsonResponse({'success': True, 'message': message})
    else:
        return JsonResponse({'error': message}, status=400)
