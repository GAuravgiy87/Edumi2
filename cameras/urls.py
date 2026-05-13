from django.urls import path
from . import views

urlpatterns = [
    # RTSP Camera URLs
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('add-camera/', views.add_camera, name='add_camera'),
    path('edit-camera/<int:camera_id>/', views.edit_camera, name='edit_camera'),
    path('delete-camera/<int:camera_id>/', views.delete_camera, name='delete_camera'),
    path('teacher-dashboard/', views.teacher_camera_dashboard, name='teacher_camera_dashboard'),
    path('control-room/<int:camera_id>/', views.teacher_control_room, name='teacher_control_room'),
    path('start-streaming/<int:camera_id>/', views.start_streaming, name='start_streaming'),
    path('stop-streaming/<int:camera_id>/', views.stop_streaming, name='stop_streaming'),
    path('start-recording/<int:camera_id>/', views.start_camera_recording, name='start_camera_recording'),
    path('stop-recording/<int:camera_id>/', views.stop_camera_recording, name='stop_camera_recording'),
    path('publish-recording/', views.publish_recording, name='publish_recording'),
    path('live-participants/<int:camera_id>/', views.live_participants, name='live_participants'),
    
    # Student Side
    path('lectures/', views.student_lecture_list, name='student_lecture_list'),
    path('watch-live/<int:camera_id>/', views.watch_live, name='watch_live'),
    path('watch-recording/<int:recording_id>/', views.watch_recording, name='watch_recording'),
    path('teacher/<int:teacher_id>/', views.teacher_profile, name='teacher_profile'),

    path('camera-feed/<int:camera_id>/', views.camera_feed, name='camera_feed'),
    path('test-camera/<int:camera_id>/', views.test_camera, name='test_camera'),
    path('test-feed/', views.test_feed_page, name='test_feed_page'),
    path('live-monitor/', views.live_monitor, name='live_monitor'),
    path('grant-permission/<int:camera_id>/', views.grant_permission, name='grant_permission'),
    path('revoke-permission/<int:camera_id>/<int:teacher_id>/', views.revoke_permission, name='revoke_permission'),
    path('manage-permissions/<int:camera_id>/', views.manage_permissions, name='manage_permissions'),
    
    # Head Counting URLs
    path('head-count/', views.head_count_dashboard, name='head_count_dashboard'),
    path('head-count/start/<str:camera_type>/<int:camera_id>/', views.start_head_count, name='start_head_count'),
    path('head-count/stop/<str:camera_type>/<int:camera_id>/', views.stop_head_count, name='stop_head_count'),
    path('head-count/logs/', views.head_count_logs, name='head_count_logs'),
    path('head-count/logs/<int:log_id>/', views.head_count_log_detail, name='head_count_log_detail'),
    path('head-count/sessions/', views.head_count_session_history, name='head_count_session_history'),
    path('head-count/api/<str:camera_type>/<int:camera_id>/', views.head_count_api, name='head_count_api'),
    path('head-count/report/', views.head_count_report, name='head_count_report'),
    path('head-count/export/', views.export_head_count_csv, name='export_head_count_csv'),
]
