import time

# Fixed at process start — busts cache on redeploy, not every second
_BOOT_TS = int(time.time())

def timestamp(request):
    """Cache-busting timestamp — fixed per process, not per request."""
    return {'timestamp': _BOOT_TS}
