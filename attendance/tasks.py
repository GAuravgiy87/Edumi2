import os
import logging
from pathlib import Path
from celery import shared_task
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone
from django.conf import settings
from .models import StudentFaceProfile
from .face_service import get_face_service

logger = logging.getLogger('attendance.tasks')


@shared_task
def process_face_registration(user_id, image_bytes, ip_address):
    """
    Background task: extract face embedding, encrypt, save to StudentFaceProfile.
    Compresses the stored photo to save disk space.
    """
    try:
        from PIL import Image
        import io

        user = User.objects.get(id=user_id)
        svc = get_face_service()

        result = svc.extract_embedding(image_bytes)
        if result['status'] != 'success':
            logger.error(f"Face processing failed for {user.username}: {result['message']}")
            return False

        encrypted, checksum = svc.prepare_for_storage(result['embedding'])

        # Compress photo before storing (max 400x400, JPEG quality 75)
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        img.thumbnail((400, 400), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=75, optimize=True)
        photo_file = ContentFile(buf.getvalue(), name=f"{user.username}_face.jpg")

        StudentFaceProfile.objects.update_or_create(
            student=user,
            defaults={
                'face_embedding_encrypted': encrypted,
                'embedding_checksum':       checksum,
                'face_quality_score':       result['quality'],
                'is_active':                True,
                'registration_ip':          ip_address,
                'face_photo':               photo_file,
            }
        )
        logger.info(f"Face registered for {user.username}")
        return True
    except Exception as e:
        logger.exception(f"process_face_registration error: {e}")
        return False


@shared_task
def cleanup_engagement_data():
    """
    Scheduled: delete engagement snapshots + CSV logs older than 24 hours.
    Runs daily via Celery beat.
    """
    from .models import StudentEngagementSnapshot
    import datetime

    cutoff = timezone.now() - datetime.timedelta(hours=24)

    deleted, _ = StudentEngagementSnapshot.objects.filter(timestamp__lt=cutoff).delete()
    logger.info(f"[Cleanup] Deleted {deleted} engagement snapshots")

    log_dir = Path(settings.MEDIA_ROOT) / 'meeting_logs'
    if log_dir.exists():
        removed = 0
        for f in log_dir.glob('*.csv'):
            if timezone.make_aware(
                timezone.datetime.fromtimestamp(f.stat().st_mtime)
            ) < cutoff:
                f.unlink()
                removed += 1
        logger.info(f"[Cleanup] Deleted {removed} CSV log files")


@shared_task
def cleanup_old_recordings():
    """
    Scheduled: delete meeting recordings older than 30 days.
    Runs daily via Celery beat.
    """
    import datetime

    recordings_dir = Path(settings.MEDIA_ROOT) / 'recordings'
    if not recordings_dir.exists():
        return

    cutoff = timezone.now() - datetime.timedelta(days=30)
    removed_files = 0
    removed_bytes = 0

    for meeting_dir in recordings_dir.iterdir():
        if not meeting_dir.is_dir():
            continue
        for f in meeting_dir.glob('*.mp4'):
            mtime = timezone.make_aware(
                timezone.datetime.fromtimestamp(f.stat().st_mtime)
            )
            if mtime < cutoff:
                removed_bytes += f.stat().st_size
                f.unlink()
                removed_files += 1
        # Remove empty meeting dirs
        if not any(meeting_dir.iterdir()):
            meeting_dir.rmdir()

    mb = removed_bytes / (1024 * 1024)
    logger.info(f"[Cleanup] Recordings: removed {removed_files} files ({mb:.1f} MB freed)")



@shared_task(bind=True, max_retries=0, ignore_result=False)
def run_face_recognition(self, frame_bytes_b64: str, encrypted_emb_b64: str,
                          threshold: float, prev_frame_b64=None) -> dict:
    """
    CPU-bound face recognition offloaded from the WebSocket event loop.
    Called by FaceAttendanceConsumer via delay() + AsyncResult.
    Returns the same dict as FaceService.compare_frame_to_stored().
    """
    import base64
    try:
        frame_bytes = base64.b64decode(frame_bytes_b64)
        encrypted_emb = base64.b64decode(encrypted_emb_b64)
        prev_bytes = base64.b64decode(prev_frame_b64) if prev_frame_b64 else None
        svc = get_face_service()
        return svc.compare_frame_to_stored(
            frame_bytes, encrypted_emb,
            threshold=threshold,
            prev_frame_bytes=prev_bytes,
        )
    except Exception as exc:
        logger.warning('run_face_recognition error: %s', exc)
        return {'match': False, 'event': 'error', 'confidence': 0.0, 'message': str(exc)}
