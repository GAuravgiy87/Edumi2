"""
Head Counting Service using OpenCV
Detects and counts heads in video frames with green bounding boxes
Includes movement tracking for detected persons
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
from collections import defaultdict

logger = logging.getLogger('cameras')


class TrackedPerson:
    """Track a detected person across frames"""
    def __init__(self, person_id, bbox, confidence):
        self.id = person_id
        self.bbox = bbox  # (x, y, w, h)
        self.confidence = confidence
        self.last_seen = time.time()
        self.movement_history = []  # Track movement path
        self.color = self._generate_color()
        self.missed_frames = 0
        
    def _generate_color(self):
        """Generate unique color for this person"""
        colors = [
            (0, 255, 0),    # Green
            (0, 255, 255),  # Cyan
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 128, 255),  # Orange
            (128, 0, 255),  # Purple
            (255, 128, 0),  # Blue-Orange
            (128, 255, 0),  # Lime
        ]
        return colors[self.id % len(colors)]
    
    def update_position(self, bbox, confidence):
        """Update person position and track movement"""
        # Calculate center point
        x, y, w, h = bbox
        center = (int(x + w/2), int(y + h/2))
        
        self.movement_history.append({
            'time': time.time(),
            'center': center,
            'bbox': bbox
        })
        
        # Keep only last 30 seconds of history
        cutoff = time.time() - 30
        self.movement_history = [h for h in self.movement_history if h['time'] > cutoff]
        
        self.bbox = bbox
        self.confidence = confidence
        self.last_seen = time.time()
        self.missed_frames = 0
        
    def mark_missed(self):
        """Mark that person was not detected in current frame"""
        self.missed_frames += 1
        
    def is_stale(self, timeout=2.0):
        """Check if person hasn't been seen for a while"""
        return (time.time() - self.last_seen > timeout) or self.missed_frames > 5
    
    def get_movement_trail(self):
        """Get movement trail for drawing"""
        if len(self.movement_history) < 2:
            return []
        return [h['center'] for h in self.movement_history]


class HeadDetector:
    """
    Head detection using OpenCV HOG (Histogram of Oriented Gradients) 
    with SVM classifier for human detection.
    Also uses Haar Cascade for face detection as a secondary method.
    Includes movement tracking for detected persons.
    """
    
    def __init__(self):
        # Initialize HOG descriptor for person detection
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        
        # Load Haar Cascade for face detection (backup method)
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        # Upper body cascade for additional detection
        upper_body_path = cv2.data.haarcascades + 'haarcascade_upperbody.xml'
        self.upper_body_cascade = cv2.CascadeClassifier(upper_body_path)
        
        # Detection parameters
        self.hog_scale = 1.05
        self.hog_padding = (8, 8)
        self.hog_win_stride = (4, 4)
        
        # Minimum confidence threshold
        self.confidence_threshold = 0.5
        
        # Person tracking
        self.tracked_persons = {}
        self.next_person_id = 0
        self.tracking_lock = threading.Lock()
        
    def detect_heads(self, frame, track_movement=True):
        """
        Detect heads/persons in a frame with optional movement tracking.
        Returns: (head_count, detections, annotated_frame, avg_confidence, tracked_persons)
        """
        if frame is None:
            return 0, [], None, 0.0, {}
        
        # Make a copy for annotation
        annotated_frame = frame.copy()
        
        # Resize for faster processing
        height, width = frame.shape[:2]
        max_width = 800
        scale = 1.0
        if width > max_width:
            scale = max_width / width
            frame = cv2.resize(frame, (max_width, int(height * scale)))
            annotated_frame = frame.copy()
        
        all_detections = []
        
        # Method 1: HOG Person Detection (full body)
        try:
            boxes, weights = self.hog.detectMultiScale(
                frame,
                winStride=self.hog_win_stride,
                padding=self.hog_padding,
                scale=self.hog_scale
            )
            
            for (x, y, w, h), weight in zip(boxes, weights):
                if weight > self.confidence_threshold:
                    all_detections.append({
                        'bbox': (x, y, w, h),
                        'confidence': float(weight),
                        'type': 'hog_person'
                    })
        except Exception as e:
            logger.error(f"HOG detection error: {e}")
        
        # Method 2: Haar Cascade Face Detection
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )
            
            for (x, y, w, h) in faces:
                # Check if this face overlaps with existing detections
                overlaps = False
                for det in all_detections:
                    dx, dy, dw, dh = det['bbox']
                    # Check overlap
                    if self._boxes_overlap((x, y, w, h), (dx, dy, dw, dh)):
                        overlaps = True
                        break
                
                if not overlaps:
                    all_detections.append({
                        'bbox': (x, y, w, h),
                        'confidence': 0.7,  # Default confidence for Haar
                        'type': 'haar_face'
                    })
        except Exception as e:
            logger.error(f"Haar face detection error: {e}")
        
        # Method 3: Upper Body Detection (for seated students)
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            upper_bodies = self.upper_body_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60)
            )
            
            for (x, y, w, h) in upper_bodies:
                # Check overlap with existing detections
                overlaps = False
                for det in all_detections:
                    dx, dy, dw, dh = det['bbox']
                    if self._boxes_overlap((x, y, w, h), (dx, dy, dw, dh)):
                        overlaps = True
                        break
                
                if not overlaps:
                    all_detections.append({
                        'bbox': (x, y, w, h),
                        'confidence': 0.6,
                        'type': 'upper_body'
                    })
        except Exception as e:
            logger.error(f"Upper body detection error: {e}")
        
        # Update tracking
        if track_movement:
            self._update_tracking(all_detections)
        
        # Draw movement trails first (so they're behind boxes)
        if track_movement:
            for person in self.tracked_persons.values():
                trail = person.get_movement_trail()
                if len(trail) > 1:
                    for i in range(1, len(trail)):
                        alpha = i / len(trail)
                        thickness = max(1, int(3 * alpha))
                        cv2.line(annotated_frame, trail[i-1], trail[i], person.color, thickness)
        
        # Draw green bounding boxes on all detections
        for i, det in enumerate(all_detections):
            x, y, w, h = det['bbox']
            confidence = det['confidence']
            
            # Get color from tracked person if available
            if track_movement and i < len(self.tracked_persons):
                person = list(self.tracked_persons.values())[i]
                color = person.color
            else:
                color = (0, 255, 0)  # Default green
            
            thickness = 2
            
            # Draw rectangle with rounded corners effect
            cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), color, thickness)
            
            # Draw corner markers for better visibility
            corner_len = min(20, w//4, h//4)
            # Top-left
            cv2.line(annotated_frame, (x, y), (x + corner_len, y), color, thickness+1)
            cv2.line(annotated_frame, (x, y), (x, y + corner_len), color, thickness+1)
            # Top-right
            cv2.line(annotated_frame, (x + w, y), (x + w - corner_len, y), color, thickness+1)
            cv2.line(annotated_frame, (x + w, y), (x + w, y + corner_len), color, thickness+1)
            # Bottom-left
            cv2.line(annotated_frame, (x, y + h), (x + corner_len, y + h), color, thickness+1)
            cv2.line(annotated_frame, (x, y + h), (x, y + h - corner_len), color, thickness+1)
            # Bottom-right
            cv2.line(annotated_frame, (x + w, y + h), (x + w - corner_len, y + h), color, thickness+1)
            cv2.line(annotated_frame, (x + w, y + h), (x + w, y + h - corner_len), color, thickness+1)
            
            # Draw confidence score with background
            label = f"{confidence:.2f}"
            if track_movement and i < len(self.tracked_persons):
                person = list(self.tracked_persons.values())[i]
                label = f"ID:{person.id} {label}"
            
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            # Draw label background
            cv2.rectangle(annotated_frame, (x, y - label_size[1] - 8), 
                         (x + label_size[0] + 8, y), color, -1)
            # Draw label text
            cv2.putText(annotated_frame, label, (x + 4, y - 4),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        # Draw total count on frame with background
        head_count = len(all_detections)
        count_text = f"Heads: {head_count}"
        if track_movement:
            count_text = f"Heads: {head_count} | Tracked: {len(self.tracked_persons)}"
        
        # Draw background for count text
        text_size, _ = cv2.getTextSize(count_text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
        cv2.rectangle(annotated_frame, (5, 5), (text_size[0] + 15, 40), (0, 0, 0), -1)
        cv2.putText(annotated_frame, count_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Calculate average confidence
        avg_confidence = 0.0
        if all_detections:
            avg_confidence = sum(d['confidence'] for d in all_detections) / len(all_detections)
        
        return head_count, all_detections, annotated_frame, avg_confidence, self.tracked_persons
    
    def _update_tracking(self, detections):
        """Update person tracking based on new detections"""
        with self.tracking_lock:
            current_time = time.time()
            
            # Mark all existing persons as potentially missed
            for person in self.tracked_persons.values():
                person.mark_missed()
            
            # Match detections to existing tracked persons
            matched_persons = set()
            
            for det in detections:
                bbox = det['bbox']
                confidence = det['confidence']
                
                # Find best matching existing person
                best_match = None
                best_iou = 0.3  # Minimum IOU threshold
                
                for person_id, person in self.tracked_persons.items():
                    if person_id in matched_persons:
                        continue
                    
                    iou = self._calculate_iou(bbox, person.bbox)
                    if iou > best_iou:
                        best_iou = iou
                        best_match = person_id
                
                if best_match is not None:
                    # Update existing person
                    self.tracked_persons[best_match].update_position(bbox, confidence)
                    matched_persons.add(best_match)
                else:
                    # Create new tracked person
                    new_person = TrackedPerson(self.next_person_id, bbox, confidence)
                    self.tracked_persons[self.next_person_id] = new_person
                    self.next_person_id += 1
                    matched_persons.add(new_person.id)
            
            # Remove stale persons
            stale_ids = [pid for pid, person in self.tracked_persons.items() if person.is_stale()]
            for pid in stale_ids:
                del self.tracked_persons[pid]
    
    def _calculate_iou(self, box1, box2):
        """Calculate Intersection over Union (IOU) between two boxes"""
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2
        
        xi1 = max(x1, x2)
        yi1 = max(y1, y2)
        xi2 = min(x1 + w1, x2 + w2)
        yi2 = min(y1 + h1, y2 + h2)
        
        if xi2 <= xi1 or yi2 <= yi1:
            return 0.0
        
        intersection = (xi2 - xi1) * (yi2 - yi1)
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def _boxes_overlap(self, box1, box2, threshold=0.3):
        """Check if two boxes overlap significantly"""
        return self._calculate_iou(box1, box2) > threshold


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
                    if reconnect_attempts >= max_reconnect:
                        logger.error(f"Max reconnection attempts reached for {camera_key}")
                        break
                    
                    cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    
                    if not cap.isOpened():
                        reconnect_attempts += 1
                        time.sleep(5)
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
                head_count, detections, annotated_frame, avg_confidence = \
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
                
                session_data['last_count'] = head_count
                
                # Wait for next interval
                time.sleep(interval)
                
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
