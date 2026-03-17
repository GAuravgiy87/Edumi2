"""
ASGI config for school_project project.
Optimized for production with Gunicorn + Uvicorn.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_project.settings')

# Setup Django before importing models
# This is crucial for Gunicorn preloading to work correctly
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from meetings.routing import websocket_urlpatterns as meeting_ws
from attendance.routing import websocket_urlpatterns as attendance_ws

# Combine all WebSocket URL patterns
all_websocket_urlpatterns = meeting_ws + attendance_ws

# Get HTTP application
django_asgi_app = get_asgi_application()

# Production-optimized ASGI application
# - AllowedHostsOriginValidator for security
# - AuthMiddlewareStack for authentication
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(all_websocket_urlpatterns)
        )
    ),
})
