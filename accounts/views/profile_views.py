"""
User profile views: view, edit, directory, search.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db import models

from accounts.models import UserProfile
from meetings.models import Meeting
from cameras.models import Camera

User = get_user_model()


@login_required
def profile_view(request, username=None):
    """View any user's profile; handles own-profile POST updates."""
    if username:
        profile_user = get_object_or_404(User, username=username)
    else:
        profile_user = request.user

    try:
        profile = profile_user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=profile_user, user_type='teacher') if profile_user.is_superuser else None

    is_own_profile = request.user == profile_user

    if is_own_profile and request.method == 'POST':
        try:
            if not profile:
                profile = UserProfile.objects.create(user=request.user, user_type='teacher')

            request.user.first_name = request.POST.get('first_name', '').strip()
            request.user.last_name = request.POST.get('last_name', '').strip()
            request.user.email = request.POST.get('email', '').strip()
            request.user.save()

            profile.display_name = request.POST.get('display_name', '').strip()
            profile.bio = request.POST.get('bio', '').strip()
            profile.phone = request.POST.get('phone', '').strip()
            profile.address = request.POST.get('address', '').strip()

            avatar_choice = request.POST.get('avatar_choice', '').strip()
            if request.FILES.get('profile_picture'):
                profile.profile_picture = request.FILES['profile_picture']
                profile.avatar_url = None
            elif avatar_choice:
                profile.avatar_url = avatar_choice
                profile.profile_picture = None

            dob = request.POST.get('date_of_birth', '').strip()
            profile.date_of_birth = dob if dob else None
            profile.linkedin = request.POST.get('linkedin', '').strip()
            profile.twitter = request.POST.get('twitter', '').strip()
            profile.website = request.POST.get('website', '').strip()

            if profile.user_type == 'student':
                profile.student_id = request.POST.get('student_id', '').strip()
                profile.grade = request.POST.get('grade', '').strip()
                enrollment = request.POST.get('enrollment_date', '').strip()
                profile.enrollment_date = enrollment if enrollment else None
            elif profile.user_type == 'teacher':
                profile.employee_id = request.POST.get('employee_id', '').strip()
                profile.department = request.POST.get('department', '').strip()
                profile.specialization = request.POST.get('specialization', '').strip()
                join = request.POST.get('join_date', '').strip()
                profile.join_date = join if join else None

            profile.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile_view', username=request.user.username)
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')

    # Profile completion score
    completion = 0
    if is_own_profile and profile:
        if profile.display_name: completion += 10
        if profile_user.first_name: completion += 10
        if profile_user.last_name: completion += 10
        if profile_user.email: completion += 10
        if profile.bio: completion += 15
        if profile.phone: completion += 10
        if profile.date_of_birth: completion += 10
        if profile.address: completion += 10
        if profile.profile_picture or profile.avatar_url: completion += 15

    stats = {}
    if profile_user.is_superuser:
        stats['total_users'] = User.objects.count()
        stats['total_meetings'] = Meeting.objects.count()
        stats['live_meetings'] = Meeting.objects.filter(status='live').count()
        stats['total_cameras'] = Camera.objects.count()
    elif profile and profile.user_type == 'teacher':
        stats['total_meetings'] = Meeting.objects.filter(teacher=profile_user, classroom__isnull=True).count()
        stats['live_meetings'] = Meeting.objects.filter(teacher=profile_user, status='live', classroom__isnull=True).count()
        stats['completed_meetings'] = Meeting.objects.filter(teacher=profile_user, status='ended', classroom__isnull=True).count()
    elif profile and profile.user_type == 'student':
        stats['enrolled_courses'] = 6
        stats['completed_assignments'] = 15
        stats['meetings_attended'] = profile_user.meetingparticipant_set.count()

    return render(request, 'accounts/profile.html', {
        'profile_user': profile_user,
        'profile': profile,
        'is_own_profile': is_own_profile,
        'stats': stats,
        'completion': completion,
    })


@login_required
def edit_profile(request):
    """Simple edit profile form (alternative to profile_view POST)."""
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user, user_type='student')

    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()

        profile.display_name = request.POST.get('display_name', '')
        profile.bio = request.POST.get('bio', '')
        profile.phone = request.POST.get('phone', '')
        profile.address = request.POST.get('address', '')

        if request.FILES.get('profile_picture'):
            profile.profile_picture = request.FILES['profile_picture']

        dob = request.POST.get('date_of_birth')
        if dob:
            profile.date_of_birth = dob

        profile.linkedin = request.POST.get('linkedin', '')
        profile.twitter = request.POST.get('twitter', '')
        profile.website = request.POST.get('website', '')

        if profile.user_type == 'student':
            profile.student_id = request.POST.get('student_id', '')
            profile.grade = request.POST.get('grade', '')
            enrollment = request.POST.get('enrollment_date')
            if enrollment:
                profile.enrollment_date = enrollment
        elif profile.user_type == 'teacher':
            profile.employee_id = request.POST.get('employee_id', '')
            profile.department = request.POST.get('department', '')
            profile.specialization = request.POST.get('specialization', '')
            join = request.POST.get('join_date')
            if join:
                profile.join_date = join

        profile.save()
        return redirect('profile_view', username=request.user.username)

    return render(request, 'accounts/edit_profile.html', {'profile': profile})


@login_required
def directory(request):
    """View all teachers and students in a searchable directory."""
    teachers = User.objects.filter(userprofile__user_type='teacher').select_related('userprofile').order_by('username')
    students = User.objects.filter(userprofile__user_type='student').select_related('userprofile').order_by('username')
    return render(request, 'accounts/directory.html', {'teachers': teachers, 'students': students})


@login_required
def search_users(request):
    """Search for teachers and students by name/username/email."""
    query = request.GET.get('q', '').strip()
    user_type = request.GET.get('type', 'all')
    results = []

    if query:
        users = User.objects.filter(
            models.Q(username__icontains=query) |
            models.Q(first_name__icontains=query) |
            models.Q(last_name__icontains=query) |
            models.Q(email__icontains=query) |
            models.Q(userprofile__display_name__icontains=query)
        ).select_related('userprofile').distinct()

        if user_type == 'teacher':
            users = users.filter(userprofile__user_type='teacher')
        elif user_type == 'student':
            users = users.filter(userprofile__user_type='student')
        else:
            users = users.filter(userprofile__user_type__in=['teacher', 'student'])

        results = users[:20]

    return render(request, 'accounts/search_results.html', {
        'query': query, 'user_type': user_type, 'results': results,
    })
