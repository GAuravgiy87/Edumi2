import subprocess
import os
import tempfile
import threading
import time
import logging
import glob

logger = logging.getLogger('camera_api.hls_proxy')

HLS_DIR = os.path.join(tempfile.gettempdir(), 'edumi_hls')
RECORDINGS_DIR = os.path.join(tempfile.gettempdir(), 'edumi_recordings')
MAX_CONCURRENT_STREAMS = 10

# Live-only HLS settings
HLS_SEGMENT_SECONDS = 2      # Each segment = 2 s
HLS_LIST_SIZE       = 3      # Playlist keeps only 3 segments (= ~6 s live window)
IDLE_STOP_SECONDS   = 30     # Stop FFmpeg if no viewer requests for this long

os.makedirs(HLS_DIR, exist_ok=True)
os.makedirs(RECORDINGS_DIR, exist_ok=True)


class HLSStreamer:
    """
    Converts an RTSP/HTTP/RTMP stream to a tiny rolling HLS window.

    Design goals:
    - NO re-encoding  → copy codec, near-zero CPU
    - Rolling window  → only 3 segments on disk at any time (~6 s)
    - No recording    → segments are deleted as soon as they leave the window
    - Idle shutdown   → FFmpeg stops after IDLE_STOP_SECONDS with no viewers
    """

    def __init__(self, camera_id, url, is_live_class=False):
        self.camera_id    = str(camera_id)
        self.url          = url
        self.is_live_class = is_live_class

        self.output_dir    = os.path.join(HLS_DIR, self.camera_id)
        self.playlist_path = os.path.join(self.output_dir, 'stream.m3u8')
        os.makedirs(self.output_dir, exist_ok=True)

        # Recording only for live-class streams
        self.recording_dir = os.path.join(RECORDINGS_DIR, self.camera_id)
        if self.is_live_class:
            os.makedirs(self.recording_dir, exist_ok=True)

        self.process      = None
        self.running      = False
        self.thread       = None
        self._last_access = time.time()   # updated on every segment/manifest request
        self._lock        = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────

    def start(self):
        with self._lock:
            if not self.running:
                self.running = True
                self.thread = threading.Thread(target=self._run, daemon=True)
                self.thread.start()

    def stop(self):
        with self._lock:
            self.running = False
        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            except Exception as e:
                logger.error(f"Error stopping FFmpeg {self.camera_id}: {e}")
            finally:
                self.process = None
        self._cleanup_segments()

    def touch(self):
        """Call this on every viewer request to reset the idle timer."""
        self._last_access = time.time()

    # ── Internal ──────────────────────────────────────────────────────────

    def _cleanup_segments(self):
        """Delete all .ts segments and the playlist for this stream."""
        try:
            for f in glob.glob(os.path.join(self.output_dir, '*.ts')):
                os.remove(f)
            if os.path.exists(self.playlist_path):
                os.remove(self.playlist_path)
        except Exception:
            pass

    def _build_ffmpeg_cmd(self):
        cmd = [
            'ffmpeg', '-y',
            '-loglevel', 'warning',   # only warnings/errors to stderr
        ]

        # ── Input ──────────────────────────────────────────────────────────
        if self.url.startswith('rtmp://') and self.is_live_class:
            cmd += ['-listen', '1']

        if self.url.startswith('rtsp://'):
            cmd += [
                '-rtsp_transport', 'tcp',
                '-stimeout', '5000000',   # 5 s connection timeout (µs)
            ]

        cmd += [
            '-fflags', 'nobuffer+discardcorrupt',
            '-flags', 'low_delay',
            '-i', self.url,
        ]

        # ── Video: copy stream directly — NO re-encoding ───────────────────
        # This is the single biggest CPU saving. The RTSP camera already
        # sends H.264; we just remux it into .ts containers.
        cmd += [
            '-c:v', 'copy',
            '-c:a', 'copy',            # copy audio too (or 'an' to drop audio)
            '-vsync', '0',
        ]

        # ── HLS output: rolling live window, delete old segments ───────────
        cmd += [
            '-f', 'hls',
            '-hls_time',     str(HLS_SEGMENT_SECONDS),
            '-hls_list_size', str(HLS_LIST_SIZE),
            '-hls_flags',    'delete_segments+omit_endlist+split_by_time',
            # Wrap segment counter at 999 so filenames stay short
            '-hls_segment_filename', os.path.join(self.output_dir, 'seg%03d.ts'),
            self.playlist_path,
        ]

        # ── Optional: 10-second recording chunks for live classes only ─────
        if self.is_live_class:
            cmd += [
                '-f', 'segment',
                '-segment_time', '10',
                '-reset_timestamps', '1',
                '-map', '0',
                os.path.join(self.recording_dir, 'chunk_%03d.mp4'),
            ]

        return cmd

    def _run(self):
        while self.running:
            logger.info(f"[FFmpeg] Starting stream {self.camera_id}")
            self._cleanup_segments()   # fresh start each time

            cmd = self._build_ffmpeg_cmd()

            try:
                # Hide console window on Windows
                kwargs = {}
                if os.name == 'nt':
                    import ctypes
                    kwargs['creationflags'] = 0x08000000  # CREATE_NO_WINDOW

                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **kwargs,
                )

                # Poll: check idle timeout while FFmpeg runs
                while self.running:
                    ret = self.process.poll()
                    if ret is not None:
                        # FFmpeg exited on its own
                        break
                    idle = time.time() - self._last_access
                    if idle > IDLE_STOP_SECONDS:
                        logger.info(
                            f"[FFmpeg] Stream {self.camera_id} idle for "
                            f"{idle:.0f}s — stopping"
                        )
                        self.running = False
                        self.process.terminate()
                        try:
                            self.process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            self.process.kill()
                        break
                    time.sleep(2)

            except Exception as e:
                logger.error(f"[FFmpeg] Process error {self.camera_id}: {e}")
            finally:
                self.process = None

            if self.running:
                logger.warning(
                    f"[FFmpeg] Stream {self.camera_id} stopped unexpectedly — "
                    f"restarting in 3 s"
                )
                time.sleep(3)

        self._cleanup_segments()
        logger.info(f"[FFmpeg] Stream {self.camera_id} shut down cleanly")


class HLSProxyManager:
    """Global manager — one HLSStreamer per camera."""

    _lock      = threading.Lock()
    _streamers = {}

    @classmethod
    def get_streamer(cls, camera_id, url, is_live_class=False):
        camera_id = str(camera_id)
        with cls._lock:
            s = cls._streamers.get(camera_id)
            if s and s.running:
                s.touch()
                return s

            # Enforce concurrency cap
            active = sum(1 for x in cls._streamers.values() if x.running)
            if active >= MAX_CONCURRENT_STREAMS:
                raise RuntimeError("Server capacity reached. Please try again later.")

            s = HLSStreamer(camera_id, url, is_live_class)
            s.start()
            cls._streamers[camera_id] = s
            return s

    @classmethod
    def touch_streamer(cls, camera_id):
        """Reset idle timer without starting a new stream."""
        camera_id = str(camera_id)
        with cls._lock:
            s = cls._streamers.get(camera_id)
            if s:
                s.touch()

    @classmethod
    def stop_streamer(cls, camera_id):
        camera_id = str(camera_id)
        with cls._lock:
            s = cls._streamers.pop(camera_id, None)
        if s:
            s.stop()

    @classmethod
    def get_file_path(cls, camera_id, filename):
        return os.path.join(HLS_DIR, str(camera_id), filename)

    @classmethod
    def get_recording_chunks(cls, camera_id):
        rec_dir = os.path.join(RECORDINGS_DIR, str(camera_id))
        if not os.path.exists(rec_dir):
            return []
        return [f for f in os.listdir(rec_dir) if f.endswith('.mp4')]

    @classmethod
    def active_streams(cls):
        with cls._lock:
            return {k: v.url for k, v in cls._streamers.items() if v.running}
