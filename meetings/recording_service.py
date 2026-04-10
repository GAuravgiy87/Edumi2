"""
Meeting Recording Service — Hardware-accelerated video encoding.

Uses AMD GPU (h264_amf) → Intel QSV (h264_qsv) → libx264 (CPU) in priority order.
Recordings are stored as H.264 MP4 files under media/recordings/<meeting_code>/.

Usage:
    recorder = MeetingRecorder(meeting_code='ABC123', fps=25, width=1280, height=720)
    recorder.start()
    recorder.write_frame(frame_bgr_numpy_array)
    recorder.stop()  # finalizes and saves path to DB
"""

import os
import subprocess
import threading
import logging
import time
from pathlib import Path

import cv2
import numpy as np
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('meetings.recording')

RECORDINGS_DIR = Path(settings.MEDIA_ROOT) / 'recordings'
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)


def _detect_best_encoder() -> str:
    """
    Probe FFmpeg for the best available hardware encoder.
    Returns encoder name string.
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-encoders', '-v', 'quiet'],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout + result.stderr
        if 'h264_amf' in output:
            logger.info("[Recording] Encoder: h264_amf (AMD GPU)")
            return 'h264_amf'
        if 'h264_qsv' in output:
            logger.info("[Recording] Encoder: h264_qsv (Intel QSV)")
            return 'h264_qsv'
        if 'libx264' in output:
            logger.info("[Recording] Encoder: libx264 (CPU)")
            return 'libx264'
    except FileNotFoundError:
        logger.warning("[Recording] FFmpeg not found — falling back to OpenCV VideoWriter")
    except Exception as e:
        logger.warning(f"[Recording] Encoder detection failed: {e}")
    return 'opencv'  # fallback


def _build_ffmpeg_cmd(encoder: str, output_path: str, fps: int,
                       width: int, height: int) -> list:
    """Build FFmpeg command for piped raw BGR frames."""
    base = [
        'ffmpeg', '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-pix_fmt', 'bgr24',
        '-s', f'{width}x{height}',
        '-r', str(fps),
        '-i', 'pipe:0',
    ]

    if encoder == 'h264_amf':
        encode = [
            '-c:v', 'h264_amf',
            '-quality', 'speed',       # balanced: speed / quality / balanced
            '-rc', 'cqp',
            '-qp_i', '23', '-qp_p', '25',
            '-movflags', '+faststart',
        ]
    elif encoder == 'h264_qsv':
        encode = [
            '-c:v', 'h264_qsv',
            '-global_quality', '23',
            '-look_ahead', '1',
            '-movflags', '+faststart',
        ]
    elif encoder == 'libx264':
        encode = [
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-tune', 'zerolatency',
            '-movflags', '+faststart',
        ]
    else:
        encode = ['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28']

    return base + encode + [output_path]


class MeetingRecorder:
    """
    Thread-safe meeting recorder.
    Pipes frames to FFmpeg for hardware-accelerated H.264 encoding.
    Falls back to OpenCV VideoWriter if FFmpeg is unavailable.
    """

    def __init__(self, meeting_code: str, fps: int = 25,
                 width: int = 1280, height: int = 720):
        self.meeting_code = meeting_code
        self.fps    = fps
        self.width  = width
        self.height = height

        self._encoder   = _detect_best_encoder()
        self._lock      = threading.Lock()
        self._running   = False
        self._proc      = None   # FFmpeg subprocess
        self._writer    = None   # OpenCV fallback
        self._output_path: str = ''
        self._frame_count = 0
        self._start_time  = None

    def start(self) -> str:
        """Start recording. Returns the output file path."""
        ts = timezone.now().strftime('%Y%m%d_%H%M%S')
        meeting_dir = RECORDINGS_DIR / self.meeting_code
        meeting_dir.mkdir(parents=True, exist_ok=True)
        self._output_path = str(meeting_dir / f'recording_{ts}.mp4')

        if self._encoder != 'opencv':
            cmd = _build_ffmpeg_cmd(
                self._encoder, self._output_path,
                self.fps, self.width, self.height
            )
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._running = True
                self._start_time = time.time()
                logger.info(f"[Recording] Started: {self._output_path} ({self._encoder})")
                return self._output_path
            except Exception as e:
                logger.error(f"[Recording] FFmpeg failed to start: {e} — falling back to OpenCV")
                self._encoder = 'opencv'

        # OpenCV fallback
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        self._writer = cv2.VideoWriter(
            self._output_path, fourcc, self.fps, (self.width, self.height)
        )
        if not self._writer.isOpened():
            # Try XVID
            self._output_path = self._output_path.replace('.mp4', '.avi')
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self._writer = cv2.VideoWriter(
                self._output_path, fourcc, self.fps, (self.width, self.height)
            )
        self._running = True
        self._start_time = time.time()
        logger.info(f"[Recording] Started (OpenCV): {self._output_path}")
        return self._output_path

    def write_frame(self, frame: np.ndarray):
        """Write a BGR frame. Resizes if needed. Thread-safe."""
        if not self._running:
            return
        try:
            # Resize to target resolution if needed
            if frame.shape[1] != self.width or frame.shape[0] != self.height:
                frame = cv2.resize(frame, (self.width, self.height))

            with self._lock:
                if self._proc and self._proc.stdin:
                    self._proc.stdin.write(frame.tobytes())
                elif self._writer:
                    self._writer.write(frame)
                self._frame_count += 1
        except BrokenPipeError:
            logger.warning("[Recording] FFmpeg pipe broken — stopping recorder")
            self._running = False
        except Exception as e:
            logger.error(f"[Recording] write_frame error: {e}")

    def stop(self) -> str:
        """Stop recording and finalize the file. Returns output path."""
        self._running = False
        with self._lock:
            if self._proc:
                try:
                    self._proc.stdin.close()
                    self._proc.wait(timeout=15)
                except Exception as e:
                    logger.warning(f"[Recording] FFmpeg stop error: {e}")
                    self._proc.kill()
                self._proc = None

            if self._writer:
                self._writer.release()
                self._writer = None

        duration = round(time.time() - self._start_time, 1) if self._start_time else 0
        size_mb   = round(os.path.getsize(self._output_path) / 1024 / 1024, 2) \
                    if os.path.exists(self._output_path) else 0
        logger.info(
            f"[Recording] Stopped: {self._output_path} | "
            f"frames={self._frame_count} duration={duration}s size={size_mb}MB"
        )
        return self._output_path

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def output_path(self) -> str:
        return self._output_path


# ── Global registry of active recorders ──────────────────────────────────────

_recorders: dict[str, MeetingRecorder] = {}
_registry_lock = threading.Lock()


def get_recorder(meeting_code: str) -> MeetingRecorder | None:
    return _recorders.get(meeting_code)


def start_recording(meeting_code: str, fps: int = 25,
                    width: int = 1280, height: int = 720) -> str:
    """Start a recording for a meeting. Returns output path."""
    with _registry_lock:
        if meeting_code in _recorders and _recorders[meeting_code].is_running:
            return _recorders[meeting_code].output_path
        recorder = MeetingRecorder(meeting_code, fps, width, height)
        path = recorder.start()
        _recorders[meeting_code] = recorder
        return path


def stop_recording(meeting_code: str) -> str | None:
    """Stop and finalize a meeting recording. Returns output path."""
    with _registry_lock:
        recorder = _recorders.pop(meeting_code, None)
    if recorder:
        return recorder.stop()
    return None


def write_frame_to_recording(meeting_code: str, frame: np.ndarray):
    """Write a frame to an active recording (non-blocking)."""
    recorder = _recorders.get(meeting_code)
    if recorder and recorder.is_running:
        recorder.write_frame(frame)
