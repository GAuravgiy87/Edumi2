"""
Edit action management views
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.db import transaction

from video_editing.models import VideoEditSession, VideoEditAction


@login_required
@require_http_methods(["POST"])
def add_edit_action(request, session_id):
    """Add an edit action to the session."""
    session = get_object_or_404(VideoEditSession, id=session_id, created_by=request.user)

    action_type = request.POST.get('action_type')
    parameters = {}  

    # Parse parameters based on action type
    if action_type == 'split':
        parameters = {
            'split_point': float(request.POST.get('split_point', 0))
        }
    elif action_type == 'trim':
        parameters = {
            'start_time': float(request.POST.get('start_time', 0)),
            'end_time': float(request.POST.get('end_time', 0))
        }
    elif action_type == 'mute':
        parameters = {
            'start_time': float(request.POST.get('start_time', 0)),
            'end_time': float(request.POST.get('end_time', 0))
        }
    elif action_type == 'rotate':
        parameters = {
            'degrees': int(request.POST.get('degrees', 90))
        }
    elif action_type == 'add_text':
        parameters = {
            'text': request.POST.get('text', ''),
            'font_size': int(request.POST.get('font_size', 24)),
            'color': request.POST.get('color', '#ffffff'),
            'position': request.POST.get('position', 'center'),
            'start_time': float(request.POST.get('start_time', 0)),
            'end_time': float(request.POST.get('end_time', 0))
        }
    elif action_type in ['add_audio', 'replace_audio']:
        parameters = {
            'start_time': float(request.POST.get('start_time', 0)),
            'volume': int(request.POST.get('volume', 100))
        }

    with transaction.atomic():
        last_order = session.actions.count()
        edit_action = VideoEditAction.objects.create(
            session=session,
            action_type=action_type,
            parameters=parameters,
            order=last_order
        )

        # Handle audio file upload
        if 'audio' in request.FILES:
            edit_action.audio_file = request.FILES['audio']
            edit_action.save()

    return JsonResponse({
        'status': 'success',
        'action': {
            'id': edit_action.id,
            'action_type': edit_action.action_type,
            'action_type_display': edit_action.get_action_type_display(),
            'parameters': edit_action.parameters,
            'order': edit_action.order,
        }
    })


@login_required
@require_http_methods(["POST"])
def remove_edit_action(request, action_id):
    """Remove an edit action from the session."""
    action = get_object_or_404(VideoEditAction, id=action_id, session__created_by=request.user)
    action.delete()
    return JsonResponse({'status': 'success'})
