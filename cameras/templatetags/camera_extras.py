from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if dictionary and key:
        return dictionary.get(key, [])
    return []

@register.filter
def duration_format(duration):
    """Format duration timedelta to H:M:S"""
    if not duration:
        return ""
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"

@register.filter
def filter_published(recordings):
    """Filter recordings that are published"""
    if not recordings:
        return []
    return [r for r in recordings if r.is_published]
