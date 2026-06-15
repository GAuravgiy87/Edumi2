"""
Simple in-process rate limiter using Redis.
Falls back to a no-op if Redis is unavailable so the app never crashes.
"""
import time
import logging
from functools import wraps
from django.http import JsonResponse
from django.core.cache import cache

logger = logging.getLogger(__name__)


def rate_limit(key_fn, limit: int, window: int, message: str = 'Too many requests. Please wait.'):
    """
    Decorator factory.

    key_fn(request) -> str   — unique key per user/IP
    limit  — max calls allowed in window
    window — time window in seconds
    """
    def decorator(view_fn):
        @wraps(view_fn)
        def wrapper(request, *args, **kwargs):
            try:
                key = f'rl:{key_fn(request)}'
                count = cache.get(key, 0)
                if count >= limit:
                    return JsonResponse({'status': 'error', 'message': message}, status=429)
                # Increment; set TTL only on first hit
                if count == 0:
                    cache.set(key, 1, timeout=window)
                else:
                    cache.incr(key)
            except Exception as exc:
                # Redis down — allow the request through, log the issue
                logger.warning('Rate limiter unavailable: %s', exc)
            return view_fn(request, *args, **kwargs)
        return wrapper
    return decorator


# Reusable key functions
def by_user(request):
    return f'user:{request.user.id}'

def by_ip(request):
    return f'ip:{request.META.get("REMOTE_ADDR", "unknown")}'
