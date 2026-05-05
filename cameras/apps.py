from django.apps import AppConfig


class CamerasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cameras'

    def ready(self):
        # Only start the camera service in the main process (not in migrations,
        # management commands, or Daphne's worker threads).
        import os
        import sys

        # Skip during manage.py commands other than runserver/daphne
        is_manage_cmd = os.path.basename(sys.argv[0]) == 'manage.py'
        if is_manage_cmd:
            cmd = sys.argv[1] if len(sys.argv) > 1 else ''
            if cmd not in ('runserver', 'daphne'):
                return

        # Skip in RUN_MAIN reloader child process (Django dev server spawns two)
        if os.environ.get('RUN_MAIN') == 'true':
            return

        from cameras.camera_service_manager import start
        start()
