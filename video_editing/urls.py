from django.urls import path

from . import views

urlpatterns = [
    # Projects
    path("", views.project_list, name="project_list"),
    path("upload/", views.project_list, name="project_upload"),  # kept for back-compat, handled by project_list
    path("project/<int:pk>/", views.project_detail, name="project_detail"),
    path("project/<int:pk>/delete/", views.project_delete, name="project_delete"),
    path("project/<int:pk>/download/", views.project_download, name="project_download"),
    path("project/<int:pk>/download/mkv/", views.project_download_mkv, name="project_download_mkv"),
    path("project/<int:pk>/status/", views.project_status, name="project_status"),

    # Edit operations
    path("project/<int:pk>/trim/", views.op_trim, name="op_trim"),
    path("project/<int:pk>/mute/", views.op_mute, name="op_mute"),
    path("project/<int:pk>/volume/", views.op_volume, name="op_volume"),
    path("project/<int:pk>/merge/", views.op_merge, name="op_merge"),
    path("project/<int:pk>/text/", views.op_text_overlay, name="op_text_overlay"),
    path("project/<int:pk>/speed/", views.op_speed, name="op_speed"),
    path("project/<int:pk>/rotate/", views.op_rotate, name="op_rotate"),
    path("project/<int:pk>/resize/", views.op_resize, name="op_resize"),
    path("project/<int:pk>/grayscale/", views.op_grayscale, name="op_grayscale"),
    path("project/<int:pk>/fade/", views.op_fade, name="op_fade"),
    path("project/<int:pk>/reset/", views.op_reset, name="op_reset"),
    path("project/<int:pk>/export/", views.export_project, name="export_project"),
    path("project/<int:pk>/background-audio/", views.op_background_audio, name="op_background_audio"),
    path("project/<int:pk>/upload-audio/", views.upload_audio_temp, name="upload_audio_temp"),
]
