"""
Views for notification management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .notification_models import Notification


@login_required
def notifications_list(request):
    """Display all notifications for the current user"""
    notifications = Notification.objects.filter(recipient=request.user)[:50]
    unread_count = Notification.get_unread_count(request.user)
    
    return render(request, 'accounts/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count
    })


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.mark_as_read()
    
    return JsonResponse({'status': 'success'})


@login_required
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    """Mark all notifications as read for the current user"""
    Notification.mark_all_as_read(request.user)
    
    return JsonResponse({'status': 'success'})


@login_required
def get_unread_count(request):
    """Get unread notification count (for AJAX polling)"""
    count = Notification.get_unread_count(request.user)
    
    return JsonResponse({'count': count})


@login_required
def get_recent_notifications(request):
    """Get recent notifications (for dropdown)"""
    notifications = Notification.objects.filter(recipient=request.user)[:10]
    
    data = [{
        'id': n.id,
        'type': n.notification_type,
        'title': n.title,
        'message': n.message,
        'link': n.link,
        'is_read': n.is_read,
        'created_at': n.created_at.strftime('%b %d, %I:%M %p')
    } for n in notifications]
    
    return JsonResponse({
        'notifications': data,
        'unread_count': Notification.get_unread_count(request.user)
    })
