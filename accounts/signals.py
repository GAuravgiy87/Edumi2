"""
Storage optimization signals for accounts app.
Compresses profile pictures on save to keep media/ lean.
"""
import io
import logging
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import UserProfile

logger = logging.getLogger('accounts')

MAX_DIMENSION = 300   # px — profile pics don't need to be large
JPEG_QUALITY  = 80


@receiver(pre_save, sender=UserProfile)
def compress_profile_picture(sender, instance, **kwargs):
    """Resize + compress profile picture before saving. Max 300x300, JPEG q80."""
    if not instance.profile_picture:
        return

    try:
        # Only process if it's a new/changed file (not already saved path)
        pic = instance.profile_picture
        if not hasattr(pic, 'file'):
            return

        from PIL import Image
        img = Image.open(pic).convert('RGB')

        # Skip if already small enough
        if img.width <= MAX_DIMENSION and img.height <= MAX_DIMENSION:
            return

        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=JPEG_QUALITY, optimize=True)
        buf.seek(0)

        # Replace file content in-place
        pic.file = buf
        pic.name = pic.name.rsplit('.', 1)[0] + '.jpg'
        logger.debug(f"Compressed profile picture for {instance.user_id}")
    except Exception as e:
        logger.warning(f"Profile picture compression failed: {e}")
