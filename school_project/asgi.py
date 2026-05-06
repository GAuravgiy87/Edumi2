"""
ASGI config for school_project project.
"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_project.settings')

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path
from meetings.routing import websocket_urlpatterns as meeting_ws
from attendance.routing import websocket_urlpatterns as attendance_ws
from accounts.routing import websocket_urlpatterns as account_ws
from cameras.routing import websocket_urlpatterns as camera_ws
from meetings.livekit_proxy import LiveKitProxyConsumer


# ── LiveKit proxy patterns (no auth needed — token is in query string) ────────
livekit_patterns = [
    re_path(r'^livekit-proxy(?P<lk_path>/.+)$', LiveKitProxyConsumer.as_asgi()),
    re_path(r'^livekit-proxy/?$',               LiveKitProxyConsumer.as_asgi()),
]


class AllowAllHostsMiddleware:
    """
    ASGI middleware that strips the Host header validation for WebSocket
    connections. Django Channels does not run SecurityMiddleware for WS,
    but Daphne itself can reject connections with unknown Host headers.
    This middleware rewrites the scope host to 'localhost' so Daphne
    always accepts the upgrade, regardless of the incoming Host header
    (ngrok, LAN IP, domain, etc.).
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            # Accept any host for WebSocket — security is handled by token auth
            scope = dict(scope)
            headers = dict(scope.get('headers', []))
            headers[b'host'] = b'localhost'
            scope['headers'] = list(headers.items())
        return await self.inner(scope, receive, send)


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowAllHostsMiddleware(
        URLRouter(
            livekit_patterns + [
                re_path(r'', AuthMiddlewareStack(
                    URLRouter(meeting_ws + attendance_ws + account_ws + camera_ws)
                )),
            ]
        )
    ),
})
