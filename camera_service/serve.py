"""
Camera Service WSGI entry point using Waitress.

Waitress is a production-quality pure-Python WSGI server that:
- Works on Windows (unlike gunicorn)
- Handles multiple concurrent requests via threads
- Is required for MJPEG streaming (each stream holds a connection open indefinitely)

Usage:
    python camera_service/serve.py
"""
import os
import sys

# Add the camera_service directory to path so Django can find its settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(BASE_DIR))  # main project root

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'camera_service.settings')

import django
django.setup()

from waitress import serve
from camera_service.wsgi import application

if __name__ == '__main__':
    port = int(os.environ.get('CAMERA_SERVICE_PORT', 8003))
    # threads=16 allows up to 16 concurrent MJPEG streams + other requests
    print(f"Camera Service starting on http://0.0.0.0:{port} (waitress, 16 threads)")
    serve(application, host='0.0.0.0', port=port, threads=16)
