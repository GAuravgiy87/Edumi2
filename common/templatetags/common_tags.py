"""
Custom template tags and filters for common use
"""
from django import template
from django.utils import timezone
from datetime import timedelta
from common.utils import format_duration, time_since, is_teacher, is_student, get_user_type

register = template.Library()


@register.filter(name='format_duration')
def format_duration_filter(seconds):
    """
    Format seconds into human-readable duration
    Usage: {{ 3661|format_duration }} → "1h 1m 1s"
    """
    return format_duration(seconds)


@register.filter(name='time_since')
def time_since_filter(dt):
    """
    Show time since datetime
    Usage: {{ post.created_at|time_since }}
    """
    return time_since(dt)


@register.filter(name='is_teacher')
def is_teacher_filter(user):
    """
    Check if user is a teacher
    Usage: {% if user|is_teacher %}
    """
    return is_teacher(user)


@register.filter(name='is_student')
def is_student_filter(user):
    """
    Check if user is a student
    Usage: {% if user|is_student %}
    """
    return is_student(user)


@register.simple_tag
def get_user_type_tag(user):
    """
    Get user type as template tag
    Usage: {% get_user_type_tag user as user_type %}
    """
    return get_user_type(user)


@register.filter(name='percentage')
def percentage(value, total):
    """
    Calculate percentage
    Usage: {{ value|percentage:total }}
    """
    if total == 0:
        return 0
    return round((value / total) * 100)


@register.filter(name='truncate_chars')
def truncate_chars(text, max_length):
    """
    Truncate text to max_length with ellipsis
    Usage: {{ long_text|truncate_chars:50 }}
    """
    if not text:
        return ""
    
    text = str(text)
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."
