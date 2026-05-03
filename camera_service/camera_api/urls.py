"""Camera API URLs"""
from django.urls import path
from . import views

urlpatterns = [
    # RTSP Cameras
    path('cameras/', views.list_cameras, name='list_cameras'),
    path('cameras/<int:camera_id>/feed/', views.camera_feed, name='camera_feed'),
    path('cameras/<int:camera_id>/test/', views.test_camera, name='test_camera'),
    
    # Mobile Cameras
    path('mobile-cameras/<int:mobile_camera_id>/feed/', views.mobile_camera_feed, name='mobile_camera_feed'),
    path('mobile-cameras/<int:mobile_camera_id>/test/', views.test_mobile_camera, name='test_mobile_camera'),
    
    # Live Streams (RTMP Ingest)
    path('live-class/start/<str:stream_key>/', views.start_live_stream, name='start_live_stream'),
    path('live-class/stop/<str:stream_key>/', views.stop_live_stream, name='stop_live_stream'),
    path('live/feed/<str:stream_key>/', views.live_stream_feed, name='live_stream_feed'),
]
