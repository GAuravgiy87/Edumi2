import time

def timestamp(request):
    """Add timestamp for cache busting"""
    return {
        'timestamp': int(time.time())
    }
