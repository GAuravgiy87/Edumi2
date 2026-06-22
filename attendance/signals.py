from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User


@receiver(post_save, sender=User)
def create_attendance_defaults(sender, instance, created, **kwargs):
    """
    When a new user is created, nothing is auto-created here
    (face profile is opt-in).  This signal file is kept as a
    hook for future auto-provisioning logic.
    """
    pass
