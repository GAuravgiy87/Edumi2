"""
Head Counting Service using OpenCV with GPU/OpenCL acceleration.
Detects and counts heads in video frames with green bounding boxes.
Uses AMD GPU via OpenCL when available, falls back to optimized CPU.
"""
import cv2
import numpy as np
import threading
import time
import logging
import os
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
from collections import defaultdict, deque
import concurrent.futures

# Force TCP transport for RTSP
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

logger = logging.getLogger('cameras')

# Enable OpenCL (AMD GPU) for OpenCV
cv2.ocl.setUseOpenCL(True)
_OPENCL_AVAILABLE = cv2.ocl.useOpenCL()
if _OPENCL_AVAILABLE:
    logger.info(f"[HeadCount] OpenCL enabled: {cv2.ocl.Device.getDefault().name()}")
else:
    logger.info("[HeadCount] OpenCL not available — using CPU")

# Use all available cores for OpenCV
cv2.setNumThreads(max(1, os.cpu_count() - 2))


class HeadDetector:
    """
    Optimized Head Detection with Frame Skipping & Resolution Control.
    Ensures high FPS while maintaining tracking accuracy.
    """
    
    def __init__(self):
        # Initialize HOG descriptor
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        
        # Load Haar Cascades
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.profile_face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_profileface.xml')
        self.upper_body_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_upperbody.xml')
        
        # Parameters
        self.confidence_threshold = 0.35
        self.tracking_lock = threading.Lock()
        
        # Motion detection (DISABLED)
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)
        
        # Performance/Stabilization State
        self.frame_counter = 0
        self.last_full_detections = []
        self.head_count_history = deque(maxlen=15)
        self.stable_head_count = 0

    def detect_heads(self, frame, track_movement=False):
        """Main entry point for detection. GPU-accelerated via OpenCL when available."""
        if frame is None: return 0, [], None, 0.0, {}

        orig_h, orig_w = frame.shape[:2]

        # Resize for performance
        max_p_w = 400
        scale = 1.0
        if orig_w > max_p_w:
            scale = max_p_w / orig_w
            p_frame = cv2.resize(frame, (max_p_w, int(orig_h * scale)))
        else:
            p_frame = frame.copy()

        inv_scale = 1.0 / scale
        annotated_raw = frame.copy()

        with self.tracking_lock:
            self.frame_counter += 1
            should_run_heavy = (self.frame_counter % 5 == 0)

            if not should_run_heavy and self.last_full_detections:
                return self._finalize(self.stable_head_count, self.last_full_detections,
                                      annotated_raw, inv_scale)

        # ── GPU-accelerated grayscale conversion ──────────────────────────
        if _OPENCL_AVAILABLE:
            umat_frame = cv2.UMat(p_frame)
            gray_umat  = cv2.cvtColor(umat_frame, cv2.COLOR_BGR2GRAY)
            gray       = gray_umat.get()
        else:
            gray = cv2.cvtColor(p_frame, cv2.COLOR_BGR2GRAY)

        all_detections = []

        # 1. HOG (CPU — no OpenCL support in HOG)
        try:
            boxes, weights = self.hog.detectMultiScale(p_frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
            for (x, y, w, h), weight in zip(boxes, weights):
                if weight > self.confidence_threshold:
                    all_detections.append({'bbox': (x, y, w, h), 'confidence': float(weight), 'type': 'hog_person'})
        except Exception:
            pass

        # 2. Haar Face (OpenCL-accelerated when available)
        try:
            gray_src = gray_umat if _OPENCL_AVAILABLE else gray
            faces = self.face_cascade.detectMultiScale(gray_src, 1.1, 3, minSize=(20, 20))
            if _OPENCL_AVAILABLE and hasattr(faces, 'get'):
                faces = faces.get() if len(faces) > 0 else []
            for box in (faces if len(faces) > 0 else []):
                if not any(self._boxes_overlap(box, d['bbox']) for d in all_detections):
                    all_detections.append({'bbox': tuple(box), 'confidence': 0.7, 'type': 'haar_face'})

            profiles = self.profile_face_cascade.detectMultiScale(gray_src, 1.1, 3, minSize=(20, 20))
            if _OPENCL_AVAILABLE and hasattr(profiles, 'get'):
                profiles = profiles.get() if len(profiles) > 0 else []
            for box in (profiles if len(profiles) > 0 else []):
                if not any(self._boxes_overlap(box, d['bbox']) for d in all_detections):
                    all_detections.append({'bbox': tuple(box), 'confidence': 0.65, 'type': 'profile_face'})
        except Exception:
            pass

        # 3. Upper Body
        try:
            bodies = self.upper_body_cascade.detectMultiScale(gray, 1.1, 3, minSize=(30, 30))
            for box in (bodies if len(bodies) > 0 else []):
                if not any(self._boxes_overlap(box, d['bbox']) for d in all_detections):
                    all_detections.append({'bbox': tuple(box), 'confidence': 0.6, 'type': 'upper_body'})
        except Exception:
            pass

        with self.tracking_lock:
            current_count = len(all_detections)
            self.head_count_history.append(current_count)
            self.stable_head_count = int(np.median(list(self.head_count_history))) if self.head_count_history else current_count
            self.last_full_detections = all_detections

            return self._finalize(self.stable_head_count, all_detections, annotated_raw, inv_scale)

    def _finalize(self, count, detections, frame, inv_scale):
        """Annotate and return frame with professional HUD."""
        
        # 1. Solid Top Bar for HUD - Fixed height 80px
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 80), (0, 0, 0), -1)
        
        # 2. Status Text
        status_text = f"Heads: {count}"
        cv2.putText(frame, status_text, (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 0), 3)
        
        # 3. Current Time on the right
        ts = time.strftime("%H:%M:%S")
        cv2.putText(frame, ts, (frame.shape[1]-150, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1)
        
        # Resize once to common display size
        if frame.shape[1] > 1280:
            frame = cv2.resize(frame, (1280, 720))
            
        return count, detections, frame, 0.0, {}

    def _calculate_iou(self, b1, b2):
        x1, y1, w1, h1 = b1
        x2, y2, w2, h2 = b2
        xi1, yi1, xi2, yi2 = max(x1, x2), max(y1, y2), min(x1+w1, x2+w2), min(y1+h1, y2+h2)
        if xi2 <= xi1 or yi2 <= yi1: return 0.0
        inter = (xi2-xi1) * (yi2-yi1)
        return inter / (w1*h1 + w2*h2 - inter)

    def _calculate_inclusion(self, s, l):
        sx, sy, sw, sh = s
        lx, ly, lw, lh = l
        xi1, yi1, xi2, yi2 = max(sx, lx), max(sy, ly), min(sx+sw, lx+lw), min(sy+sh, ly+lh)
        if xi2 <= xi1 or yi2 <= yi1: return 0.0
        return (xi2-xi1)*(yi2-yi1) / (sw*sh)

    def _boxes_overlap(self, b1, b2, threshold=0.3):
        if self._calculate_iou(b1, b2) > threshold: return True
        return self._calculate_inclusion(b1, b2) > 0.8 or self._calculate_inclusion(b2, b1) > 0.8


class HeadCountManager:
    """
    Manages head counting sessions for multiple cameras.
    Runs in background threads and logs counts periodically.
    """
    
    _instance = None
    _lock = threading.Lock()
    _sessions = {}  # camera_key -> session_data
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.detector = HeadDetector()
                    cls._instance._sessions = {}
        return cls._instance
    
    def get_camera_key(self, camera_type, camera_id):
        """Generate unique key for camera"""
        return f"{camera_type}_{camera_id}"
    
    def start_session(self, camera_type, camera_id, stream_url, camera_name, 
                      user, classroom=None, interval=30):
        """
        Start a head counting session for a camera.
        
        Args:
            camera_type: 'rtsp' or 'mobile'
            camera_id: ID of the camera
            stream_url: URL to stream video from
            camera_name: Name of the camera
            user: User who started the session
            classroom: Optional classroom to associate
            interval: Seconds between captures
        """
        from .models import HeadCountSession
        
        camera_key = self.get_camera_key(camera_type, camera_id)
        
        # Check if session already exists
        if camera_key in self._sessions:
            return False, "Session already active for this camera"
        
        # Create session record
        session = HeadCountSession.objects.create(
            camera_type=camera_type,
            camera_id=camera_id,
            camera_name=camera_name,
            classroom=classroom,
            started_by=user,
            status='active',
            capture_interval=interval
        )
        
        # Start background thread
        session_data = {
            'session': session,
            'stream_url': stream_url,
            'running': True,
            'thread': None,
            'cap': None,
            'last_count': 0,
        }
        
        thread = threading.Thread(
            target=self._run_session,
            args=(camera_key, session_data),
            daemon=True
        )
        session_data['thread'] = thread
        
        self._sessions[camera_key] = session_data
        thread.start()
        
        logger.info(f"Started head count session for {camera_key}")
        return True, session.id
    
    def stop_session(self, camera_type, camera_id):
        """Stop a head counting session"""
        from .models import HeadCountSession
        from django.db import transaction
        
        camera_key = self.get_camera_key(camera_type, camera_id)
        
        if camera_key not in self._sessions:
            return False, "No active session for this camera"
        
        session_data = self._sessions[camera_key]
        session_data['running'] = False
        
        # Release video capture
        if session_data.get('cap'):
            session_data['cap'].release()
        
        # Wait for thread to finish
        if session_data.get('thread'):
            session_data['thread'].join(timeout=5)
        
        # Update session record
        try:
            session = HeadCountSession.objects.get(id=session_data['session'].id)
            session.status = 'stopped'
            session.stopped_at = timezone.now()
            session.save()
        except HeadCountSession.DoesNotExist:
            pass
        
        del self._sessions[camera_key]
        logger.info(f"Stopped head count session for {camera_key}")
        return True, "Session stopped"
    
    def get_active_sessions(self):
        """Get all active sessions"""
        return {key: data['session'] for key, data in self._sessions.items()}
    
    def is_session_active(self, camera_type, camera_id):
        """Check if a session is active for a camera"""
        camera_key = self.get_camera_key(camera_type, camera_id)
        return camera_key in self._sessions
    
    def _run_session(self, camera_key, session_data):
        """Background thread for head counting"""
        from .models import HeadCountLog, HeadCountSession
        
        session = session_data['session']
        stream_url = session_data['stream_url']
        interval = session.capture_interval
        
        # Initialize video capture
        cap = None
        reconnect_attempts = 0
        max_reconnect = 5
        
        while session_data['running']:
            try:
                # Connect to stream
                if cap is None or not cap.isOpened():
                    if reconnect_attempts >= 3: # Reduced from 5 for faster "Stop"
                        logger.error(f"Camera {camera_key} is OFFLINE. Stopping session.")
                        # Stop the session properly
                        self.stop_session(session.camera_type, session.camera_id)
                        # Mark as errored in DB if possible
                        try:
                            s = HeadCountSession.objects.get(id=session.id)
                            s.status = 'error'
                            s.save()
                        except: pass
                        break
                    
                    cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    
                    if not cap.isOpened():
                        reconnect_attempts += 1
                        time.sleep(2) # Faster check
                        continue
                    
                    reconnect_attempts = 0
                
                # Read frame
                ret, frame = cap.read()
                
                if not ret or frame is None:
                    logger.warning(f"Failed to read frame from {camera_key}")
                    cap.release()
                    cap = None
                    time.sleep(2)
                    continue
                
                # Detect heads
                head_count, detections, annotated_frame, avg_confidence, tracked_persons = \
                    self.detector.detect_heads(frame)
                
                # Save log entry
                self._save_log(session, head_count, avg_confidence, annotated_frame)
                
                # Update session stats
                try:
                    session = HeadCountSession.objects.get(id=session.id)
                    session.total_captures += 1
                    
                    if session.total_captures == 1:
                        session.max_head_count = head_count
                        session.min_head_count = head_count
                        session.average_head_count = head_count
                    else:
                        session.max_head_count = max(session.max_head_count, head_count)
                        session.min_head_count = min(session.min_head_count, head_count)
                        # Running average
                        session.average_head_count = (
                            (session.average_head_count * (session.total_captures - 1) + head_count) 
                            / session.total_captures
                        )
                    session.save()
                except HeadCountSession.DoesNotExist:
                    pass
                
                # Wait for next interval (checked in small increments for faster shutdown)
                for _ in range(int(interval * 2)):
                    if not session_data['running']: break
                    time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error in head count session {camera_key}: {e}")
                if cap:
                    cap.release()
                    cap = None
                time.sleep(5)
        
        # Cleanup
        if cap:
            cap.release()
        logger.info(f"Head count thread ended for {camera_key}")
    
    def _save_log(self, session, head_count, avg_confidence, annotated_frame):
        """Save a head count log entry"""
        from .models import HeadCountLog
        
        try:
            log_entry = HeadCountLog(
                camera_type=session.camera_type,
                camera_id=session.camera_id,
                camera_name=session.camera_name,
                classroom=session.classroom,
                head_count=head_count,
                confidence_score=avg_confidence,
                recorded_by=session.started_by,
            )
            
            # Save annotated frame as snapshot
            if annotated_frame is not None:
                ret, buffer = cv2.imencode('.jpg', annotated_frame, 
                                          [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    log_entry.snapshot.save(
                        f"headcount_{session.id}_{int(time.time())}.jpg",
                        ContentFile(buffer.tobytes()),
                        save=False
                    )
            
            log_entry.save()
            logger.info(f"Saved head count log: {head_count} heads")
            
        except Exception as e:
            logger.error(f"Error saving head count log: {e}")
    
    def get_current_count(self, camera_type, camera_id):
        """Get the current head count for a camera"""
        camera_key = self.get_camera_key(camera_type, camera_id)
        if camera_key in self._sessions:
            return self._sessions[camera_key].get('last_count', 0)
        return None


# Singleton instance
head_count_manager = HeadCountManager()
