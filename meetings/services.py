"""
Service layer for Meetings app.
"""
from django.utils import timezone
from django.core.cache import cache
from .models import Meeting, MeetingParticipant, Classroom, ClassroomMembership, MeetingSummary
from attendance.models import AttendanceRecord
from django.db.models import Count, Q


def get_classroom_detail_context(classroom, user):
    """Get context for classroom detail view based on user role."""
    is_teacher = classroom.teacher == user
    is_approved_student = ClassroomMembership.objects.filter(
        classroom=classroom, student=user, status='approved'
    ).exists()

    if not (is_teacher or is_approved_student):
        return None

    context = {
        'classroom': classroom,
        'is_teacher': is_teacher,
        'active_meeting': classroom.get_active_meeting(),
    }

    if is_teacher:
        approved_students = classroom.get_approved_memberships()
        att_total_count = approved_students.count()

        # Cache meeting list for 60s — avoids repeated annotate() on every page load
        cache_key = f'classroom_meetings_{classroom.id}'
        meetings = cache.get(cache_key)
        if meetings is None:
            meetings = list(
                classroom.meetings.all()
                .annotate(att_present=Count(
                    'face_attendance_records',
                    filter=Q(face_attendance_records__status__in=['present', 'late'])
                ))
                .order_by('-created_at')
                [:20]  # cap at 20 — no need to load entire history
            )
            cache.set(cache_key, meetings, 60)

        for m in meetings:
            m.att_total = att_total_count

        context.update({
            'pending_requests': classroom.get_pending_requests(),
            'approved_students': approved_students,
            'meetings': meetings,
        })
    else:
        context.update({
            'meetings': classroom.meetings.filter(
                status__in=['scheduled', 'live']
            ).order_by('-created_at')[:10],
            'pending_requests': None,
            'approved_students': None,
        })

    return context
