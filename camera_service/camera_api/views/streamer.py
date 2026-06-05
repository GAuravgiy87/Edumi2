"""
camera_service/camera_api/views/streamer.py
CameraStreamer and CameraManager classes for RTSP cameras.
Handles connection, reconnection, digital zoom, and adaptive frame encoding.
"""
import os
import time
import threading
import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger('camera_api')

os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'
cv2.ocl.setUseOpenCL(True)
if cv2.ocl.haveOpenCL():
    logger.info("OpenCL Hardware Acceleration ENABLED")
else:
    logger.warning("OpenCL Hardware Acceleration NOT available")

RTSP_OPEN_TIMEOUT = 4000
RTSP_READ_TIMEOUT = 4000
RTSP_RECONNECT_DELAY = 2
RTSP_MAX_RECONNECT = 10


class CameraStreamer:
    """Non-blocking RTSP camera streamer with auto-reconnection and digital zoom."""

    def __init__(self, camera_id, rtsp_url):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame: Optional[bytes] = None
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.last_access = time.time()
        self.last_frame: Optional[np.ndarray] = None
        self.last_frame_time = 0
        self.connection_attempts = 0
        self.zoom_level = 1.0
        self.zoom_center_x = 0.5
        self.zoom_center_y = 0.5

    def set_zoom(self, level, x=None, y=None):
        """Update digital zoom level (1.0–5.0) and optional center point."""
        try:
            self.zoom_level = max(1.0, min(5.0, float(level)))
            if x is not None:
                self.zoom_center_x = max(0.0, min(1.0, float(x)))
            if y is not None:
                self.zoom_center_y = max(0.0, min(1.0, float(y)))
            return True
        except Exception:
            return False

    def _apply_zoom(self, frame):
        """Crop and resize frame to simulate digital zoom."""
        if self.zoom_level <= 1.0:
            return frame
        h, w = frame.shape[:2]
        crop_w, crop_h = int(w / self.zoom_level), int(h / self.zoom_level)
        cx, cy = int(w * self.zoom_center_x), int(h * self.zoom_center_y)
        x1 = max(0, min(w - crop_w, cx - crop_w // 2))
        y1 = max(0, min(h - crop_h, cy - crop_h // 2))
        cropped = frame[y1:y1 + crop_h, x1:x1 + crop_w]
        if cv2.ocl.useOpenCL():
            try:
                return cv2.resize(cv2.UMat(cropped), (w, h), interpolation=cv2.INTER_LINEAR).get()
            except Exception:
                pass
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._update, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def _connect_camera(self):
        """Try TCP/UDP × HW-accel combinations; return working VideoCapture or None."""
        combos = [
            ('tcp', 'rtsp_transport;tcp', 'd3d11va', 'hwaccel;d3d11va'),
            ('tcp', 'rtsp_transport;tcp', 'none', ''),
            ('udp', 'rtsp_transport;udp', 'none', ''),
        ]
        for transport, t_opt, hw_name, hw_opt in combos:
            cap = None
            try:
                opts = f'{t_opt};stimeout;4000000'
                if hw_opt:
                    opts += f';{hw_opt}'
                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = opts
                cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, RTSP_OPEN_TIMEOUT)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, RTSP_READ_TIMEOUT)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if cap.isOpened():
                    for _ in range(5):
                        ret, frame = cap.read()
                        if ret and frame is not None and np.mean(frame) > 0.1:
                            self.connection_attempts = 0
                            return cap
                        time.sleep(0.3)
                    cap.release()
            except Exception as e:
                logger.error(f"Connection error ({transport}/{hw_name}): {e}")
                if cap:
                    try:
                        cap.release()
                    except Exception:
                        pass
        # Fallback
        try:
            os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            if cap.isOpened():
                return cap
        except Exception:
            pass
        return None

    def _update(self):
        """Background capture loop — reads frames, applies zoom, encodes JPEG."""
        while self.running:
            if time.time() - self.last_access > 90:
                break
            if self.cap is None:
                if self.connection_attempts >= RTSP_MAX_RECONNECT:
                    time.sleep(10)
                    self.connection_attempts = 0
                    continue
                self.connection_attempts += 1
                self.cap = self._connect_camera()
                if self.cap is None:
                    time.sleep(RTSP_RECONNECT_DELAY)
                    continue
            try:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    self.connection_attempts = 0
                    self.last_frame_time = time.time()
                    frame = self._apply_zoom(frame)
                    if self.lock.acquire(blocking=False):
                        try:
                            self.last_frame = frame.copy()
                            med = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_LINEAR)
                            ret_j, jpeg = cv2.imencode('.jpg', med, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            if ret_j:
                                self.frame = jpeg.tobytes()
                        finally:
                            self.lock.release()
                    time.sleep(0.001)
                else:
                    if self.cap:
                        self.cap.release()
                    self.cap = None
                    time.sleep(RTSP_RECONNECT_DELAY)
            except Exception as e:
                logger.error(f"Camera {self.camera_id} read error: {e}")
                if self.cap:
                    try:
                        self.cap.release()
                    except Exception:
                        pass
                self.cap = None
                time.sleep(RTSP_RECONNECT_DELAY)
        if self.cap:
            self.cap.release()

    def get_frame(self):
        self.last_access = time.time()
        with self.lock:
            return self.frame

    def get_adaptive_frame(self, quality_level='med'):
        """Return frame encoded at requested quality level (4k/high/med/low)."""
        self.last_access = time.time()
        with self.lock:
            if self.last_frame is None:
                return self.frame
            frame = self.last_frame.copy()
        configs = {
            '4k':   {'res': (3840, 2160), 'quality': 90},
            'high': {'res': (1920, 1080), 'quality': 95},
            'med':  {'res': (1280, 720),  'quality': 85},
            'low':  {'res': (640, 360),   'quality': 60},
        }
        cfg = configs.get(quality_level, configs['med'])
        try:
            if cv2.ocl.useOpenCL():
                try:
                    resized = cv2.resize(cv2.UMat(frame), cfg['res'], interpolation=cv2.INTER_LINEAR).get()
                except Exception:
                    resized = cv2.resize(frame, cfg['res'], interpolation=cv2.INTER_LINEAR)
            else:
                resized = cv2.resize(frame, cfg['res'], interpolation=cv2.INTER_LINEAR)
            ret, jpeg = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, cfg['quality']])
            return jpeg.tobytes() if ret else self.frame
        except Exception:
            return self.frame


class CameraManager:
    """Singleton-like registry of active CameraStreamer instances."""
    _lock = threading.Lock()
    _streamers = {}

    @classmethod
    def get_streamer(cls, camera_id, rtsp_url, force_restart=False):
        with cls._lock:
            if camera_id not in cls._streamers or force_restart or not cls._streamers[camera_id].running:
                if camera_id in cls._streamers:
                    cls._streamers[camera_id].stop()
                s = CameraStreamer(camera_id, rtsp_url)
                s.start()
                cls._streamers[camera_id] = s
            return cls._streamers[camera_id]

    @classmethod
    def stop_streamer(cls, camera_id):
        with cls._lock:
            if camera_id in cls._streamers:
                cls._streamers[camera_id].stop()
                del cls._streamers[camera_id]


camera_manager = CameraManager()
