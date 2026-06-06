class EdumiRouter:
    """
    A router to control all database operations on models in the
    application to load balance across multiple databases.
    """
    
    # Map app labels to their specific database
    # Anything not in this map goes to 'default'
    app_db_map = {
        'cameras': 'camera_db',
        'mobile_cameras': 'camera_db',
        'videos': 'video_db',
        'video_editing': 'video_db',
        'meetings': 'meeting_db',
        'attendance': 'meeting_db',
    }

    def db_for_read(self, model, **hints):
        """
        Attempts to read models go to their mapped database.
        """
        if model._meta.app_label in self.app_db_map:
            return self.app_db_map[model._meta.app_label]
        return 'default'

    def db_for_write(self, model, **hints):
        """
        Attempts to write models go to their mapped database.
        """
        if model._meta.app_label in self.app_db_map:
            return self.app_db_map[model._meta.app_label]
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow any relation between apps.
        Since we have disabled SQLite foreign key pragma,
        these cross-db relations will function perfectly without throwing integrity errors.
        """
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the apps only appear in the related database.
        """
        if app_label in self.app_db_map:
            return db == self.app_db_map[app_label]
        # Otherwise, they go to the default database
        return db == 'default'
