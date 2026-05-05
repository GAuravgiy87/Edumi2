"""
Camera Service Process Manager
Starts and stops the camera service (port 8001) alongside the main Django app.
Called from CamerasConfig.ready() so it runs once when Django starts.
"""
import subprocess
import sys
import os
import time
import logging
import atexit
import threading

logger = logging.getLogger('cameras')

_process = None
_lock    = threading.Lock()


def _find_python():
    """Return the same Python executable that's running the main app."""
    return sys.executable


def is_running():
    """Check if camera service is already listening on port 8001."""
    import socket
    try:
        with socket.create_connection(('127.0.0.1', 8001), timeout=1):
            return True
    except OSError:
        return False


def start():
    """Start the camera service as a subprocess if not already running."""
    global _process

    with _lock:
        if is_running():
            logger.info('[CameraService] Already running on :8001 — skipping start')
            return

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        manage_py = os.path.join(base_dir, 'camera_service', 'manage.py')

        if not os.path.exists(manage_py):
            logger.warning('[CameraService] manage.py not found — camera service will not start')
            return

        kwargs = {}
        if os.name == 'nt':
            # Windows: hide the console window
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

        _process = subprocess.Popen(
            [_find_python(), manage_py, 'runserver', '0.0.0.0:8001', '--noreload'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )
        logger.info(f'[CameraService] Started (PID {_process.pid}) on :8001')

        # Register cleanup so it stops when main app exits
        atexit.register(stop)


def stop():
    """Terminate the camera service subprocess."""
    global _process
    with _lock:
        if _process and _process.poll() is None:
            logger.info(f'[CameraService] Stopping PID {_process.pid}')
            _process.terminate()
            try:
                _process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _process.kill()
            _process = None
            logger.info('[CameraService] Stopped')
