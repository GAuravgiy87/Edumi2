"""
Messaging views: inbox list, conversation detail, start conversation, send message.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import models

from accounts.messaging_models import Conversation, Message

User = get_user_model()


@login_required
def inbox(request):
    """View all conversations with optional user search."""
    search_query = request.GET.get('q', '').strip()
    conversations = request.user.conversations.all().prefetch_related(
        'participants', 'participants__userprofile', 'messages'
    )
    for conv in conversations:
        conv.other_user = conv.get_other_user(request.user)
        conv.last_msg = conv.get_last_message()
        conv.unread_count = conv.messages.filter(is_read=False).exclude(sender=request.user).count()

    search_results = []
    if search_query:
        search_results = User.objects.filter(
            models.Q(username__icontains=search_query) |
            models.Q(first_name__icontains=search_query) |
            models.Q(last_name__icontains=search_query) |
            models.Q(email__icontains=search_query) |
            models.Q(userprofile__display_name__icontains=search_query)
        ).exclude(id=request.user.id).select_related('userprofile').distinct()[:10]

    return render(request, 'accounts/inbox.html', {
        'conversations': conversations,
        'search_query': search_query,
        'search_results': search_results,
    })


@login_required
def conversation_detail(request, conversation_id):
    """View a specific conversation thread."""
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user not in conversation.participants.all():
        messages.error(request, 'You do not have access to this conversation')
        return redirect('inbox')
    conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    other_user = conversation.get_other_user(request.user)
    messages_list = conversation.messages.all().select_related('sender')
    return render(request, 'accounts/conversation.html', {
        'conversation': conversation,
        'other_user': other_user,
        'messages': messages_list,
    })


@login_required
def start_conversation(request, username):
    """Start a new (or resume existing) conversation with another user."""
    other_user = get_object_or_404(User, username=username)
    if other_user == request.user:
        messages.error(request, 'You cannot message yourself')
        return redirect('inbox')
    existing_conv = Conversation.objects.filter(participants=request.user).filter(participants=other_user).first()
    if existing_conv:
        return redirect('conversation_detail', conversation_id=existing_conv.id)
    conversation = Conversation.objects.create()
    conversation.participants.add(request.user, other_user)
    return redirect('conversation_detail', conversation_id=conversation.id)


@login_required
@require_http_methods(["POST"])
def send_message(request, conversation_id):
    """Send a message (text, image, or file) in a conversation."""
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user not in conversation.participants.all():
        return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)

    content = request.POST.get('content', '').strip()
    image = request.FILES.get('image')
    file = request.FILES.get('file')

    if not content and not image and not file:
        return JsonResponse({'status': 'error', 'message': 'Message cannot be empty'}, status=400)

    message = Message.objects.create(
        conversation=conversation, sender=request.user,
        content=content, image=image, file=file
    )
    conversation.save()

    from accounts.notification_utils import notify_new_message
    other_user = conversation.get_other_user(request.user)
    if other_user:
        notify_new_message(request.user, other_user, conversation_id, content=content)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'message_id': message.id,
            'content': message.content,
            'image_url': message.image.url if message.image else None,
            'file_url': message.file.url if message.file else None,
            'sender': message.sender.username,
            'created_at': message.created_at.strftime('%I:%M %p'),
        })
    return redirect('conversation_detail', conversation_id=conversation_id)
