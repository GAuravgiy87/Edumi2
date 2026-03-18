"""
ASGI config for school_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_project.settings')

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from meetings.routing import websocket_urlpatterns as meeting_ws
from attendance.routing import websocket_urlpatterns as attendance_ws

# Combine all WebSocket URL patterns
all_websocket_urlpatterns = meeting_ws + attendance_ws

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            all_websocket_urlpatterns
        )
    ),
})
