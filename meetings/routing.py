from django.urls import re_path
from . import consumers
from .classroom_consumer import ClassroomConsumer

websocket_urlpatterns = [
    re_path(r'^ws/meeting/(?P<meeting_code>\w+)/$', consumers.MeetingConsumer.as_asgi()),
    re_path(r'^ws/classroom/(?P<classroom_id>\d+)/$', ClassroomConsumer.as_asgi()),
]
