"""
Camera Service ASGI/SSL entry point using Daphne.
"""
import os
import sys
from pathlib import Path

# Add project root and camera_service directory to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR.parent))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'camera_service.settings')

import django
django.setup()

from daphne.server import Server
from camera_service.asgi import application

if __name__ == '__main__':
    port = int(os.environ.get('CAMERA_SERVICE_PORT', 8003))
    bind = "0.0.0.0"
    
    # SSL cert configuration
    cert_file = BASE_DIR.parent / "certs" / "edumi.crt"
    key_file  = BASE_DIR.parent / "certs" / "edumi.key"
    
    if cert_file.exists() and key_file.exists():
        # Relative paths (forward slashes) to avoid Twisted endpoint colon conflicts on Windows
        cert_rel = str(cert_file.relative_to(BASE_DIR.parent)).replace("\\", "/")
        key_rel  = str(key_file.relative_to(BASE_DIR.parent)).replace("\\", "/")
        
        # Change working directory so relative paths resolve correctly
        os.chdir(str(BASE_DIR.parent))
        
        ssl_endpoint = (
            f"ssl:port={port}:interface={bind}"
            f":certKey={cert_rel}:privateKey={key_rel}"
        )
        print(f"Camera Service starting on HTTPS/WSS 0.0.0.0:{port} (daphne, SSL enabled)")
        
        server = Server(
            application=application,
            endpoints=[ssl_endpoint],
            signal_handlers=True,
            http_timeout=86400,
            websocket_timeout=86400,
            verbosity=0,
        )
    else:
        # Fallback to plain HTTP if certs don't exist
        print(f"SSL certs not found. Camera Service starting on http://0.0.0.0:{port} (daphne, HTTP)")
        server = Server(
            application=application,
            endpoints=[f"tcp:port={port}:interface={bind}"],
            signal_handlers=True,
            http_timeout=86400,
            websocket_timeout=86400,
            verbosity=0,
        )
        
    server.run()
