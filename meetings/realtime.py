"""
Helpers to push real-time events to classroom WebSocket groups.
Call these from any synchronous Django view.
"""
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def _send(group: str, payload: dict):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(group, payload)


def push_new_join_request(classroom_id, membership):
    """Notify the teacher's classroom page that a new request arrived."""
    student = membership.student
    _send(f'classroom_{classroom_id}', {
        'type': 'new_join_request',
        'membership_id': membership.id,
        'student_id': student.id,
        'student_name': student.get_full_name() or student.username,
        'student_email': student.email,
        'requested_at': membership.requested_at.strftime('%b %d, %Y %H:%M'),
    })


def push_request_approved(classroom_id, student_id, classroom):
    """Notify the specific student that their request was approved."""
    # We broadcast to the whole classroom group; the student filters by their own user_id
    _send(f'classroom_{classroom_id}', {
        'type': 'request_approved',
        'target_student_id': student_id,
        'classroom_id': classroom.id,
        'classroom_title': classroom.title,
        'classroom_code': classroom.class_code,
    })


def push_request_denied(classroom_id, student_id, classroom):
    """Notify the specific student that their request was denied."""
    _send(f'classroom_{classroom_id}', {
        'type': 'request_denied',
        'target_student_id': student_id,
        'classroom_id': classroom.id,
        'classroom_title': classroom.title,
    })


def push_student_removed(classroom_id, student_id, membership_id):
    """Notify everyone that a student was removed."""
    _send(f'classroom_{classroom_id}', {
        'type': 'student_removed',
        'student_id': student_id,
        'membership_id': membership_id,
    })


def push_meeting_started(classroom_id, meeting):
    """Notify all classroom members that a meeting has started."""
    _send(f'classroom_{classroom_id}', {
        'type': 'meeting_started',
        'meeting_code': meeting.meeting_code,
        'meeting_title': meeting.title,
    })


def push_meeting_ended(classroom_id):
    """Notify all classroom members that the meeting ended."""
    _send(f'classroom_{classroom_id}', {
        'type': 'meeting_ended',
    })


def push_pending_count(classroom_id, count: int):
    """Update the pending requests badge count for the teacher."""
    _send(f'classroom_{classroom_id}', {
        'type': 'pending_count_update',
        'count': count,
    })
