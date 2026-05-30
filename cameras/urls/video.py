
from django.urls import path
from .. import views

urlpatterns = [
    path('toggle-publish/<int:recording_id>/', views.toggle_recording_publish, name='toggle_recording_publish'),
    path('manage-recordings/', views.manage_recordings, name='manage_recordings'),
    path('recordings-folder/', views.recordings_folder, name='recordings_folder'),
    path('upload-video/', views.upload_video, name='upload_video'),
    path('stream-video/<int:recording_id>/', views.stream_video, name='stream_video'),
    path('recording-playlist/<int:recording_id>/', views.recording_playlist, name='recording_playlist'),
    path('stream-chunk/<int:recording_id>/<int:sequence>/', views.stream_recording_chunk, name='stream_chunk'),
    path('watch-recording/<int:recording_id>/', views.watch_recording, name='watch_recording'),
    path('teacher/<int:teacher_id>/', views.teacher_profile, name='teacher_profile'),
]
