from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from .models import Meeting, MeetingParticipant, Classroom, ClassroomMembership
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
    
    # Check permissions
    is_teacher = classroom.teacher == request.user
    is_approved_student = ClassroomMembership.objects.filter(
        classroom=classroom,
        student=request.user,
        status='approved'
    ).exists()
    
    if not (is_teacher or is_approved_student):
        messages.error(request, 'You do not have access to this classroom')
        return redirect('student_classrooms')
    
    # Get data based on role
    if is_teacher:
        pending_requests = classroom.get_pending_requests()
        approved_students = classroom.get_approved_memberships()
        meetings = classroom.meetings.all().order_by('-created_at')
    else:
        pending_requests = None
        approved_students = None
        meetings = classroom.meetings.filter(status__in=['scheduled', 'live']).order_by('-created_at')
    
    active_meeting = classroom.get_active_meeting()
    
    return render(request, 'meetings/classroom_detail.html', {
        'classroom': classroom,
        'is_teacher': is_teacher,
        'pending_requests': pending_requests,
        'approved_students': approved_students,
        'meetings': meetings,
        'active_meeting': active_meeting
    })

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
        from accounts.notification_utils import notify_classroom_join_request
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
    from accounts.notification_utils import notify_classroom_request_approved, notify_student_joined_classroom
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
    from accounts.notification_utils import notify_classroom_request_denied
    notify_classroom_request_denied(membership.student, membership.classroom)
    membership.save()
    
    return JsonResponse({
        'status': 'success',
        'message': f'{membership.student.username} denied'
    })

@login_required
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
    from accounts.notification_utils import notify_student_removed_from_classroom
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
        from accounts.notification_utils import notify_meeting_started
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
    
    return render(request, 'meetings/teacher_meetings.html', {
        'meetings': meetings,
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
        from accounts.notification_utils import notify_meeting_started
        notify_meeting_started(meeting, meeting.classroom)
    
    return render(request, 'meetings/meeting_room.html', {
        'meeting': meeting,
        'is_host': meeting.teacher == request.user
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
    from accounts.notification_utils import notify_meeting_cancelled
    notify_meeting_cancelled(meeting, meeting.classroom)
    
    return JsonResponse({'status': 'success'})
