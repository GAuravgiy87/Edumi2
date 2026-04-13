from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import admin_list_views
from . import notification_views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('accounts/dismiss-welcome/', views.dismiss_welcome, name='dismiss_welcome'),
    path('accounts/save-emoji-avatar/', views.save_emoji_avatar, name='save_emoji_avatar'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('register/', views.register, name='register'),
    path('home/', views.home, name='home'),
    path('teacher-dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/<str:username>/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('settings/', views.settings_view, name='settings'),
    path('directory/', views.directory, name='directory'),
    path('search/', views.search_users, name='search_users'),
    path('inbox/', views.inbox, name='inbox'),
    path('inbox/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('inbox/start/<str:username>/', views.start_conversation, name='start_conversation'),
    path('inbox/send/<int:conversation_id>/', views.send_message, name='send_message'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('user-management/', views.user_management, name='user_management'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('architecture/', views.architecture_view, name='architecture'),
    
    # Notification URLs
    path('notifications/', notification_views.notifications_list, name='notifications_list'),
    path('notifications/mark-read/<int:notification_id>/', notification_views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', notification_views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/unread-count/', notification_views.get_unread_count, name='get_unread_count'),
    path('notifications/recent/', notification_views.get_recent_notifications, name='get_recent_notifications'),
    path('notifications/broadcast/', notification_views.send_broadcast, name='send_broadcast'),
    
    # Admin list views
    path('admin/users/', admin_list_views.admin_all_users, name='admin_all_users'),
    path('admin/students/', admin_list_views.admin_all_students, name='admin_all_students'),
    path('admin/teachers/', admin_list_views.admin_all_teachers, name='admin_all_teachers'),
    path('admin/meetings/', admin_list_views.admin_all_meetings, name='admin_all_meetings'),
    path('admin/live-meetings/', admin_list_views.admin_live_meetings, name='admin_live_meetings'),
]
