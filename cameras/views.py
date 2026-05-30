
from django.contrib.auth.decorators import login_required
from .views_logic import (
    get_video_stream,
    is_admin,
    can_view_camera,
    test_rtsp_paths,
    broadcast_live_status,
    stream_video as stream_video_impl,
    upload_video as upload_video_impl,
    mobile_mic as mobile_mic_impl,
    recordings_folder as recordings_folder_impl,
    manage_recordings as manage_recordings_impl,
    toggle_recording_publish as toggle_recording_publish_impl,
    admin_content_manager as admin_content_manager_impl,
    delete_recording_admin as delete_recording_admin_impl,
    delete_meeting_admin as delete_meeting_admin_impl,
    admin_dashboard as admin_dashboard_impl,
    add_camera as add_camera_impl,
    edit_camera as edit_camera_impl,
    delete_camera as delete_camera_impl,
    camera_feed as camera_feed_impl,
    test_camera as test_camera_impl,
    live_monitor as live_monitor_impl,
    test_feed_page as test_feed_page_impl,
    teacher_camera_dashboard as teacher_camera_dashboard_impl,
    teacher_control_room as teacher_control_room_impl,
    update_zoom as update_zoom_impl,
    start_streaming as start_streaming_impl,
    stop_streaming as stop_streaming_impl,
    live_participants as live_participants_impl,
    student_lecture_list as student_lecture_list_impl,
    watch_live as watch_live_impl,
    watch_recording as watch_recording_impl,
    stream_recording_chunk as stream_recording_chunk_impl,
    recording_playlist as recording_playlist_impl,
    teacher_profile as teacher_profile_impl,
    start_camera_recording as start_camera_recording_impl,
    stop_camera_recording as stop_camera_recording_impl,
    publish_recording as publish_recording_impl,
    grant_permission as grant_permission_impl,
    revoke_permission as revoke_permission_impl,
    manage_permissions as manage_permissions_impl,
    head_count_dashboard as head_count_dashboard_impl,
    start_head_count as start_head_count_impl,
    stop_head_count as stop_head_count_impl,
    head_count_logs as head_count_logs_impl,
    head_count_log_detail as head_count_log_detail_impl,
    head_count_session_history as head_count_session_history_impl,
    head_count_api as head_count_api_impl,
    head_count_report as head_count_report_impl,
    export_head_count_csv as export_head_count_csv_impl,
)


# Video views
@login_required
def stream_video(request, recording_id):
    return stream_video_impl(request, recording_id)

@login_required
def upload_video(request):
    return upload_video_impl(request)

@login_required
def mobile_mic(request, camera_id):
    return mobile_mic_impl(request, camera_id)

@login_required
def recordings_folder(request):
    return recordings_folder_impl(request)

@login_required
def manage_recordings(request):
    return manage_recordings_impl(request)

@login_required
def toggle_recording_publish(request, recording_id):
    return toggle_recording_publish_impl(request, recording_id)

@login_required
def watch_recording(request, recording_id):
    return watch_recording_impl(request, recording_id)

@login_required
def stream_recording_chunk(request, recording_id, sequence):
    return stream_recording_chunk_impl(request, recording_id, sequence)

@login_required
def recording_playlist(request, recording_id):
    return recording_playlist_impl(request, recording_id)

@login_required
def teacher_profile(request, teacher_id):
    return teacher_profile_impl(request, teacher_id)


# Admin and content management views
@login_required
def admin_content_manager(request):
    return admin_content_manager_impl(request)

@login_required
def delete_recording_admin(request, recording_id):
    return delete_recording_admin_impl(request, recording_id)

@login_required
def delete_meeting_admin(request, meeting_id):
    return delete_meeting_admin_impl(request, meeting_id)

@login_required
def admin_dashboard(request):
    return admin_dashboard_impl(request)


# Camera management views
@login_required
def add_camera(request):
    return add_camera_impl(request)

@login_required
def edit_camera(request, camera_id):
    return edit_camera_impl(request, camera_id)

@login_required
def delete_camera(request, camera_id):
    return delete_camera_impl(request, camera_id)

@login_required
def camera_feed(request, camera_id):
    return camera_feed_impl(request, camera_id)

@login_required
def test_camera(request, camera_id):
    return test_camera_impl(request, camera_id)

@login_required
def live_monitor(request):
    return live_monitor_impl(request)

@login_required
def test_feed_page(request):
    return test_feed_page_impl(request)


# Streaming and control room views
@login_required
def teacher_camera_dashboard(request):
    return teacher_camera_dashboard_impl(request)

@login_required
def teacher_control_room(request, camera_id):
    return teacher_control_room_impl(request, camera_id)

@login_required
def update_zoom(request, camera_id):
    return update_zoom_impl(request, camera_id)

@login_required
def start_streaming(request, camera_id):
    return start_streaming_impl(request, camera_id)

@login_required
def stop_streaming(request, camera_id):
    return stop_streaming_impl(request, camera_id)

@login_required
def live_participants(request, camera_id):
    return live_participants_impl(request, camera_id)

@login_required
def student_lecture_list(request):
    return student_lecture_list_impl(request)

@login_required
def watch_live(request, camera_id):
    return watch_live_impl(request, camera_id)

@login_required
def start_camera_recording(request, camera_id):
    return start_camera_recording_impl(request, camera_id)

@login_required
def stop_camera_recording(request, camera_id):
    return stop_camera_recording_impl(request, camera_id)

@login_required
def publish_recording(request):
    return publish_recording_impl(request)


# Permission views
@login_required
def grant_permission(request, camera_id):
    return grant_permission_impl(request, camera_id)

@login_required
def revoke_permission(request, camera_id, teacher_id):
    return revoke_permission_impl(request, camera_id, teacher_id)

@login_required
def manage_permissions(request, camera_id):
    return manage_permissions_impl(request, camera_id)


# Head counting views
@login_required
def head_count_dashboard(request):
    return head_count_dashboard_impl(request)

@login_required
def start_head_count(request, camera_type, camera_id):
    return start_head_count_impl(request, camera_type, camera_id)

@login_required
def stop_head_count(request, camera_type, camera_id):
    return stop_head_count_impl(request, camera_type, camera_id)

@login_required
def head_count_logs(request):
    return head_count_logs_impl(request)

@login_required
def head_count_log_detail(request, log_id):
    return head_count_log_detail_impl(request, log_id)

@login_required
def head_count_session_history(request):
    return head_count_session_history_impl(request)

@login_required
def head_count_api(request, camera_type, camera_id):
    return head_count_api_impl(request, camera_type, camera_id)

@login_required
def head_count_report(request):
    return head_count_report_impl(request)

@login_required
def export_head_count_csv(request):
    return export_head_count_csv_impl(request)
