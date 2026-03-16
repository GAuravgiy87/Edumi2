"""
WebSocket consumer for real-time face-recognition attendance.

Route: ws/attendance/<meeting_code>/

Flow:
  1. Student connects → consumer fetches their encrypted face embedding.
  2. Browser sends periodic base64 JPEG frames (canvas snapshot of localVideo).
  3. Consumer decodes frame → FaceService → compare against stored embedding.
  4. After enough verified seconds → AttendanceRecord saved as 'present'.
  5. No images or frames are ever persisted.
"""
import json
import base64
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger('attendance.consumers')


class FaceAttendanceConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user         = self.scope['user']
        self.meeting_code = self.scope['url_route']['kwargs']['meeting_code']

        if not self.user.is_authenticated:
            await self.close()
            return

        # Load settings & cached embedding bytes
        self.att_settings    = await self.get_settings()
        self.encrypted_emb   = await self.get_encrypted_embedding()
        self.verified_seconds = 0
        self.attendance_marked = False
        self.join_time = timezone.now()

        await self.accept()
        await self.send(json.dumps({
            'type':     'connected',
            'interval': self.att_settings.get('interval', 15),
            'message':  'Face recognition active – your camera is being verified.',
            'has_profile': self.encrypted_emb is not None,
        }))

        if self.encrypted_emb is None:
            await self.send(json.dumps({
                'type':    'no_profile',
                'message': '⚠ No face profile found. Please register your face in Settings.',
            }))

    async def disconnect(self, close_code):
        pass  # No channel-groups used; nothing to clean up.

    async def receive(self, text_data):
        """Receive a base64-encoded JPEG frame from the browser."""
        if self.attendance_marked or self.encrypted_emb is None:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if data.get('type') != 'frame':
            return

        frame_b64 = data.get('frame', '')
        if not frame_b64:
            return

        try:
            frame_bytes = base64.b64decode(frame_b64)
        except Exception:
            return

        # Run CPU-bound recognition in thread pool
        result = await database_sync_to_async(self._run_recognition)(frame_bytes)

        # Log the attempt (no images stored)
        await self._log_attempt(result['event'], result['confidence'])

        if result['match']:
            interval = self.att_settings.get('interval', 15)
            self.verified_seconds += interval
            threshold = self.att_settings.get('presence_duration', 30)

            if self.verified_seconds >= threshold:
                await self._mark_present(result['confidence'])
                self.attendance_marked = True
                await self.send(json.dumps({
                    'type':       'attendance_marked',
                    'status':     'present',
                    'confidence': result['confidence'],
                    'message':    '✅ Attendance recorded successfully!',
                }))
            else:
                await self.send(json.dumps({
                    'type':             'verification_progress',
                    'confidence':       result['confidence'],
                    'verified_seconds': self.verified_seconds,
                    'required_seconds': threshold,
                    'message':          f"🔍 Verified {self.verified_seconds}s / {threshold}s",
                }))
        else:
            await self.send(json.dumps({
                'type':       'verification_failed',
                'event':      result.get('event', 'match_failed'),
                'confidence': result.get('confidence', 0.0),
                'message':    result.get('message', 'Face not recognized.'),
            }))

    # ── Sync helpers (run in thread pool) ──────────────────────────

    def _run_recognition(self, frame_bytes: bytes) -> dict:
        from .face_service import FaceService
        svc = FaceService()
        return svc.compare_frame_to_stored(frame_bytes, self.encrypted_emb)

    # ── Async DB helpers ────────────────────────────────────────────

    @database_sync_to_async
    def get_encrypted_embedding(self):
        from .models import StudentFaceProfile
        try:
            profile = StudentFaceProfile.objects.get(
                student=self.user, is_active=True
            )
            return bytes(profile.face_embedding_encrypted)
        except StudentFaceProfile.DoesNotExist:
            return None

    @database_sync_to_async
    def get_settings(self) -> dict:
        from meetings.models import Meeting
        from .models import AttendanceSettings
        defaults = {'interval': 15, 'presence_duration': 30, 'late_threshold': 10,
                    'enabled': True, 'confidence_threshold': 0.55}
        try:
            meeting  = Meeting.objects.select_related('classroom').get(
                meeting_code=self.meeting_code
            )
            s, _ = AttendanceSettings.objects.get_or_create(classroom=meeting.classroom)
            return {
                'interval':            s.recognition_interval_seconds,
                'presence_duration':   s.presence_duration_seconds,
                'late_threshold':      s.late_threshold_minutes,
                'enabled':             s.face_recognition_enabled,
                'confidence_threshold': s.confidence_threshold,
            }
        except Exception:
            return defaults

    @database_sync_to_async
    def _mark_present(self, confidence: float):
        from meetings.models import Meeting
        from .models import AttendanceRecord
        now = timezone.now()

        # Determine if student is late
        meeting_start = self.join_time  # approximate
        late_threshold = self.att_settings.get('late_threshold', 10)
        try:
            meeting = Meeting.objects.select_related('classroom').get(
                meeting_code=self.meeting_code
            )
            minutes_late = (now - meeting.scheduled_time).total_seconds() / 60
            status = 'late' if minutes_late > late_threshold else 'present'
        except Exception:
            meeting = None
            status  = 'present'

        if meeting:
            AttendanceRecord.objects.update_or_create(
                student=self.user,
                meeting=meeting,
                defaults={
                    'classroom':            meeting.classroom,
                    'date':                 now.date(),
                    'status':               status,
                    'face_match_confidence': confidence,
                    'face_verified_at':      now,
                    'marked_present_at':     now,
                    'verification_method':   'face_recognition',
                }
            )
            # Update last_verified_at on the face profile
            from .models import StudentFaceProfile
            StudentFaceProfile.objects.filter(student=self.user).update(
                last_verified_at=now
            )

    @database_sync_to_async
    def _log_attempt(self, event_type: str, confidence: float):
        from meetings.models import Meeting
        from .models import FaceRecognitionLog
        try:
            meeting = Meeting.objects.get(meeting_code=self.meeting_code)
            FaceRecognitionLog.objects.create(
                student=self.user,
                meeting=meeting,
                event_type=event_type,
                confidence_score=confidence,
            )
        except Exception:
            pass
