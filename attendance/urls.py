from django.urls import path
from . import views

urlpatterns = [
    # ── Student: Face Registration ──────────────────────────────
    path('face/setup/',   views.face_setup,              name='face_setup'),
    path('face/upload/',  views.upload_face_photo,       name='upload_face_photo'),
    path('face/capture/', views.capture_face_photo,      name='capture_face_photo'),
    path('face/detect/',  views.detect_face,             name='detect_face'),
    path('face/status/',  views.face_registration_status, name='face_status'),

    # ── Student: My Attendance ──────────────────────────────────
    path('my/', views.my_attendance, name='my_attendance'),

    # ── Teacher: Controls ───────────────────────────────────────
    path('schedule/<int:classroom_id>/set/',      views.set_class_schedule,              name='set_class_schedule'),
    path('settings/<int:classroom_id>/',          views.attendance_settings_view,        name='attendance_settings'),
    path('override/<int:record_id>/',             views.override_attendance,             name='override_attendance'),

    # ── Teacher: Reports ────────────────────────────────────────
    path('classroom/<int:classroom_id>/',                    views.classroom_attendance_overview, name='classroom_attendance_overview'),
    path('classroom/<int:classroom_id>/daily/',              views.daily_report,                  name='daily_report'),
    path('classroom/<int:classroom_id>/student/<int:student_id>/', views.student_report,       name='student_report'),

    # ── Export ──────────────────────────────────────────────────
    path('classroom/<int:classroom_id>/export/excel/', views.export_excel, name='export_excel'),

    # ── API ─────────────────────────────────────────────────────
    path('api/check-schedule/<str:meeting_code>/', views.check_schedule_api, name='check_schedule_api'),

    # ── Admin: Face Photos ───────────────────────────────────────
    path('admin/face-photos/', views.admin_face_photos, name='admin_face_photos'),

    # ── Engagement Reports ───────────────────────────────────────
    path('engagement-report/<int:meeting_id>/', views.engagement_report_view, name='engagement_report'),
]

    # ── Attendance dashboard API (chart data) ────────────────────
    path('api/classroom/<int:classroom_id>/monthly/', views.attendance_monthly_api, name='attendance_monthly_api'),
