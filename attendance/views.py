"""
Attendance module views — all endpoints for:
  • Student face registration (upload / camera capture)
  • Teacher controls (schedule, settings, override)
  • Attendance records & reports (daily, student, classroom)
  • Export (Excel)
"""
import json
import base64
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Q, Prefetch
from django.core.cache import cache
from django.views.decorators.cache import cache_page

from meetings.models import Classroom, Meeting
from .models import (
    StudentFaceProfile, ClassSchedule, AttendanceRecord,
    FaceRecognitionLog, AttendanceSettings
)
from .forms import FacePhotoForm
from .face_service import FaceService, get_face_service

logger = logging.getLogger('attendance')


# ══════════════════════════════════════════════════════════════
#  STUDENT: FACE REGISTRATION
# ══════════════════════════════════════════════════════════════

@login_required
@cache_page(60)  # Cache for 1 minute
def face_setup(request):
    """Landing page for face registration — tabs: upload / camera capture."""
    from .models import FaceResetRequest
    profile = getattr(request.user, 'face_profile', None)

    # Determine lock state
    is_registered = profile is not None and profile.is_active
    pending_request  = FaceResetRequest.objects.filter(student=request.user, status='pending').first()
    approved_request = FaceResetRequest.objects.filter(student=request.user, status='approved').first()
    # Locked = registered AND no approved unlock
    is_locked = is_registered and approved_request is None

    ctx = {
        'has_profile':        is_registered,
        'profile':            profile,
        'is_locked':          is_locked,
        'pending_request':    pending_request,
        'approved_request':   approved_request,
        'page_title':         'Face Registration',
    }
    return render(request, 'attendance/face_setup.html', ctx)


@login_required
@require_POST
def upload_face_photo(request):
    """Handle file upload approach to face registration."""
    form = FacePhotoForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, ' '.join(
            e for errors in form.errors.values() for e in errors
        ))
        return redirect('face_setup')

    photo = form.cleaned_data['photo']
    photo.seek(0)                   # reset pointer — Django may have read it during validation
    image_bytes = photo.read()

    svc = get_face_service()
    result = svc.extract_embedding(image_bytes)  # live=False (default) — skip variance check for uploads

    if result['status'] != 'success':
        messages.error(request, f"Face detection failed: {result['message']}")
        return redirect('face_setup')

    # Encrypt and save
    encrypted, checksum = svc.prepare_for_storage(result['embedding'])

    # Save the actual photo file for admin review
    from django.core.files.base import ContentFile
    photo_file = ContentFile(image_bytes, name=f"{request.user.username}_face.jpg")

    StudentFaceProfile.objects.update_or_create(
        student=request.user,
        defaults={
            'face_embedding_encrypted': encrypted,
            'embedding_checksum':       checksum,
            'face_quality_score':       result['quality'],
            'is_active':                True,
            'registration_ip':          _get_client_ip(request),
            'face_photo':               photo_file,
        }
    )

    # Close any approved reset request — face is now re-registered, lock again
    from .models import FaceResetRequest
    FaceResetRequest.objects.filter(student=request.user, status='approved').update(status='denied')

    messages.success(request, "✅ Face registered successfully! Attendance will now be tracked automatically.")
    return redirect('face_setup')


@login_required
@require_POST
def capture_face_photo(request):
    """Handle camera-captured base64 frame approach to face registration."""
    try:
        body   = json.loads(request.body)
        b64    = body.get('frame_b64', '')
        if not b64:
            return JsonResponse({'status': 'error', 'message': 'No frame data received.'}, status=400)

        # Strip data-URL prefix if present
        if ',' in b64:
            b64 = b64.split(',', 1)[1]

        image_bytes = base64.b64decode(b64)
    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': f'Invalid frame data: {exc}'}, status=400)

    svc    = get_face_service()
    result = svc.extract_embedding(image_bytes)  # live=False (default) — skip variance check for captures

    if result['status'] != 'success':
        return JsonResponse({'status': 'error', 'message': result['message']})

    encrypted, checksum = svc.prepare_for_storage(result['embedding'])

    # Save the captured frame as the face photo for admin review
    from django.core.files.base import ContentFile
    photo_file = ContentFile(image_bytes, name=f"{request.user.username}_face.jpg")

    StudentFaceProfile.objects.update_or_create(
        student=request.user,
        defaults={
            'face_embedding_encrypted': encrypted,
            'embedding_checksum':       checksum,
            'face_quality_score':       result['quality'],
            'is_active':                True,
            'registration_ip':          _get_client_ip(request),
            'face_photo':               photo_file,
        }
    )

    # Close any approved reset request — face is now re-registered, lock again
    from .models import FaceResetRequest
    FaceResetRequest.objects.filter(student=request.user, status='approved').update(status='denied')

    return JsonResponse({
        'status':  'success',
        'quality': result['quality'],
        'message': '✅ Face registered successfully!',
    })


@login_required
def face_registration_status(request):
    """AJAX: return whether the current user has a face profile."""
    profile = getattr(request.user, 'face_profile', None)
    return JsonResponse({
        'registered': profile is not None and profile.is_active,
        'quality':    profile.face_quality_score if profile else 0,
        'updated_at': profile.updated_at.isoformat() if profile else None,
    })


# ══════════════════════════════════════════════════════════════
#  STUDENT: VIEW OWN ATTENDANCE
# ══════════════════════════════════════════════════════════════

@login_required
def my_attendance(request):
    """Student view of their own attendance records across all classrooms."""
    records = AttendanceRecord.objects.filter(
        student=request.user
    ).select_related('meeting', 'classroom').order_by('-date')

    # Per-classroom summary
    summary = {}
    for rec in records:
        key = rec.classroom_id
        if key not in summary:
            summary[key] = {
                'classroom': rec.classroom,
                'total': 0, 'present': 0, 'absent': 0, 'late': 0,
            }
        summary[key]['total'] += 1
        summary[key][rec.status] = summary[key].get(rec.status, 0) + 1

    for s in summary.values():
        s['percentage'] = round((s['present'] + s.get('late', 0)) / s['total'] * 100) if s['total'] else 0

    ctx = {
        'records':    records,
        'summary':    list(summary.values()),
        'page_title': 'My Attendance',
    }
    return render(request, 'attendance/my_attendance.html', ctx)


# ══════════════════════════════════════════════════════════════
#  TEACHER: CLASS SCHEDULE
# ══════════════════════════════════════════════════════════════

@login_required
def set_class_schedule(request, classroom_id):
    """Teacher sets which days of the week classes are held."""
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)

    if request.method == 'POST':
        # Delete old schedules
        ClassSchedule.objects.filter(classroom=classroom).delete()

        days        = request.POST.getlist('days')          # ['0','2','4']
        start_times = request.POST.getlist('start_times')
        end_times   = request.POST.getlist('end_times')

        for day, start, end in zip(days, start_times, end_times):
            if day and start and end:
                ClassSchedule.objects.create(
                    classroom=classroom,
                    day_of_week=int(day),
                    start_time=start,
                    end_time=end,
                    created_by=request.user,
                )

        messages.success(request, "Class schedule updated successfully.")
        return redirect('classroom_detail', classroom_id=classroom_id)

    schedules = ClassSchedule.objects.filter(classroom=classroom)
    ctx = {
        'classroom': classroom,
        'schedules': schedules,
        'all_days':  ClassSchedule.DAY_CHOICES,
        'page_title': f'Schedule — {classroom.title}',
    }
    return render(request, 'attendance/class_schedule.html', ctx)


# ══════════════════════════════════════════════════════════════
#  TEACHER: ATTENDANCE SETTINGS
# ══════════════════════════════════════════════════════════════

@login_required
def attendance_settings_view(request, classroom_id):
    """Teacher configures face-recognition thresholds for a classroom."""
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)
    settings_obj, _ = AttendanceSettings.objects.get_or_create(classroom=classroom)

    if request.method == 'POST':
        settings_obj.face_recognition_enabled    = 'face_recognition_enabled' in request.POST
        settings_obj.confidence_threshold         = float(request.POST.get('confidence_threshold', 0.55))
        settings_obj.presence_duration_seconds    = int(request.POST.get('presence_duration_seconds', 30))
        settings_obj.late_threshold_minutes       = int(request.POST.get('late_threshold_minutes', 10))
        settings_obj.recognition_interval_seconds = int(request.POST.get('recognition_interval_seconds', 15))
        settings_obj.enforce_schedule             = 'enforce_schedule' in request.POST
        settings_obj.save()
        messages.success(request, "Attendance settings saved.")
        return redirect('attendance_settings', classroom_id=classroom_id)

    ctx = {
        'classroom':    classroom,
        'att_settings': settings_obj,
        'page_title':   f'Attendance Settings — {classroom.title}',
    }
    return render(request, 'attendance/attendance_settings.html', ctx)


# ══════════════════════════════════════════════════════════════
#  TEACHER: OVERRIDE ATTENDANCE
# ══════════════════════════════════════════════════════════════

@login_required
@require_POST
def override_attendance(request, record_id):
    """Teacher manually marks a student present/absent/late."""
    record = get_object_or_404(AttendanceRecord, id=record_id)
    # Verify requester is the classroom teacher
    if record.classroom.teacher != request.user:
        return JsonResponse({'status': 'forbidden'}, status=403)

    new_status = request.POST.get('status', 'present')
    reason     = request.POST.get('reason', '')

    if new_status not in dict(AttendanceRecord.STATUS_CHOICES):
        return JsonResponse({'status': 'error', 'message': 'Invalid status.'}, status=400)

    record.status               = new_status
    record.override_reason      = reason
    record.overridden_by        = request.user
    record.verification_method  = 'manual'
    record.save()

    return JsonResponse({'status': 'success', 'new_status': new_status})


# ══════════════════════════════════════════════════════════════
#  TEACHER: REPORTS
# ══════════════════════════════════════════════════════════════

@login_required
def daily_report(request, classroom_id):
    """Show attendance for a specific date (default: today)."""
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)
    date_str  = request.GET.get('date', timezone.now().strftime('%Y-%m-%d'))

    try:
        from datetime import date as ddate
        report_date = ddate.fromisoformat(date_str)
    except ValueError:
        report_date = timezone.now().date()

    # All approved students
    memberships = classroom.get_approved_memberships()
    student_ids = [m.student_id for m in memberships]

    # Records for that date
    records_qs = AttendanceRecord.objects.filter(
        classroom=classroom, date=report_date
    ).select_related('student', 'student__userprofile')

    records_map = {r.student_id: r for r in records_qs}

    rows = []
    for m in memberships:
        rec = records_map.get(m.student_id)
        rows.append({
            'student':    m.student,
            'record':     rec,
            'status':     rec.status if rec else 'absent',
            'time_in':    rec.marked_present_at if rec else None,
            'confidence': round(rec.face_match_confidence * 100, 1) if rec else 0,
            'method':     rec.verification_method if rec else '—',
        })

    present_count = sum(1 for r in rows if r['status'] == 'present')
    late_count    = sum(1 for r in rows if r['status'] == 'late')
    absent_count  = len(rows) - present_count - late_count

    ctx = {
        'classroom':     classroom,
        'report_date':   report_date,
        'date_str':      date_str,
        'rows':          rows,
        'present_count': present_count,
        'late_count':    late_count,
        'absent_count':  absent_count,
        'total':         len(rows),
        'page_title':    f'Daily Attendance — {report_date}',
    }
    return render(request, 'attendance/daily_report.html', ctx)


@login_required
def student_report(request, classroom_id, student_id):
    """Per-student attendance history within a classroom."""
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)
    student   = get_object_or_404(User, id=student_id)

    records = AttendanceRecord.objects.filter(
        classroom=classroom, student=student
    ).select_related('meeting').order_by('-date')

    total   = records.count()
    present = records.filter(status__in=['present', 'late']).count()
    pct     = round(present / total * 100) if total else 0

    ctx = {
        'classroom':  classroom,
        'student':    student,
        'records':    records,
        'total':      total,
        'present':    present,
        'absent':     total - present,
        'percentage': pct,
        'page_title': f'Attendance — {student.get_full_name() or student.username}',
    }
    return render(request, 'attendance/student_report.html', ctx)


@login_required
def classroom_attendance_overview(request, classroom_id):
    """Teacher dashboard: all students with overall attendance %."""
    from django.db.models import Count, Q
    classroom   = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)
    memberships = classroom.get_approved_memberships()

    total_meetings = Meeting.objects.filter(classroom=classroom, status='ended').count()

    # Single query: aggregate attendance per student
    att_map = {
        r['student_id']: r
        for r in AttendanceRecord.objects.filter(classroom=classroom)
            .values('student_id')
            .annotate(
                total=Count('id'),
                present=Count('id', filter=Q(status__in=['present', 'late']))
            )
    }

    rows = []
    for m in memberships:
        agg = att_map.get(m.student_id, {'total': 0, 'present': 0})
        total   = agg['total']
        present = agg['present']
        try:
            face_registered = m.student.face_profile.is_active
        except Exception:
            face_registered = False

        rows.append({
            'student':         m.student,
            'total':           total,
            'present':         present,
            'absent':          total - present,
            'percentage':      round(present / total * 100) if total else 0,
            'face_registered': face_registered,
        })

    rows.sort(key=lambda x: x['percentage'])

    face_registered_count = sum(1 for r in rows if r['face_registered'])
    settings_obj, _ = AttendanceSettings.objects.get_or_create(classroom=classroom)
    schedules        = ClassSchedule.objects.filter(classroom=classroom, is_active=True)

    ctx = {
        'classroom':             classroom,
        'rows':                  rows,
        'att_settings':          settings_obj,
        'schedules':             schedules,
        'total_meetings':        total_meetings,
        'face_registered_count': face_registered_count,
        'page_title':            f'Attendance — {classroom.title}',
    }
    return render(request, 'attendance/classroom_overview.html', ctx)


# ══════════════════════════════════════════════════════════════
#  EXPORT
# ══════════════════════════════════════════════════════════════

@login_required
def export_excel(request, classroom_id):
    """Export all attendance records for the classroom as Excel."""
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher=request.user)

    try:
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    except ImportError:
        messages.error(request, "openpyxl is not installed. Run: pip install openpyxl")
        return redirect('classroom_attendance_overview', classroom_id=classroom_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Attendance'

    # ── Styling helpers ────────────────────────────────────────
    header_fill  = PatternFill('solid', fgColor='1877F2')
    header_font  = Font(bold=True, color='FFFFFF', size=11)
    center_align = Alignment(horizontal='center', vertical='center')
    thin_border  = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    status_colors = {
        'present': 'D4EDDA', 'late': 'FFF3CD',
        'absent':  'F8D7DA', 'partial': 'D1ECF1',
    }

    # ── Title row ─────────────────────────────────────────────
    ws.merge_cells('A1:H1')
    title_cell = ws['A1']
    title_cell.value = f'Attendance Report  —  {classroom.title}'
    title_cell.font  = Font(bold=True, size=14, color='1A1A2E')
    title_cell.alignment = center_align

    # ── Header row ────────────────────────────────────────────
    headers = ['Student Name', 'Student ID', 'Date', 'Meeting', 'Status',
               'Time In', 'Method', 'Confidence']
    ws.append([])  # blank row
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx, value=header)
        cell.fill      = header_fill
        cell.font      = header_font
        cell.alignment = center_align
        cell.border    = thin_border

    ws.column_dimensions['A'].width = 24
    ws.column_dimensions['B'].width = 14
    ws.column_dimensions['C'].width = 14
    ws.column_dimensions['D'].width = 28
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 20
    ws.column_dimensions['H'].width = 14

    # ── Data rows ─────────────────────────────────────────────
    records = AttendanceRecord.objects.filter(
        classroom=classroom
    ).select_related('student', 'student__userprofile', 'meeting').order_by('-date', 'student__last_name')

    for row_idx, rec in enumerate(records, 4):
        try:
            sid = rec.student.userprofile.student_id or '—'
        except Exception:
            sid = '—'

        time_in = rec.marked_present_at.strftime('%H:%M:%S') if rec.marked_present_at else '—'
        conf    = f"{rec.face_match_confidence * 100:.1f}%" if rec.face_match_confidence else '—'

        row_data = [
            rec.student.get_full_name() or rec.student.username,
            sid,
            str(rec.date),
            rec.meeting.title,
            rec.get_status_display(),
            time_in,
            rec.get_verification_method_display(),
            conf,
        ]

        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = thin_border
            cell.alignment = Alignment(vertical='center')
            if col_idx == 5:  # Status column
                color = status_colors.get(rec.status, 'FFFFFF')
                cell.fill = PatternFill('solid', fgColor=color)
                cell.alignment = center_align
                cell.font = Font(bold=True)

    # ── Response ───────────────────────────────────────────────
    filename = f"attendance_{classroom.class_code}_{timezone.now().strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


# ══════════════════════════════════════════════════════════════
#  API: CHECK SCHEDULE (used by JS before starting FR)
# ══════════════════════════════════════════════════════════════

@login_required
def check_schedule_api(request, meeting_code):
    """Return whether today is a scheduled class day for this meeting's classroom."""
    try:
        meeting   = Meeting.objects.select_related('classroom').get(meeting_code=meeting_code)
        classroom = meeting.classroom
    except Meeting.DoesNotExist:
        return JsonResponse({'scheduled': False, 'message': 'Meeting not found.'})

    settings_obj, _ = AttendanceSettings.objects.get_or_create(classroom=classroom)
    if not settings_obj.face_recognition_enabled:
        return JsonResponse({'scheduled': False, 'message': 'Face recognition disabled for this classroom.'})

    if not settings_obj.enforce_schedule:
        return JsonResponse({'scheduled': True, 'message': 'Schedule not enforced.'})

    today = timezone.localdate()
    scheduled = ClassSchedule.objects.filter(
        classroom=classroom,
        day_of_week=today.weekday(),
        is_active=True
    ).exists()

    return JsonResponse({
        'scheduled': scheduled,
        'message':   'Class is scheduled today.' if scheduled else 'No class scheduled today — attendance not recorded.',
        'interval':  settings_obj.recognition_interval_seconds,
    })


# ══════════════════════════════════════════════════════════════
#  TEACHER: ENGAGEMENT REPORT
# ══════════════════════════════════════════════════════════════

@login_required
def engagement_report_view(request, meeting_id):
    """Teacher views the engagement report for a completed meeting."""
    from meetings.models import Meeting
    from .models import EngagementReport

    meeting = get_object_or_404(Meeting, id=meeting_id)

    if meeting.teacher != request.user and not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Access denied.")

    report = EngagementReport.objects.filter(meeting=meeting).first()

    # If report doesn't exist yet, generate it now
    if not report and meeting.status == 'ended':
        from .engagement_service import generate_engagement_report
        generate_engagement_report(meeting.id)
        report = EngagementReport.objects.filter(meeting=meeting).first()

    ctx = {
        'meeting':    meeting,
        'report':     report,
        'page_title': f'Engagement Report — {meeting.title}',
    }
    return render(request, 'attendance/engagement_report.html', ctx)


# ══════════════════════════════════════════════════════════════
#  STUDENT: FACE RESET REQUEST
# ══════════════════════════════════════════════════════════════

@login_required
@require_POST
def request_face_reset(request):
    """Student submits a request to re-register their face."""
    from .models import FaceResetRequest

    # Block if there's already a pending request
    if FaceResetRequest.objects.filter(student=request.user, status='pending').exists():
        return JsonResponse({'status': 'error', 'message': 'You already have a pending request.'})

    subject = request.POST.get('subject', '').strip()
    reason  = request.POST.get('reason', '').strip()

    if not subject or not reason:
        return JsonResponse({'status': 'error', 'message': 'Subject and reason are required.'})

    if len(reason) < 20:
        return JsonResponse({'status': 'error', 'message': 'Please provide a more detailed reason (at least 20 characters).'})

    req = FaceResetRequest.objects.create(
        student=request.user,
        subject=subject,
        reason=reason,
    )

    # Notify all superusers
    from accounts.notification_models import Notification
    from django.contrib.auth.models import User as AuthUser
    admins = AuthUser.objects.filter(is_superuser=True)
    for admin in admins:
        Notification.objects.create(
            recipient=admin,
            notification_type='system',
            title=f'Face Reset Request — {request.user.get_full_name() or request.user.username}',
            message=f'Subject: {subject}',
            link='/attendance/admin/face-reset-requests/',
            related_user=request.user,
        )

    return JsonResponse({'status': 'success', 'message': 'Request submitted. You will be notified once reviewed.'})


@login_required
def admin_face_reset_requests(request):
    """Admin view: list all face reset requests."""
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Access denied.")

    from .models import FaceResetRequest
    requests_qs = FaceResetRequest.objects.select_related('student', 'reviewed_by').all()

    ctx = {
        'requests':   requests_qs,
        'page_title': 'Face Reset Requests',
    }
    return render(request, 'attendance/admin_face_reset_requests.html', ctx)


@login_required
@require_POST
def review_face_reset_request(request, request_id):
    """Admin approves or denies a face reset request."""
    if not request.user.is_superuser:
        return JsonResponse({'status': 'forbidden'}, status=403)

    from .models import FaceResetRequest
    from accounts.notification_models import Notification
    from django.utils import timezone

    req = get_object_or_404(FaceResetRequest, id=request_id)
    action     = request.POST.get('action')   # 'approve' or 'deny'
    admin_note = request.POST.get('admin_note', '').strip()

    if action not in ('approve', 'deny'):
        return JsonResponse({'status': 'error', 'message': 'Invalid action.'})

    req.status      = 'approved' if action == 'approve' else 'denied'
    req.admin_note  = admin_note
    req.reviewed_by = request.user
    req.reviewed_at = timezone.now()
    req.save()

    # Notify the student
    if action == 'approve':
        Notification.objects.create(
            recipient=req.student,
            notification_type='system',
            title='Face Re-registration Approved',
            message='Your request to re-register your face has been approved. You can now update your face profile.',
            link='/attendance/face/setup/',
        )
    else:
        Notification.objects.create(
            recipient=req.student,
            notification_type='system',
            title='Face Re-registration Request Denied',
            message=f'Your request was not approved.{" Reason: " + admin_note if admin_note else ""}',
            link='/attendance/face/setup/',
        )

    return JsonResponse({'status': 'success', 'new_status': req.status})


# ══════════════════════════════════════════════════════════════
#  ADMIN: STUDENT FACE PHOTOS
# ══════════════════════════════════════════════════════════════

@login_required
def admin_face_photos(request):
    """Admin-only view of all student face registration photos."""
    if not request.user.is_superuser:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Access denied.")

    profiles = StudentFaceProfile.objects.filter(
        is_active=True, face_photo__isnull=False
    ).exclude(face_photo='').select_related('student', 'student__userprofile').order_by('-updated_at')

    ctx = {
        'profiles':   profiles,
        'page_title': 'Student Face Photos',
    }
    return render(request, 'attendance/admin_face_photos.html', ctx)


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
