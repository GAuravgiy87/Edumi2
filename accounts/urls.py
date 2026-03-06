from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import admin_list_views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('home/', views.home, name='home'),
    path('teacher-dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/<str:username>/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
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
    
    # Admin list views
    path('admin/users/', admin_list_views.admin_all_users, name='admin_all_users'),
    path('admin/students/', admin_list_views.admin_all_students, name='admin_all_students'),
    path('admin/teachers/', admin_list_views.admin_all_teachers, name='admin_all_teachers'),
    path('admin/meetings/', admin_list_views.admin_all_meetings, name='admin_all_meetings'),
    path('admin/live-meetings/', admin_list_views.admin_live_meetings, name='admin_live_meetings'),
    path('admin/cameras/', admin_list_views.admin_all_cameras, name='admin_all_cameras'),
]
