from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from meetings.models import Meeting, MeetingParticipant, Classroom, ClassroomMembership, MeetingAttendanceLog, MeetingChat, MeetingSummary, KickedParticipant
from meetings.tasks import generate_meeting_summary
from accounts.notification_utils import (
    notify_classroom_join_request, 
    notify_classroom_request_approved, 
    notify_student_joined_classroom,
    notify_classroom_request_denied,
    notify_student_removed_from_classroom,
    notify_meeting_started,
    notify_meeting_cancelled
)
from django.conf import settings
from livekit.api import AccessToken, VideoGrants
import random
import string
import base64
from django.core.files.base import ContentFile
from attendance.face_service import get_face_service
from attendance.models import StudentFaceProfile

def generate_meeting_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

# ==================== CLASSROOM MANAGEMENT ====================

@login_required
def create_classroom(request):
    """Teacher creates a new classroom"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'teacher':
        messages.error(request, 'Only teachers can create classrooms')
        return redirect('login')
    
    if request.method == 'POST':
        class_code = request.POST.get('class_code').strip().upper()
        title = request.POST.get('title').strip()
        password = request.POST.get('password')
        description = request.POST.get('description', '').strip()
        
        # Validate class code uniqueness
        if Classroom.objects.filter(class_code=class_code).exists():
            messages.error(request, 'Class code already exists. Please choose a different one.')
            return render(request, 'meetings/create_classroom.html')
        
        # Create classroom with hashed password
        classroom = Classroom.objects.create(
            class_code=class_code,
            title=title,
            password=make_password(password),
            teacher=request.user,
            description=description
        )
        
        messages.success(request, f'Classroom "{title}" created successfully! Share code: {class_code}')
        return redirect('teacher_classrooms')
    
    return render(request, 'meetings/create_classroom.html')

@login_required
def teacher_classrooms(request):
    """Teacher views all their classrooms"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'teacher':
        return redirect('login')
    
    classrooms = Classroom.objects.filter(teacher=request.user, is_active=True)
    return render(request, 'meetings/teacher_classrooms.html', {'classrooms': classrooms})

@login_required
def classroom_detail(request, classroom_id):
    """View classroom details with pending requests and approved students"""
    classroom = get_object_or_404(Classroom, id=classroom_id)
    
    from .services import get_classroom_detail_context
    ctx = get_classroom_detail_context(classroom, request.user)
    
    if ctx is None:
        messages.error(request, 'You do not have access to this classroom')
        return redirect('student_classrooms')
    
    return render(request, 'meetings/classroom_detail.html', ctx)

@login_required
def join_classroom_request(request):
    """Student submits request to join a classroom"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'student':
        messages.error(request, 'Only students can join classrooms')
        return redirect('login')
    
    if request.method == 'POST':
        class_code = request.POST.get('class_code').strip().upper()
        password = request.POST.get('password')
        
        try:
            classroom = Classroom.objects.get(class_code=class_code, is_active=True)
        except Classroom.DoesNotExist:
            messages.error(request, 'Invalid class code')
            return render(request, 'meetings/join_classroom.html')
        
        # Verify password
        if not check_password(password, classroom.password):
            messages.error(request, 'Incorrect password')
            return render(request, 'meetings/join_classroom.html')
        
        # Check if already a member
        existing_membership = ClassroomMembership.objects.filter(
            classroom=classroom,
            student=request.user
        ).first()
        
        if existing_membership:
            if existing_membership.status == 'approved':
                messages.info(request, 'You are already a member of this classroom')
                return redirect('classroom_detail', classroom_id=classroom.id)
            elif existing_membership.status == 'pending':
                messages.info(request, 'Your join request is pending approval')
                return redirect('student_classrooms')
            elif existing_membership.status == 'denied':
                messages.error(request, 'Your previous request was denied. Please contact the teacher.')
                return redirect('student_classrooms')
        
        # Create new membership request
        ClassroomMembership.objects.create(
            classroom=classroom,
            student=request.user,
            status='pending'
        )
        
        # Send notification to teacher
        notify_classroom_join_request(request.user, classroom)
        
        messages.success(request, f'Join request submitted for "{classroom.title}". Waiting for teacher approval.')
        return redirect('student_classrooms')
    
    return render(request, 'meetings/join_classroom.html')

@login_required
def student_classrooms(request):
    """Student views all their classrooms"""
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'student':
        return redirect('login')
    
    # Get approved classrooms
    approved_memberships = ClassroomMembership.objects.filter(
        student=request.user,
        status='approved'
    ).select_related('classroom')
    
    # Get pending requests
    pending_memberships = ClassroomMembership.objects.filter(
        student=request.user,
        status='pending'
    ).select_related('classroom')
    
    return render(request, 'meetings/student_classrooms.html', {
        'approved_memberships': approved_memberships,
        'pending_memberships': pending_memberships
    })

@login_required
@require_http_methods(["POST"])
def approve_join_request(request, membership_id):
    """Teacher approves a student's join request"""
    membership = get_object_or_404(ClassroomMembership, id=membership_id)
    
    # Check if user is the classroom teacher
    if membership.classroom.teacher != request.user:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    membership.status = 'approved'
    membership.approved_at = timezone.now()
    membership.approved_by = request.user
    membership.save()
    
    # Send notification to student
    notify_classroom_request_approved(membership.student, membership.classroom, request.user)
    notify_student_joined_classroom(membership.student, membership.classroom)
    
    return JsonResponse({
        'status': 'success',
        'message': f'{membership.student.username} approved'
    })

@login_required
@require_http_methods(["POST"])
def deny_join_request(request, membership_id):
    """Teacher denies a student's join request"""
    membership = get_object_or_404(ClassroomMembership, id=membership_id)
    
    # Check if user is the classroom teacher
    if membership.classroom.teacher != request.user:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    membership.status = 'denied'
    membership.save()
    
    # Send notification to student
    notify_classroom_request_denied(membership.student, membership.classroom)
    
    return JsonResponse({
        'status': 'success',
        'message': f'{membership.student.username} denied'
    })

@login_required
@require_http_methods(["POST"])
def remove_student(request, membership_id):
    """Teacher removes a student from classroom"""
    membership = get_object_or_404(ClassroomMembership, id=membership_id)
    
    # Check if user is the classroom teacher
    if membership.classroom.teacher != request.user:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    membership.status = 'removed'
    membership.save()
    
    # Send notification to student
    notify_student_removed_from_classroom(membership.student, membership.classroom)
    
    return JsonResponse({
        'status': 'success',
        'message': f'{membership.student.username} removed from classroom'
    })

@login_required
@require_http_methods(["POST"])
def delete_classroom(request, classroom_id):
    """Teacher deletes a classroom"""
    classroom = get_object_or_404(Classroom, id=classroom_id)
    
    # Check if user is the classroom teacher
    if classroom.teacher != request.user:
        messages.error(request, 'Only the classroom teacher can delete this classroom')
        return redirect('classroom_detail', classroom_id=classroom_id)
    
    # Check if there's an active meeting
    if classroom.has_active_meeting():
        messages.error(request, 'Cannot delete classroom with an active meeting. End the meeting first.')
        return redirect('classroom_detail', classroom_id=classroom_id)
    
    classroom_title = classroom.title
    classroom.delete()
    
    messages.success(request, f'Classroom "{classroom_title}" has been deleted successfully')
    return redirect('teacher_classrooms')

@login_required
@require_http_methods(["POST"])
def leave_classroom(request, classroom_id):
    """Student leaves a classroom"""
    classroom = get_object_or_404(Classroom, id=classroom_id)
    
    # Get the student's membership
    try:
        membership = ClassroomMembership.objects.get(
            classroom=classroom,
            student=request.user,
            status='approved'
        )
    except ClassroomMembership.DoesNotExist:
        messages.error(request, 'You are not a member of this classroom')
        return redirect('student_classrooms')
    
    # Update membership status
    membership.status = 'left'
    membership.save()
    
    messages.success(request, f'You have left "{classroom.title}"')
    return redirect('student_classrooms')

@login_required
def start_classroom_meeting(request, classroom_id):
    """Teacher starts a new meeting in the classroom"""
    classroom = get_object_or_404(Classroom, id=classroom_id)
    
    # Check if user is the classroom teacher
    if classroom.teacher != request.user:
        messages.error(request, 'Only the classroom teacher can start meetings')
        return redirect('classroom_detail', classroom_id=classroom_id)
    
    # Check if there's already an active meeting
    if classroom.has_active_meeting():
        active_meeting = classroom.get_active_meeting()
        messages.info(request, 'A meeting is already in progress')
        return redirect('join_meeting', meeting_code=active_meeting.meeting_code)
    
    if request.method == 'POST':
        title = request.POST.get('title', classroom.title).strip()
        duration_minutes = int(request.POST.get('duration_minutes', 60))
        allow_screen_share = request.POST.get('allow_screen_share', 'on') == 'on'
        allow_chat = request.POST.get('allow_chat', 'on') == 'on'
        record_meeting = request.POST.get('record_meeting') == 'on'

        if not title:
            messages.error(request, 'Meeting title cannot be empty.')
            return render(request, 'meetings/start_classroom_meeting.html', {'classroom': classroom})

        # Prevent duplicate title within the same classroom (across non-ended meetings)
        if Meeting.objects.filter(classroom=classroom, title__iexact=title).exclude(status__in=['ended', 'cancelled']).exists():
            messages.error(request, f'A meeting named "{title}" already exists in this classroom. Please use a different title.')
            return render(request, 'meetings/start_classroom_meeting.html', {'classroom': classroom})

        meeting_code = generate_meeting_code()
        
        meeting = Meeting.objects.create(
            classroom=classroom,
            title=title,
            teacher=request.user,
            meeting_code=meeting_code,
            scheduled_time=timezone.now(),
            duration_minutes=duration_minutes,
            status='live',
            allow_screen_share=allow_screen_share,
            allow_chat=allow_chat,
            record_meeting=record_meeting
        )
        
        # Send notification to all approved students
        notify_meeting_started(meeting, classroom)
        
        messages.success(request, 'Meeting started successfully!')
        return redirect('join_meeting', meeting_code=meeting.meeting_code)
    
    return render(request, 'meetings/start_classroom_meeting.html', {'classroom': classroom})

# ==================== MEETING MANAGEMENT ====================


@login_required
def create_meeting(request):
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'teacher':
        return redirect('login')
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '')
        scheduled_time = request.POST.get('scheduled_time')
        duration_minutes = int(request.POST.get('duration_minutes', 60))
        allow_screen_share = request.POST.get('allow_screen_share') == 'on'
        allow_chat = request.POST.get('allow_chat') == 'on'

        if not title:
            messages.error(request, 'Meeting title cannot be empty.')
            return render(request, 'meetings/create_meeting.html')

        # Prevent duplicate title for the same teacher (across non-ended standalone meetings)
        if Meeting.objects.filter(teacher=request.user, title__iexact=title, classroom__isnull=True).exclude(status__in=['ended', 'cancelled']).exists():
            messages.error(request, f'You already have a meeting named "{title}". Please use a different title.')
            return render(request, 'meetings/create_meeting.html')

        meeting_code = generate_meeting_code()
        
        meeting = Meeting.objects.create(
            title=title,
            description=description,
            teacher=request.user,
            meeting_code=meeting_code,
            scheduled_time=scheduled_time,
            duration_minutes=duration_minutes,
            allow_screen_share=allow_screen_share,
            allow_chat=allow_chat,
        )
        
        return redirect('teacher_meetings')
    
    return render(request, 'meetings/create_meeting.html')

@login_required
def teacher_meetings(request):
    # Allow admin to view all non-classroom meetings
    if request.user.is_superuser:
        meetings = Meeting.objects.filter(classroom__isnull=True)
    elif hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'teacher':
        meetings = Meeting.objects.filter(teacher=request.user, classroom__isnull=True)
    else:
        return redirect('login')
    
    # Separate sleeping meetings
    sleeping_meetings = meetings.filter(status='live', sleep_status='sleeping')
    active_meetings = meetings.exclude(sleep_status='sleeping')
    
    return render(request, 'meetings/teacher_meetings.html', {
        'meetings': active_meetings,
        'sleeping_meetings': sleeping_meetings,
        'is_admin': request.user.is_superuser
    })

@login_required
def student_meetings(request):
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'student':
        return redirect('login')
    
    # Get all scheduled and live non-classroom meetings
    meetings = Meeting.objects.filter(status__in=['scheduled', 'live'], classroom__isnull=True)
    return render(request, 'meetings/student_meetings.html', {'meetings': meetings})

@login_required
def join_meeting(request, meeting_code):
    meeting = get_object_or_404(Meeting, meeting_code=meeting_code)
    
    # Check if meeting is sleeping - prevent joining
    if meeting.is_sleeping():
        messages.error(request, 'This meeting is currently in sleep mode. Please wait for the host to unfreeze it.')
        user_type = request.user.userprofile.user_type if hasattr(request.user, 'userprofile') else None
        return redirect('student_dashboard' if user_type == 'student' else 'teacher_dashboard')
    
    # Check if user is kicked/banned
    from .models import KickedParticipant
    kick_record = KickedParticipant.objects.filter(meeting=meeting, user=request.user).first()
    if kick_record and kick_record.is_banned():
        messages.error(request, f'You have been kicked from this meeting. You can rejoin at {kick_record.banned_until.strftime("%H:%M")}.')
        user_type = request.user.userprofile.user_type if hasattr(request.user, 'userprofile') else None
        return redirect('student_dashboard' if user_type == 'student' else 'teacher_dashboard')
    
    # Check if meeting is in a classroom
    if meeting.classroom:
        # Verify user is approved member or teacher
        is_teacher = meeting.classroom.teacher == request.user
        is_approved = ClassroomMembership.objects.filter(
            classroom=meeting.classroom,
            student=request.user,
            status='approved'
        ).exists()
        
        if not (is_teacher or is_approved):
            messages.error(request, 'You must be an approved member of this classroom to join')
            return redirect('student_classrooms')
    
    is_student = hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'student'
    is_host = meeting.teacher == request.user or request.user.is_superuser

    # --- Face registration check: WARN but do NOT block ---
    face_not_registered = False
    if is_student and not is_host:
        face_not_registered = not StudentFaceProfile.objects.filter(student=request.user).exists()
        if face_not_registered:
            messages.warning(
                request,
                '⚠️ You have not registered your face identity. '
                'Your attendance will still be recorded but face verification is unavailable. '
                'Please complete Face Setup soon.'
            )

    # Create or get participant record (unique_together = meeting + user)
    participant, created = MeetingParticipant.objects.get_or_create(
        meeting=meeting,
        user=request.user,
        defaults={'joined_at': timezone.now(), 'is_active': True}
    )

    join_time = timezone.now()
    if not created:
        # Re-joining: update join timestamp and mark active again
        participant.joined_at = join_time
        participant.is_active = True
        participant.save(update_fields=['joined_at', 'is_active'])

    # --- Log every JOIN event for detailed attendance tracking ---
    MeetingAttendanceLog.objects.create(
        participant=participant,
        event_type='join'
    )

    # Update meeting status to live if teacher joins
    if meeting.teacher == request.user and meeting.status == 'scheduled':
        meeting.status = 'live'
        meeting.save()
        notify_meeting_started(meeting, meeting.classroom)
    
    # Ensure host has permissions
    if meeting.teacher == request.user or request.user.is_superuser:
        participant.audio_permitted = True
        participant.video_permitted = True
        participant.screenshare_permitted = True
        participant.save()
    
    # Redirect registered students to face-verification pre-join
    # Skip if: user not registered, user is host, already verified, or explicitly skipped
    skip_verify = request.GET.get('skip_verify') == '1'
    if is_student and not is_host and not face_not_registered and not skip_verify:
        if not request.session.get(f'verified_meeting_{meeting.meeting_code}'):
            return redirect('pre_join', meeting_code=meeting.meeting_code)

    return render(request, 'meetings/meeting_room.html', {
        'meeting': meeting,
        'participant': participant,
        'is_host': is_host,
        'livekit_url': settings.LIVEKIT_URL,
        'face_not_registered': face_not_registered,
    })

@login_required
def pre_join(request, meeting_code):
    meeting = get_object_or_404(Meeting, meeting_code=meeting_code)
    
    # If host, skip pre-join
    if meeting.teacher == request.user or request.user.is_superuser:
        return redirect('join_meeting', meeting_code=meeting_code)
    
    # Check if student has a face profile registered
    face_registered = StudentFaceProfile.objects.filter(student=request.user).exists()
    # NOTE: If not registered we still show the page with a 'Skip' option — attendance
    # was already logged in join_meeting, so they are not blocked.

    profile = getattr(request.user, 'userprofile', None)
    return render(request, 'meetings/pre_join.html', {
        'meeting': meeting,
        'profile': profile,
        'face_registered': face_registered,
    })

@login_required
@require_http_methods(["POST"])
def verify_face_prejoin(request):
    import json
    data = json.loads(request.body)
    image_data = data.get('image')
    meeting_code = data.get('meeting_code')
    
    if not image_data:
        return JsonResponse({'success': False, 'message': 'No image provided'})

    # Decode base64 image
    format, imgstr = image_data.split(';base64,')
    image_bytes = base64.b64decode(imgstr)
    
    # Get stored profile
    try:
        profile = StudentFaceProfile.objects.get(student=request.user)
    except StudentFaceProfile.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'No face profile found'})

    # Use FaceService to compare
    fs = get_face_service()
    result = fs.compare_frame_to_stored(
        frame_bytes=image_bytes,
        encrypted_embedding=profile.face_embedding_encrypted,
        threshold=0.55
    )

    if result['match']:
        # Mark this specific meeting as verified in the session
        if meeting_code:
            request.session[f'verified_meeting_{meeting_code}'] = True
        
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False, 'message': result['message']})

@login_required
def livekit_token(request, meeting_code):
    """Generate a LiveKit access token for the requesting user."""
    meeting = get_object_or_404(Meeting, meeting_code=meeting_code)

    # Same access check as join_meeting
    if meeting.classroom:
        is_teacher = meeting.classroom.teacher == request.user
        is_approved = ClassroomMembership.objects.filter(
            classroom=meeting.classroom,
            student=request.user,
            status='approved'
        ).exists()
        if not (is_teacher or is_approved):
            return JsonResponse({'error': 'Access denied'}, status=403)

    is_host = meeting.teacher == request.user or request.user.is_superuser

    token = (
        AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(str(request.user.id))
        .with_name(request.user.username)
        .with_grants(VideoGrants(
            room_join=True,
            room=meeting_code,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
            room_admin=is_host,
        ))
        .to_jwt()
    )

    return JsonResponse({'token': token, 'url': settings.LIVEKIT_URL})

@login_required
def meeting_attendance(request, meeting_code):
    meeting = get_object_or_404(Meeting, meeting_code=meeting_code)
    
    # Check permission (Teacher of meeting or Superuser)
    if meeting.teacher != request.user and not request.user.is_superuser:
        return render(request, 'error.html', {'message': 'You do not have permission to view attendance for this meeting'})
    
    participants = meeting.participants.all().select_related('user').prefetch_related('attendance_logs')
    
    # Build detailed session data for each participant
    participant_data = []
    for p in participants:
        logs_list = list(p.attendance_logs.order_by('timestamp'))

        # Pair join/leave into individual sessions
        sessions = []
        pending_join = None
        accumulated_secs = 0

        for log in logs_list:
            if log.event_type == 'join':
                pending_join = log.timestamp
            elif log.event_type == 'leave' and pending_join:
                secs = max(0, int((log.timestamp - pending_join).total_seconds()))
                sessions.append({
                    'joined': pending_join,
                    'left': log.timestamp,
                    'duration_secs': secs,
                    'duration_fmt': f"{secs // 60}m {secs % 60}s",
                    'active': False,
                })
                accumulated_secs += secs
                pending_join = None

        # Still active — join without a matching leave
        if pending_join:
            sessions.append({
                'joined': pending_join,
                'left': None,
                'duration_secs': None,
                'duration_fmt': 'In progress',
                'active': True,
            })

        participant_data.append({
            'participant': p,
            'logs': logs_list,
            'sessions': sessions,
            'session_count': len(sessions),
            'total_secs': accumulated_secs,
            'total_fmt': f"{accumulated_secs // 60}m {accumulated_secs % 60}s" if accumulated_secs else '—',
        })
    
    return render(request, 'meetings/attendance_report.html', {
        'meeting': meeting,
        'participants': participants,
        'participant_data': participant_data,
    })

@login_required
def meeting_summary(request, meeting_code):
    meeting = get_object_or_404(Meeting, meeting_code=meeting_code)
    
    # Check permissions (Teacher or Participant)
    is_teacher = meeting.teacher == request.user
    is_admin = request.user.is_superuser
    
    if not (is_teacher or is_admin):
        # Even students might want to see the summary of a meeting they attended
        if not MeetingParticipant.objects.filter(meeting=meeting, user=request.user).exists():
            messages.error(request, 'You do not have permission to view this summary')
            return redirect('student_meetings')

    # Try to get existing summary
    summary = MeetingSummary.objects.filter(meeting=meeting).first()
    
    return render(request, 'meetings/meeting_summary.html', {
        'meeting': meeting,
        'summary': summary
    })

@login_required
@require_http_methods(["POST"])
def end_meeting(request, meeting_id):
    meeting = get_object_or_404(Meeting, id=meeting_id)
    
    # Allow teacher or admin to end meeting
    if meeting.teacher != request.user and request.user.username != 'Admin' and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    end_time = timezone.now()
    meeting.status = 'ended'
    meeting.ended_at = end_time
    meeting.save()
    
    # Log LEAVE for all still-active participants and accumulate duration
    active_participants = MeetingParticipant.objects.filter(meeting=meeting, is_active=True).select_related('user')
    for p in active_participants:
        # Log the leave event
        MeetingAttendanceLog.objects.create(participant=p, event_type='leave')
        # Accumulate session time
        if p.joined_at:
            session_secs = max(0, int((end_time - p.joined_at).total_seconds()))
            p.total_duration_seconds = (p.total_duration_seconds or 0) + session_secs
        p.is_active = False
        p.left_at = end_time
        p.save(update_fields=['is_active', 'left_at', 'total_duration_seconds'])
    
    # Trigger AI Summary Generation (Background Task)
    generate_meeting_summary.delay(meeting.id)

    # Generate face engagement report (sync — fast, uses existing snapshots)
    try:
        from attendance.engagement_service import generate_engagement_report
        generate_engagement_report(meeting.id)
    except Exception as _e:
        pass  # Don't block meeting end if report fails
    
    # Redirect to classroom if meeting was in a classroom
    if meeting.classroom:
        return JsonResponse({
            'status': 'success',
            'redirect_url': f'/meetings/classroom/{meeting.classroom.id}/'
        })
    
    return JsonResponse({'status': 'success'})

@login_required
@require_http_methods(["POST"])
def leave_meeting(request, meeting_id):
    meeting = get_object_or_404(Meeting, id=meeting_id)
    
    try:
        participant = MeetingParticipant.objects.get(meeting=meeting, user=request.user)
        leave_time = timezone.now()

        # --- Log every LEAVE event for detailed attendance tracking ---
        MeetingAttendanceLog.objects.create(
            participant=participant,
            event_type='leave'
        )

        # Accumulate session duration into total
        if participant.joined_at and participant.is_active:
            session_secs = max(0, int((leave_time - participant.joined_at).total_seconds()))
            participant.total_duration_seconds = (participant.total_duration_seconds or 0) + session_secs

        participant.is_active = False
        participant.left_at = leave_time
        participant.save(update_fields=['is_active', 'left_at', 'total_duration_seconds'])
        return JsonResponse({'status': 'success'})
    except MeetingParticipant.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not a participant'})

@login_required
def get_participants(request, meeting_id):
    meeting = get_object_or_404(Meeting, id=meeting_id)
    participants = MeetingParticipant.objects.filter(meeting=meeting, is_active=True)
    
    data = [{
        'id': p.user.id,
        'username': p.user.username,
        'is_host': p.user == meeting.teacher
    } for p in participants]
    
    return JsonResponse({'participants': data})

@login_required
@require_http_methods(["POST"])
def delete_meeting(request, meeting_id):
    meeting = get_object_or_404(Meeting, id=meeting_id)
    
    # Allow teacher or admin to delete meeting
    if meeting.teacher != request.user and request.user.username != 'Admin' and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    meeting.delete()
    return JsonResponse({'status': 'success'})

@login_required
@require_http_methods(["POST"])
def cancel_meeting(request, meeting_id):
    meeting = get_object_or_404(Meeting, id=meeting_id)
    
    # Allow teacher or admin to cancel meeting
    if meeting.teacher != request.user and request.user.username != 'Admin' and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    meeting.status = 'cancelled'
    meeting.save()
    
    # Send notification to all participants
    notify_meeting_cancelled(meeting, meeting.classroom)
    
    return JsonResponse({'status': 'success'})


@login_required
def sleep_meeting(request, meeting_code):
    """Put meeting to sleep mode - only teacher/host can do this"""
    meeting = get_object_or_404(Meeting, meeting_code=meeting_code)
    
    # Check if user is the teacher/host
    if request.user != meeting.teacher:
        return JsonResponse({'error': 'Only the meeting host can put it to sleep'}, status=403)
    
    # Can only sleep live meetings
    if meeting.status != 'live':
        return JsonResponse({'error': 'Only live meetings can be put to sleep'}, status=400)
    
    # Put meeting to sleep
    meeting.put_to_sleep()
    
    # Notify all participants that meeting is sleeping
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'meeting_{meeting.meeting_code}',
        {
            'type': 'meeting_sleeping',
            'message': 'Meeting has been put to sleep by the host'
        }
    )
    
    return JsonResponse({
        'status': 'success',
        'message': 'Meeting is now sleeping',
        'sleep_status': 'sleeping'
    })


@login_required
def unfreeze_meeting(request, meeting_code):
    """Unfreeze/wake up a sleeping meeting - only teacher/host can do this"""
    meeting = get_object_or_404(Meeting, meeting_code=meeting_code)
    
    # Check if user is the teacher/host
    if request.user != meeting.teacher:
        return JsonResponse({'error': 'Only the meeting host can unfreeze it'}, status=403)
    
    # Can only unfreeze sleeping meetings
    if meeting.sleep_status != 'sleeping':
        return JsonResponse({'error': 'Meeting is not in sleep mode'}, status=400)
    
    # Unfreeze the meeting
    meeting.unfreeze()
    
    # Notify all participants via WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'meeting_{meeting.meeting_code}',
        {
            'type': 'meeting_unfrozen',
            'message': 'Meeting is now active'
        }
    )
    
    return JsonResponse({
        'status': 'success',
        'message': 'Meeting is now active',
        'sleep_status': 'active'
    })


@login_required
def get_meeting_status(request, meeting_code):
    """Get current meeting status including sleep status"""
    meeting = get_object_or_404(Meeting, meeting_code=meeting_code)
    
    return JsonResponse({
        'status': meeting.status,
        'sleep_status': meeting.sleep_status,
        'can_join': meeting.can_join(),
        'is_teacher': request.user == meeting.teacher
    })




@login_required
@require_http_methods(["POST"])
def kick_participant(request, meeting_id, user_id):
    """Teacher kicks a student from a meeting with a 1-hour ban"""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    if meeting.teacher != request.user and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    user_to_kick = get_object_or_404(User, id=user_id)
    ban_until = timezone.now() + timezone.timedelta(hours=1)
    
    KickedParticipant.objects.update_or_create(
        meeting=meeting,
        user=user_to_kick,
        defaults={'banned_until': ban_until}
    )
    
    # Notify through websocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'meeting_{meeting.meeting_code}',
        {
            'type': 'kick_user',
            'user_id': user_to_kick.id,
            'message': 'You have been kicked by the teacher. You cannot rejoin for 1 hour.'
        }
    )
    
    return JsonResponse({'status': 'success', 'message': f'{user_to_kick.username} kicked successfully'})

@login_required
@require_http_methods(["POST"])
def update_participant_permission(request, meeting_id, user_id):
    """Grant or revoke specific permissions for a participant"""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    if meeting.teacher != request.user and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    participant = get_object_or_404(MeetingParticipant, meeting=meeting, user_id=user_id)
    
    import json
    data = json.loads(request.body)
    perm_type = data.get('type') # 'audio', 'video', 'screenshare'
    value = data.get('value') # True/False
    
    if perm_type == 'audio':
        participant.audio_permitted = value
    elif perm_type == 'video':
        participant.video_permitted = value
    elif perm_type == 'screenshare':
        participant.screenshare_permitted = value
    
    participant.save()
    
    # Notify through websocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'meeting_{meeting.meeting_code}',
        {
            'type': 'permission_update',
            'user_id': user_id,
            'permission_type': perm_type,
            'value': value,
            'message': f'Teacher has {"granted" if value else "revoked"} your {perm_type} permission.'
        }
    )
    
    return JsonResponse({'status': 'success'})

@login_required
@require_http_methods(["POST"])
def toggle_global_control(request, meeting_id):
    """Enable or disable global controls (mute all, camera off all, etc.)"""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    if meeting.teacher != request.user and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    import json
    data = json.loads(request.body)
    control_type = data.get('type') # 'mute_all', 'camera_off_all', 'screenshare_off_all'
    value = data.get('value')
    
    if control_type == 'mute_all':
        meeting.global_mute = value
    elif control_type == 'camera_off_all':
        meeting.global_camera_off = value
    elif control_type == 'screenshare_off_all':
        meeting.global_screenshare_off = value
    
    meeting.save()
    
    # Notify through websocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'meeting_{meeting.meeting_code}',
        {
            'type': 'global_control_update',
            'control_type': control_type,
            'value': value,
            'message': f'Teacher has {"enabled" if value else "disabled"} global {control_type.replace("_", " ")}.'
        }
    )
    
    return JsonResponse({'status': 'success'})

@login_required
@require_http_methods(["POST"])
def revoke_ban(request, meeting_id, user_id):
    """Teacher unbans a student before the 1-hour limit"""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    if meeting.teacher != request.user and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    KickedParticipant.objects.filter(meeting=meeting, user_id=user_id).delete()
    return JsonResponse({'status': 'success', 'message': 'Ban revoked'})

@login_required
def get_banned_users(request, meeting_id):
    """Get list of banned users for a meeting"""
    meeting = get_object_or_404(Meeting, id=meeting_id)
    if meeting.teacher != request.user and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'})
    
    banned = KickedParticipant.objects.filter(meeting=meeting).select_related('user')
    data = [{
        'id': b.user.id,
        'username': b.user.username,
        'banned_until': b.banned_until.isoformat()
    } for b in banned if b.is_banned()]
    
    return JsonResponse({'banned': data})
