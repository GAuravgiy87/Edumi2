from django.urls import path

from . import views

urlpatterns = [
    # Projects
    path("", views.project_list, name="project_list"),
    path("upload/", views.project_list, name="project_upload"),  # kept for back-compat
    path("chunked-upload/", views.chunked_upload_view, name="chunked_upload"),
    path("project/<int:pk>/", views.project_detail, name="project_detail"),
    path("project/<int:pk>/proxy-status/", views.proxy_status_view, name="proxy_status"),
    path("project/<int:pk>/delete/", views.project_delete, name="project_delete"),
    path("project/<int:pk>/download/", views.project_download, name="project_download"),
    path("project/<int:pk>/download/mkv/", views.project_download_mkv, name="project_download_mkv"),
    path("project/<int:pk>/status/", views.project_status, name="project_status"),

    # Media range requests for smooth timeline scrubbing
    path("media-ranges/<path:path>", views.serve_media_ranges, name="serve_media_ranges"),

    # Edit operations
    path("project/<int:pk>/reset/", views.op_reset, name="op_reset"),
    path("project/<int:pk>/export/", views.export_project, name="export_project"),
    path("project/<int:pk>/publish/", views.publish_to_lecture, name="publish_to_lecture"),
    path("project/<int:pk>/upload-audio/", views.upload_audio_temp, name="upload_audio_temp"),
    path("project/<int:pk>/upload-asset/", views.upload_asset, name="upload_asset"),
    
    # Timeline JSON endpoints (retained for backward compatibility)
    path("project/<int:pk>/save-timeline/", views.save_timeline, name="save_timeline"),
    path("project/<int:pk>/export-timeline/", views.export_timeline, name="export_timeline"),
]
