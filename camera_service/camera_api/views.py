"""Camera streaming views - isolated service"""
import subprocess
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

# Import HLS Proxy Manager
try:
    from .hls_proxy import HLSProxyManager
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from hls_proxy import HLSProxyManager

def serve_hls_file(camera_id, filename, is_mobile=False):
    """Helper to serve HLS chunks and playlist"""
    import mimetypes
    from django.http import FileResponse, Http404
    
    # Get the file path from the proxy manager
    # We use a prefix 'm_' for mobile cameras, 'l_' for live classes
    if is_mobile:
        cid = f"m_{camera_id}"
    elif filename.startswith('l_'):
        cid = str(camera_id) # live class ids are already prefixed if needed, but here we just use the camera_id string
    else:
        cid = str(camera_id)
    
    filepath = HLSProxyManager.get_file_path(cid, filename)
    
    if not os.path.exists(filepath):
        # If it's a playlist request, maybe the stream is starting up
        if filename.endswith('.m3u8'):
            time.sleep(2)
            if not os.path.exists(filepath):
                return JsonResponse({'error': 'Stream not ready yet, wait a moment'}, status=404)
        else:
            raise Http404("Segment not found")
            
    content_type, _ = mimetypes.guess_type(filepath)
    if not content_type:
        content_type = 'application/octet-stream'
        
    response = FileResponse(open(filepath, 'rb'), content_type=content_type)
    # Enable CORS for frontend players
    response['Access-Control-Allow-Origin'] = '*'
    
    # Do not cache m3u8 playlists
    if filename.endswith('.m3u8'):
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

def camera_feed(request, camera_id):
    """Serve HLS feed for RTSP cameras"""
    filename = request.GET.get('file', 'stream.m3u8')
    try:
        camera = Camera.objects.get(id=camera_id)
        if filename == 'stream.m3u8':
            # Ensure the streamer is running when playlist is requested
            full_url = camera.get_full_rtsp_url()
            HLSProxyManager.get_streamer(str(camera.id), full_url)
            
        return serve_hls_file(camera.id, filename, is_mobile=False)
    except Camera.DoesNotExist:
        return JsonResponse({'error': 'Camera not found'}, status=404)

def mobile_camera_feed(request, mobile_camera_id):
    """Serve HLS feed for Mobile cameras"""
    from mobile_cameras.models import MobileCamera
    filename = request.GET.get('file', 'stream.m3u8')
    try:
        mobile_camera = MobileCamera.objects.get(id=mobile_camera_id)
        if not mobile_camera.is_active:
            return JsonResponse({'error': 'Camera is paused'}, status=503)
            
        if filename == 'stream.m3u8':
            # Ensure streamer is running
            stream_url = mobile_camera.get_stream_url()
            HLSProxyManager.get_streamer(f"m_{mobile_camera.id}", stream_url)
            
        return serve_hls_file(mobile_camera.id, filename, is_mobile=True)
    except Exception as e:
        logger.error(f"Error in mobile_camera_feed: {e}")
        return JsonResponse({'error': str(e)}, status=500)

def test_mobile_camera(request, mobile_camera_id):
    """Test mobile camera connection"""
    from mobile_cameras.models import MobileCamera
    try:
        mobile_camera = MobileCamera.objects.get(id=mobile_camera_id)
        if not mobile_camera.is_active:
            return JsonResponse({'status': 'error', 'message': 'Camera is paused'})
        
        from cameras.utils import validate_rtsp_url
        stream_url = mobile_camera.get_stream_url()
        is_valid, message = validate_rtsp_url(stream_url, timeout=5)
        
        if is_valid:
            return JsonResponse({'status': 'success', 'message': 'Mobile camera accessible', 'url': stream_url})
        return JsonResponse({'status': 'error', 'message': message})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

def start_live_stream(request, stream_key):
    """Start listening for an RTMP stream and convert to HLS"""
    # Use a specific ID for live streams to avoid collision with camera IDs
    stream_id = f"live_{stream_key}"
    # In a real scenario, we'd use a fixed RTMP port or dynamic allocation
    # Here we'll listen on 0.0.0.0:1935 (standard) or a dynamic port
    # For simplicity, we'll use a local RTMP URL that FFmpeg will listen on
    rtmp_url = f"rtmp://0.0.0.0:1935/live/{stream_key}"
    
    try:
        HLSProxyManager.get_streamer(stream_id, rtmp_url, is_live_class=True)
        return JsonResponse({
            'status': 'success', 
            'message': 'RTMP listener started',
            'rtmp_url': f'rtmp://{request.get_host().split(":")[0]}:1935/live/{stream_key}',
            'hls_url': f'/api/live/feed/{stream_key}/?file=stream.m3u8'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def stop_live_stream(request, stream_key):
    """Stop an active live stream"""
    stream_id = f"live_{stream_key}"
    HLSProxyManager.stop_streamer(stream_id)
    return JsonResponse({'status': 'success', 'message': 'Stream stopped'})

def live_stream_feed(request, stream_key):
    """Serve HLS feed for live classes"""
    filename = request.GET.get('file', 'stream.m3u8')
    stream_id = f"live_{stream_key}"
    return serve_hls_file(stream_id, filename)
