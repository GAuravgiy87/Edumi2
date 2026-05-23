from django.apps import AppConfig


class CamerasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cameras'

    def ready(self):
        # Run orphaned recording cleanup in a thread to not block startup
        import threading
        from .recording_engine import cleanup_orphaned_recordings
        threading.Thread(target=cleanup_orphaned_recordings, daemon=True).start()
