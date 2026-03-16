from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r'ws/attendance/(?P<meeting_code>\w+)/$',
        consumers.FaceAttendanceConsumer.as_asgi()
    ),
]
