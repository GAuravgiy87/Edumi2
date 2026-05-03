from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/live-class/<str:stream_key>/', consumers.LiveClassConsumer.as_asgi()),
]
