from django.urls import path
from . import views

urlpatterns = [
    path('video/<int:video_id>/', views.edit_video, name='edit_video'),
    path('session/<int:session_id>/add-action/', views.add_edit_action, name='add_edit_action'),
    path('action/<int:action_id>/remove/', views.remove_edit_action, name='remove_edit_action'),
    path('session/<int:session_id>/process/', views.process_edits, name='process_edits'),
    path('session/<int:session_id>/download/', views.download_edited_video, name='download_edited_video'),
]