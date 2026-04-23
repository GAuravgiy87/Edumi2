from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance'
    verbose_name = 'Attendance Management'

    def ready(self):
        from . import signals  # noqa
        # Configure OpenCV thread count to avoid CPU saturation
        try:
            import cv2, os
            # Cap OpenCV to half the available cores — leave room for Django/Celery
            threads = max(1, (os.cpu_count() or 4) // 2)
            cv2.setNumThreads(threads)
            cv2.ocl.setUseOpenCL(True)  # enable GPU if available, no-op if not
        except Exception:
            pass
