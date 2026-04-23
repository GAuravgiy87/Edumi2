from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from meetings.models import Meeting, MeetingParticipant, Classroom, ClassroomMembership, MeetingAttendanceLog, MeetingChat, MeetingSummary
from meetings.tasks import generate_meeting_summary
from meetings.realtime import (
    push_new_join_request, push_request_approved, push_request_denied,
    push_student_removed, push_meeting_started, push_meeting_ended, push_pending_count,
)
from school_project.ratelimit import rate_limit, by_user
from accounts.notification_utils import (
    notify_classroom_join_request, 
    notify_classroom_request_approved, 
    notify_student_joined_classroom,
    notify_classroom_request_denied,
    notify_student_removed_from_classroom,
    notify_meeting_started,
    notify_meeting_cancelled
)
import random
import string

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
@rate_limit(by_user, limit=5, window=60, message='Too many join requests. Please wait a minute.')
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
        membership = ClassroomMembership.objects.create(
            classroom=classroom,
            student=request.user,
            status='pending'
        )
        
        # Send notification to teacher
        notify_classroom_join_request(request.user, classroom)
        # Push real-time event to teacher's classroom page
        push_new_join_request(classroom.id, membership)
        
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
@rate_limit(by_user, limit=30, window=60, message='Too many approval actions.')
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

    # Push real-time events
    push_request_approved(membership.classroom.id, membership.student.id, membership.classroom)
    pending_count = membership.classroom.get_pending_requests().count()
    push_pending_count(membership.classroom.id, pending_count)
    
    return JsonResponse({
        'status': 'success',
        'message': f'{membership.student.username} approved',
        'student_id': membership.student.id,
        'membership_id': membership.id,
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

    # Push real-time events
    push_request_denied(membership.classroom.id, membership.student.id, membership.classroom)
    pending_count = membership.classroom.get_pending_requests().count()
    push_pending_count(membership.classroom.id, pending_count)
    
    return JsonResponse({
        'status': 'success',
        'message': f'{membership.student.username} denied',
        'student_id': membership.student.id,
        'membership_id': membership.id,
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

    # Push real-time event
    push_student_removed(membership.classroom.id, membership.student.id, membership.id)
    
    return JsonResponse({
        'status': 'success',
        'message': f'{membership.student.username} removed from classroom',
        'student_id': membership.student.id,
        'membership_id': membership.id,
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
        title = request.POST.get('title', classroom.title)
        duration_minutes = int(request.POST.get('duration_minutes', 60))
        allow_screen_share = request.POST.get('allow_screen_share', 'on') == 'on'
        allow_chat = request.POST.get('allow_chat', 'on') == 'on'
        record_meeting = request.POST.get('record_meeting') == 'on'
        
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
        # Push real-time event to all classroom members
        push_meeting_started(classroom.id, meeting)
        
        messages.success(request, 'Meeting started successfully!')
        return redirect('join_meeting', meeting_code=meeting.meeting_code)
    
    return render(request, 'meetings/start_classroom_meeting.html', {'classroom': classroom})

# ==================== MEETING MANAGEMENT ====================


@login_required
def create_meeting(request):
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'teacher':
        return redirect('login')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        scheduled_time = request.POST.get('scheduled_time')
        duration_minutes = int(request.POST.get('duration_minutes', 60))
        allow_screen_share = request.POST.get('allow_screen_share') == 'on'
        allow_chat = request.POST.get('allow_chat') == 'on'
        
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
    
    # Create or get participant
    participant, created = MeetingParticipant.objects.get_or_create(
        meeting=meeting,
        user=request.user,
        defaults={'joined_at': timezone.now(), 'is_active': True}
    )
    
    if not created:
        participant.joined_at = timezone.now()
        participant.is_active = True
        participant.save()
    
    # Update meeting status to live if teacher joins
    if meeting.teacher == request.user and meeting.status == 'scheduled':
        meeting.status = 'live'
        meeting.save()
        
        # Send notification to all participants that meeting has started
        notify_meeting_started(meeting, meeting.classroom)
    
    from django.conf import settings as _s
    return render(request, 'meetings/meeting_room.html', {
        'meeting':  meeting,
        'is_host':  meeting.teacher == request.user or request.user.is_superuser,
        'sfu_url':  getattr(_s, 'SFU_URL', 'http://localhost:3000'),
    })

@login_required
def meeting_attendance(request, meeting_code):
    meeting = get_object_or_404(Meeting, meeting_code=meeting_code)
    
    # Check permission (Teacher of meeting or Superuser)
    if meeting.teacher != request.user and not request.user.is_superuser:
        return render(request, 'error.html', {'message': 'You do not have permission to view attendance for this meeting'})
    
    participants = meeting.participants.all().select_related('user').prefetch_related('attendance_logs')
    
    # Prepare logs for each participant
    logs = []
    for p in participants:
        participant_logs = p.attendance_logs.order_by('timestamp')
        logs.append({
            'participant': p,
            'logs': participant_logs
        })
    
    return render(request, 'meetings/attendance_report.html', {
        'meeting': meeting,
        'participants': participants,
        'logs': logs
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
    
    meeting.status = 'ended'
    meeting.ended_at = timezone.now()
    meeting.save()
    
    # Mark all participants as inactive
    MeetingParticipant.objects.filter(meeting=meeting, is_active=True).update(
        is_active=False,
        left_at=timezone.now()
    )
    
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
        push_meeting_ended(meeting.classroom.id)
        # Invalidate classroom meeting cache
        from django.core.cache import cache
        cache.delete(f'classroom_meetings_{meeting.classroom.id}')
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
        participant.is_active = False
        participant.left_at = timezone.now()
        participant.save()
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



