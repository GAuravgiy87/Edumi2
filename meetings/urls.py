from django.urls import path
from . import views

urlpatterns = [
    # Classroom Management
    path('classroom/create/', views.create_classroom, name='create_classroom'),
    path('classroom/teacher/', views.teacher_classrooms, name='teacher_classrooms'),
    path('classroom/student/', views.student_classrooms, name='student_classrooms'),
    path('classroom/<int:classroom_id>/', views.classroom_detail, name='classroom_detail'),
    path('classroom/join/', views.join_classroom_request, name='join_classroom_request'),
    path('classroom/approve/<int:membership_id>/', views.approve_join_request, name='approve_join_request'),
    path('classroom/deny/<int:membership_id>/', views.deny_join_request, name='deny_join_request'),
    path('classroom/remove/<int:membership_id>/', views.remove_student, name='remove_student'),
    path('classroom/<int:classroom_id>/delete/', views.delete_classroom, name='delete_classroom'),
    path('classroom/<int:classroom_id>/leave/', views.leave_classroom, name='leave_classroom'),
    path('classroom/<int:classroom_id>/start-meeting/', views.start_classroom_meeting, name='start_classroom_meeting'),
    
    # Meeting Management (Legacy)
    path('create/', views.create_meeting, name='create_meeting'),
    path('teacher/', views.teacher_meetings, name='teacher_meetings'),
    path('student/', views.student_meetings, name='student_meetings'),
    path('join/<str:meeting_code>/', views.join_meeting, name='join_meeting'),
    path('token/<str:meeting_code>/', views.livekit_token, name='livekit_token'),
    path('end/<int:meeting_id>/', views.end_meeting, name='end_meeting'),
    path('leave/<int:meeting_id>/', views.leave_meeting, name='leave_meeting'),
    path('participants/<int:meeting_id>/', views.get_participants, name='get_participants'),
    path('delete/<int:meeting_id>/', views.delete_meeting, name='delete_meeting'),
    path('cancel/<int:meeting_id>/', views.cancel_meeting, name='cancel_meeting'),
    path('attendance/<str:meeting_code>/', views.meeting_attendance, name='meeting_attendance'),
    path('summary/<str:meeting_code>/', views.meeting_summary, name='meeting_summary'),
    
    # Meeting Sleep Mode
    path('sleep/<str:meeting_code>/', views.sleep_meeting, name='sleep_meeting'),
    path('unfreeze/<str:meeting_code>/', views.unfreeze_meeting, name='unfreeze_meeting'),
    path('status/<str:meeting_code>/', views.get_meeting_status, name='get_meeting_status'),
    path('prep/<str:meeting_code>/', views.pre_join, name='pre_join'),
    path('verify-prejoin/', views.verify_face_prejoin, name='verify_face_prejoin'),
    
    # Teacher Controls
    path('kick/<int:meeting_id>/<int:user_id>/', views.kick_participant, name='kick_participant'),
    path('permissions/<int:meeting_id>/<int:user_id>/', views.update_participant_permission, name='update_participant_permission'),
    path('global-control/<int:meeting_id>/', views.toggle_global_control, name='toggle_global_control'),
    path('revoke-ban/<int:meeting_id>/<int:user_id>/', views.revoke_ban, name='revoke_ban'),
    path('banned-users/<int:meeting_id>/', views.get_banned_users, name='get_banned_users'),
]
