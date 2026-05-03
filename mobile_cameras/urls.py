from django.urls import path
from . import views

app_name = 'mobile_cameras'

urlpatterns = [
    path('dashboard/', views.mobile_camera_dashboard, name='dashboard'),
    path('add/', views.add_mobile_camera, name='add'),
    path('delete/<int:mobile_camera_id>/', views.delete_mobile_camera, name='delete'),
    path('feed/<int:mobile_camera_id>/', views.mobile_camera_feed, name='feed'),
    path('view/<int:mobile_camera_id>/', views.view_mobile_camera, name='view'),
    path('live-monitor/', views.live_monitor, name='live_monitor'),
    path('test/<int:mobile_camera_id>/', views.test_mobile_camera, name='test'),
    path('grant-permission/<int:mobile_camera_id>/', views.grant_permission, name='grant_permission'),
    path('revoke-permission/<int:mobile_camera_id>/<int:teacher_id>/', views.revoke_permission, name='revoke_permission'),
    path('manage-permissions/<int:mobile_camera_id>/', views.manage_permissions, name='manage_permissions'),
]
