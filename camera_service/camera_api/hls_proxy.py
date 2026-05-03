import subprocess
import os
import tempfile
import threading
import time
import logging
import shutil

logger = logging.getLogger('camera_api.hls_proxy')

# Use a more permanent directory for recordings
RECORDINGS_DIR = os.path.join(tempfile.gettempdir(), 'edumi_recordings')
HLS_DIR = os.path.join(tempfile.gettempdir(), 'edumi_hls')
MAX_CONCURRENT_STREAMS = 10  # Prevent CPU exhaustion

os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(HLS_DIR, exist_ok=True)

class HLSStreamer:
    """Uses FFmpeg to proxy an RTSP/HTTP/RTMP stream into HLS segments and chunks"""
    def __init__(self, camera_id, url, is_live_class=False):
        self.camera_id = str(camera_id)
        self.url = url
        self.is_live_class = is_live_class
        
        # HLS directory (temporary segments for live viewing)
        self.output_dir = os.path.join(HLS_DIR, self.camera_id)
        os.makedirs(self.output_dir, exist_ok=True)
        self.playlist_path = os.path.join(self.output_dir, 'stream.m3u8')
        
        # Recording directory (permanent chunks)
        self.recording_dir = os.path.join(RECORDINGS_DIR, self.camera_id)
        if self.is_live_class:
            os.makedirs(self.recording_dir, exist_ok=True)
            
        self.process = None
        self.running = False
        self.thread = None

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False
        if self.process:
            try:
                # Send terminate signal
                self.process.terminate()
                # Wait for termination, but don't block forever
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    logger.warning(f"FFmpeg {self.camera_id} did not stop gracefully. Killing...")
                    self.process.kill()
                    self.process.wait()
            except Exception as e:
                logger.error(f"Error stopping FFmpeg for {self.camera_id}: {e}")
            finally:
                self.process = None

    def _run(self):
        while self.running:
            logger.info(f"Starting FFmpeg HLS stream for {'live class' if self.is_live_class else 'camera'} {self.camera_id}")
            
            # Base command with thread capping for performance
            cmd = ['ffmpeg', '-y', '-threads', '2']
            
            # RTMP listen mode if applicable
            if self.url.startswith('rtmp://') and self.is_live_class:
                cmd += ['-listen', '1']
                
            # Input
            if self.url.startswith('rtsp://'):
                cmd += ['-rtsp_transport', 'tcp']
                
            cmd += [
                '-fflags', 'nobuffer',
                '-flags', 'low_delay',
                '-i', self.url,
            ]
            
            # Global encoding settings (low latency)
            cmd += [
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-g', '30',
                '-sc_threshold', '0',
            ]
            
            # Output 1: HLS for live viewing
            cmd += [
                '-f', 'hls',
                '-hls_time', '2',
                '-hls_list_size', '5',
                '-hls_flags', 'delete_segments+append_list',
                '-hls_segment_filename', os.path.join(self.output_dir, 'segment_%03d.ts'),
                self.playlist_path
            ]
            
            # Output 2: Chunked recording (if live class)
            if self.is_live_class:
                cmd += [
                    '-f', 'segment',
                    '-segment_time', '10',  # 10 second chunks as requested
                    '-reset_timestamps', '1',
                    '-map', '0',
                    os.path.join(self.recording_dir, 'chunk_%03d.mp4')
                ]
            
            try:
                # Use creationflags for Windows to prevent console windows popping up if needed
                # For this environment we'll stay standard
                self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.process.wait()
            except Exception as e:
                logger.error(f"FFmpeg process error for {self.camera_id}: {e}")
            
            if self.running:
                logger.warning(f"FFmpeg process for {self.camera_id} stopped unexpectedly. Restarting in 3s...")
                time.sleep(3)

class HLSProxyManager:
    """Global manager for HLS streams"""
    _lock = threading.Lock()
    _streamers = {}

    @classmethod
    def get_streamer(cls, camera_id, url, is_live_class=False):
        camera_id = str(camera_id)
        with cls._lock:
            # 1. Check if already running
            if camera_id in cls._streamers and cls._streamers[camera_id].running:
                return cls._streamers[camera_id]
                
            # 2. Check concurrency limit
            active_count = sum(1 for s in cls._streamers.values() if s.running)
            if active_count >= MAX_CONCURRENT_STREAMS:
                logger.error(f"Cannot start stream {camera_id}: Max concurrent streams ({MAX_CONCURRENT_STREAMS}) reached.")
                raise RuntimeError("Server capacity reached. Please try again later.")
            
            # 3. Start new streamer
            streamer = HLSStreamer(camera_id, url, is_live_class)
            streamer.start()
            cls._streamers[camera_id] = streamer
            return streamer
            
    @classmethod
    def stop_streamer(cls, camera_id):
        camera_id = str(camera_id)
        with cls._lock:
            if camera_id in cls._streamers:
                cls._streamers[camera_id].stop()
                del cls._streamers[camera_id]

    @classmethod
    def get_file_path(cls, camera_id, filename):
        return os.path.join(HLS_DIR, str(camera_id), filename)
    
    @classmethod
    def get_recording_chunks(cls, camera_id):
        rec_dir = os.path.join(RECORDINGS_DIR, str(camera_id))
        if not os.path.exists(rec_dir):
            return []
        return [f for f in os.listdir(rec_dir) if f.endswith('.mp4')]
