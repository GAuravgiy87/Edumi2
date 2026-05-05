import subprocess
import secrets
import logging
from django.utils import timezone
from datetime import timedelta
from urllib.parse import quote, urlparse
from .models import StreamToken

logger = logging.getLogger('cameras.utils')

def validate_rtsp_url(url, timeout=5):
    """
    Validate if an RTSP or HTTP stream is reachable using ffprobe.
    Returns (is_valid, error_message)
    """
    try:
        cmd = [
            'ffprobe', '-v', 'error', 
            '-timeout', str(timeout * 1000000), # microseconds
            '-show_entries', 'stream=codec_type',
            '-of', 'csv=p=0',
            url
        ]
        # Add TCP transport for RTSP
        if url.startswith('rtsp://'):
            cmd.insert(3, '-rtsp_transport')
            cmd.insert(4, 'tcp')
            
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+2)
        if result.returncode == 0 and 'video' in result.stdout:
            return True, "Valid"
        return False, result.stderr.strip() or "No video stream found"
    except subprocess.TimeoutExpired:
        return False, "Connection timed out"
    except Exception as e:
        return False, str(e)

def auto_detect_stream_path(ip, port, username, password, protocol='rtsp'):
    """
    Unified path detection for both RTSP and HTTP cameras using ffprobe.
    For RTSP cameras, also tries HTTP paths since many IP cameras serve
    video over HTTP (MJPEG/H264) even when they also support RTSP.
    """
    if protocol == 'rtsp':
        # Try RTSP paths first
        rtsp_paths = [
            '/stream', '/live', '/h264', '/video', '/cam/realmonitor',
            '/Streaming/Channels/101', '/Streaming/Channels/1',
            '/1', '/11', '/av0_0', '/mpeg4',
            '/media/video1', '/onvif1', '/ch0', '/ch01.264',
            '/videoMain', '/video1', '/live/ch00_0',
            '/live/main', '/live/sub', '/live0', '/live1',
            '/',
        ]
        # Also try HTTP paths — many IP cameras (Hikvision, Dahua, generic)
        # serve MJPEG or H264 over HTTP even when RTSP is also available
        http_paths = [
            '/video', '/mjpeg', '/mjpegfeed', '/videostream.cgi',
            '/video.mjpg', '/video.cgi', '/cgi-bin/video.cgi',
            '/cgi-bin/mjpeg', '/snap.jpg', '/image.jpg',
            '/cgi-bin/viewer/video.jpg', '/GetData.cgi',
            '/videoMain', '/video1.mjpeg',
        ]

        # Try RTSP first
        for path in rtsp_paths:
            url = _build_url('rtsp://', ip, port, username, password, path)
            is_valid, _ = validate_rtsp_url(url, timeout=3)
            if is_valid:
                return path, url

        # Fall back to HTTP on port 80 (or the given port if it's not 554)
        http_port = 80 if port == 554 else port
        for path in http_paths:
            url = _build_url('http://', ip, http_port, username, password, path)
            is_valid, _ = validate_rtsp_url(url, timeout=3)
            if is_valid:
                return path, url

        return None, None

    else:  # http/mobile
        common_paths = [
            '/video', '/mjpegfeed', '/videofeed', '/cam_1.mjpg',
            '/stream', '/video.mjpg', '/video.cgi', '/',
        ]
        for path in common_paths:
            url = _build_url('http://', ip, port, username, password, path)
            is_valid, _ = validate_rtsp_url(url, timeout=3)
            if is_valid:
                return path, url

        return None, None


def _build_url(prefix, ip, port, username, password, path):
    # Omit default ports so the URL is clean and standard
    default_port = 554 if prefix == 'rtsp://' else 80
    host = f"{ip}:{port}" if port != default_port else ip
    if username and password:
        safe_user = quote(username)
        safe_pass = quote(password)
        return f"{prefix}{safe_user}:{safe_pass}@{host}{path}"
    return f"{prefix}{host}{path}"

def parse_stream_url(url):
    """
    Unified URL parser for RTSP and HTTP streams.
    Handles complex passwords and extracts all components.
    """
    if url.startswith('rtsp://'):
        scheme = 'rtsp'
        temp = url[7:]
    elif url.startswith('http://'):
        scheme = 'http'
        temp = url[7:]
    else:
        # Fallback to standard urlparse
        parsed = urlparse(url)
        return {
            'ip_address': parsed.hostname,
            'port': parsed.port,
            'username': parsed.username or '',
            'password': parsed.password or '',
            'stream_path': parsed.path or '/',
            'scheme': parsed.scheme
        }

    # Custom parsing for complex credentials
    if '@' in temp:
        userinfo, rest = temp.rsplit('@', 1)
        if ':' in userinfo:
            username, password = userinfo.split(':', 1)
        else:
            username = userinfo
            password = ''
    else:
        username = ''
        password = ''
        rest = temp
    
    if '/' in rest:
        hostport, stream_path = rest.split('/', 1)
        stream_path = '/' + stream_path
    else:
        hostport = rest
        stream_path = '/'
    
    if ':' in hostport:
        ip_address, port = hostport.split(':', 1)
        try:
            port = int(port)
        except ValueError:
            port = 554 if scheme == 'rtsp' else 80
    else:
        ip_address = hostport
        port = 554 if scheme == 'rtsp' else 80
    
    return {
        'ip_address': ip_address,
        'port': port,
        'username': username,
        'password': password,
        'stream_path': stream_path,
        'scheme': scheme
    }

def generate_stream_token(user, camera_id):
    """Generate a temporary access token for a stream"""
    token = secrets.token_urlsafe(32)
    expires_at = timezone.now() + timedelta(hours=4)
    
    StreamToken.objects.create(
        token=token,
        user=user,
        camera_id=str(camera_id),
        expires_at=expires_at
    )
    return token

def verify_stream_token(token_str, camera_id):
    """Verify if a token is valid for a specific camera"""
    try:
        token = StreamToken.objects.get(token=token_str)
        if token.is_valid() and token.camera_id == str(camera_id):
            return True
        return False
    except StreamToken.DoesNotExist:
        return False

def is_admin(user):
    """Common admin check utility"""
    return user.is_authenticated and user.is_superuser
