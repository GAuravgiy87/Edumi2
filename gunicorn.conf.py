"""
Gunicorn configuration for Edumi2 Production
Optimized for high performance with Django Channels/WebSocket support
"""
import os
import multiprocessing

# Server socket binding
bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8000')

# Number of worker processes
# Formula: (2 x CPU cores) + 1, but limited for WebSocket-heavy apps
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))

# Worker class - Uvicorn for ASGI (WebSocket) support
worker_class = 'uvicorn.workers.UvicornWorker'

# Worker connections (for async workers)
worker_connections = int(os.environ.get('GUNICORN_WORKER_CONNECTIONS', '1000'))

# Maximum requests per worker (prevents memory leaks)
max_requests = int(os.environ.get('GUNICORN_MAX_REQUESTS', '10000'))
max_requests_jitter = int(os.environ.get('GUNICORN_MAX_REQUESTS_JITTER', '1000'))

# Timeout settings
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '120'))
graceful_timeout = int(os.environ.get('GUNICORN_GRACEFUL_TIMEOUT', '30'))
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', '5'))

# Logging
accesslog = os.environ.get('GUNICORN_ACCESS_LOG', '-')
errorlog = os.environ.get('GUNICORN_ERROR_LOG', '-')
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'edumi2'

# Server mechanics
daemon = False
pidfile = os.environ.get('GUNICORN_PIDFILE', 'gunicorn.pid')

# SSL (optional - set via environment variables)
keyfile = os.environ.get('SSL_KEYFILE', None)
certfile = os.environ.get('SSL_CERTFILE', None)

# Preload application for memory efficiency
preload_app = True

# Worker temporary directory
worker_tmp_dir = '/dev/shm' if os.path.exists('/dev/shm') else None


def on_starting(server):
    """Called just before the master process is initialized."""
    print(f"🚀 Starting Edumi2 with {workers} workers on {bind}")


def on_reload(server):
    """Called when receiving SIGHUP signal."""
    print("🔄 Reloading configuration...")


def when_ready(server):
    """Called just after the server is started."""
    print(f"✅ Edumi2 server ready at http://{bind}")


def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    worker.log.info("Worker received INT or QUIT signal")


def on_exit(server):
    """Called just before exiting Gunicorn."""
    print("👋 Shutting down Edumi2 server")
