"""
ASGI config for school_project project.
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_project.settings')

# get_asgi_application() MUST be called first — it initialises the app registry.
# All Django model imports (consumers, routing) must come AFTER this line.
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from meetings.routing import websocket_urlpatterns as meeting_ws
from attendance.routing import websocket_urlpatterns as attendance_ws

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(meeting_ws + attendance_ws)
    ),
})
