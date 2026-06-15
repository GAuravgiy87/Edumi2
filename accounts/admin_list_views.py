"""Admin list views — paginated, minimal DB load."""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from meetings.models import Meeting

PAGE_SIZE = 25


def _admin_required(user):
    return user.is_superuser


@login_required
def admin_all_users(request):
    if not _admin_required(request.user):
        return redirect('login')
    qs = (
        User.objects
        .select_related('userprofile')
        .only('id', 'username', 'email', 'date_joined', 'is_active',
              'userprofile__user_type')
        .order_by('-date_joined')
    )
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get('page', 1))
    return render(request, 'accounts/admin_all_users.html', {
        'users': page, 'total_count': qs.count()
    })


@login_required
def admin_all_students(request):
    if not _admin_required(request.user):
        return redirect('login')
    qs = (
        User.objects
        .filter(userprofile__user_type='student')
        .select_related('userprofile')
        .only('id', 'username', 'email', 'date_joined', 'userprofile__user_type')
        .order_by('-date_joined')
    )
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get('page', 1))
    return render(request, 'accounts/admin_all_students.html', {
        'students': page, 'total_count': qs.count()
    })


@login_required
def admin_all_teachers(request):
    if not _admin_required(request.user):
        return redirect('login')
    qs = (
        User.objects
        .filter(userprofile__user_type='teacher')
        .select_related('userprofile')
        .only('id', 'username', 'email', 'date_joined', 'userprofile__user_type')
        .order_by('-date_joined')
    )
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get('page', 1))
    return render(request, 'accounts/admin_all_teachers.html', {
        'teachers': page, 'total_count': qs.count()
    })


@login_required
def admin_all_meetings(request):
    if not _admin_required(request.user):
        return redirect('login')
    qs = (
        Meeting.objects
        .filter(classroom__isnull=True)
        .select_related('teacher')
        .only('id', 'title', 'meeting_code', 'status', 'scheduled_time',
              'teacher__username')
        .order_by('-scheduled_time')
    )
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get('page', 1))
    return render(request, 'accounts/admin_all_meetings.html', {
        'meetings': page, 'total_count': qs.count()
    })


@login_required
def admin_live_meetings(request):
    if not _admin_required(request.user):
        return redirect('login')
    # Live meetings are few — no pagination needed, but still use .only()
    meetings = (
        Meeting.objects
        .filter(status='live', classroom__isnull=True)
        .select_related('teacher')
        .only('id', 'title', 'meeting_code', 'status', 'scheduled_time',
              'teacher__username')
        .order_by('-scheduled_time')
    )
    return render(request, 'accounts/admin_live_meetings.html', {
        'meetings': meetings, 'total_count': meetings.count()
    })
