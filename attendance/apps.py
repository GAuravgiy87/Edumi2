from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance'
    verbose_name = 'Attendance Management'

    def ready(self):
        from . import signals  # noqa
        # Run GPU setup here — app registry is fully loaded at this point
        try:
            from scripts.gpu_setup import get_gpu_config
            from django.conf import settings
            cfg = get_gpu_config()
            settings.GPU_CONFIG = cfg
            # Update Celery concurrency based on actual GPU config
            settings.CELERY_WORKER_CONCURRENCY = cfg['threads'].get('celery_workers', 2)
        except Exception:
            pass  # safe defaults already set in settings.py
