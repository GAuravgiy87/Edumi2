"""
Utility functions for creating notifications
"""
from .notification_models import Notification
from django.contrib.auth.models import User


def notify_new_message(sender, recipient, conversation_id):
    """Send notification when a new message is sent"""
    if sender != recipient:  # Don't notify yourself
        Notification.create_message_notification(recipient, sender, conversation_id)


def notify_meeting_scheduled(meeting, classroom=None):
    """Send notification when a meeting is scheduled"""
    teacher = meeting.teacher
    
    if classroom:
        # Notify all approved students in the classroom
        students = classroom.get_approved_students()
        for student in students:
            Notification.create_meeting_scheduled_notification(student, meeting, teacher)
    # For non-classroom meetings, you could notify specific participants if needed


def notify_meeting_started(meeting, classroom=None):
    """Send notification when a meeting starts"""
    if classroom:
        # Notify all approved students in the classroom
        students = classroom.get_approved_students()
        for student in students:
            Notification.create_meeting_started_notification(student, meeting)
    else:
        # Notify all participants
        participants = meeting.participants.all()
        for participant in participants:
            if participant.user != meeting.teacher:
                Notification.create_meeting_started_notification(participant.user, meeting)


def notify_meeting_cancelled(meeting, classroom=None):
    """Send notification when a meeting is cancelled"""
    if classroom:
        # Notify all approved students in the classroom
        students = classroom.get_approved_students()
        for student in students:
            Notification.create_meeting_cancelled_notification(student, meeting)
    else:
        # Notify all participants
        participants = meeting.participants.all()
        for participant in participants:
            if participant.user != meeting.teacher:
                Notification.create_meeting_cancelled_notification(participant.user, meeting)


def notify_classroom_join_request(student, classroom):
    """Send notification to teacher when student requests to join classroom"""
    teacher = classroom.teacher
    Notification.create_classroom_join_request_notification(teacher, student, classroom)


def notify_classroom_request_approved(student, classroom, teacher):
    """Send notification to student when their join request is approved"""
    Notification.create_classroom_approved_notification(student, classroom, teacher)


def notify_classroom_request_denied(student, classroom):
    """Send notification to student when their join request is denied"""
    Notification.create_classroom_denied_notification(student, classroom)


def notify_student_removed_from_classroom(student, classroom):
    """Send notification to student when they are removed from classroom"""
    Notification.create_classroom_removed_notification(student, classroom)


def notify_student_joined_classroom(student, classroom):
    """Send notification to teacher when a student joins their classroom"""
    teacher = classroom.teacher
    Notification.create_student_joined_notification(teacher, student, classroom)


def notify_meeting_reminder(meeting, classroom=None):
    """Send reminder notification 15 minutes before meeting starts"""
    if classroom:
        # Notify all approved students in the classroom
        students = classroom.get_approved_students()
        for student in students:
            Notification.create_meeting_reminder_notification(student, meeting)
    else:
        # Notify all participants
        participants = meeting.participants.all()
        for participant in participants:
            if participant.user != meeting.teacher:
                Notification.create_meeting_reminder_notification(participant.user, meeting)
