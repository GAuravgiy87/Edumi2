"""
Service layer for Accounts app.
Contains business logic for profile management and dashboards.
"""
from django.contrib.auth.models import User
from .models import UserProfile
from meetings.models import Meeting
def get_profile_completion(user):
    """Calculate profile completion percentage."""
    if not hasattr(user, 'userprofile'):
        return 0
    profile = user.userprofile
    completion = 0
    if profile.display_name: completion += 10
    if user.first_name: completion += 10
    if user.last_name: completion += 10
    if user.email: completion += 10
    if profile.bio: completion += 15
    if profile.phone: completion += 10
    if profile.date_of_birth: completion += 10
    if profile.address: completion += 10
    if profile.profile_picture or profile.avatar_url: completion += 15
    return completion

def get_teacher_stats(user):
    """Get statistics for the teacher dashboard."""
    return {
        'total_meetings': Meeting.objects.filter(teacher=user, classroom__isnull=True).count(),
        'live_meetings': Meeting.objects.filter(teacher=user, status='live', classroom__isnull=True).count(),
        'scheduled_meetings': Meeting.objects.filter(teacher=user, status='scheduled', classroom__isnull=True).count(),
        'completed_meetings': Meeting.objects.filter(teacher=user, status='ended', classroom__isnull=True).count(),
    }

def get_student_stats(user):
    """Get statistics for the student dashboard."""
    return {
        'available_meetings': Meeting.objects.filter(status__in=['scheduled', 'live'], classroom__isnull=True).count(),
        'attended_meetings': user.meetingparticipant_set.filter(meeting__classroom__isnull=True).count(),
        'enrolled_courses': 6,  # Placeholder/Future logic
        'completed_assignments': 15,  # Placeholder/Future logic
    }

def get_admin_stats():
    """Get overall platform statistics for the admin panel."""
    return {
        'total_users': User.objects.count(),
        'total_students': UserProfile.objects.filter(user_type='student').count(),
        'total_teachers': UserProfile.objects.filter(user_type='teacher').count(),
        'total_meetings': Meeting.objects.filter(classroom__isnull=True).count(),
        'live_meetings_count': Meeting.objects.filter(status='live', classroom__isnull=True).count(),
    }
