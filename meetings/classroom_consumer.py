"""
WebSocket consumer for real-time classroom updates.

Route: ws/classroom/<classroom_id>/

Events pushed to teacher:
  - new_join_request   → student submitted a join request
  - student_left       → student left the classroom

Events pushed to student:
  - request_approved   → teacher approved their request
  - request_denied     → teacher denied their request
  - meeting_started    → teacher started a meeting
  - meeting_ended      → active meeting ended
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)


class ClassroomConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.classroom_id = self.scope['url_route']['kwargs']['classroom_id']
        self.room_group = f'classroom_{self.classroom_id}'

        # Verify the user actually belongs to this classroom
        allowed = await self._check_access()
        if not allowed:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group'):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data):
        # Clients don't need to send anything on this channel
        pass

    # ── Group message handlers ────────────────────────────────────

    async def new_join_request(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_join_request',
            'membership_id': event['membership_id'],
            'student_id': event['student_id'],
            'student_name': event['student_name'],
            'student_email': event['student_email'],
            'requested_at': event['requested_at'],
        }))

    async def request_approved(self, event):
        # Only deliver to the targeted student
        if str(event.get('target_student_id')) != str(self.user.id):
            return
        await self.send(text_data=json.dumps({
            'type': 'request_approved',
            'classroom_id': event['classroom_id'],
            'classroom_title': event['classroom_title'],
            'classroom_code': event['classroom_code'],
        }))

    async def request_denied(self, event):
        # Only deliver to the targeted student
        if str(event.get('target_student_id')) != str(self.user.id):
            return
        await self.send(text_data=json.dumps({
            'type': 'request_denied',
            'classroom_id': event['classroom_id'],
            'classroom_title': event['classroom_title'],
        }))

    async def meeting_started(self, event):
        await self.send(text_data=json.dumps({
            'type': 'meeting_started',
            'meeting_code': event['meeting_code'],
            'meeting_title': event['meeting_title'],
        }))

    async def meeting_ended(self, event):
        await self.send(text_data=json.dumps({
            'type': 'meeting_ended',
        }))

    async def student_removed(self, event):
        await self.send(text_data=json.dumps({
            'type': 'student_removed',
            'student_id': event['student_id'],
            'membership_id': event['membership_id'],
        }))

    async def pending_count_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'pending_count_update',
            'count': event['count'],
        }))

    # ── DB helpers ────────────────────────────────────────────────

    @database_sync_to_async
    def _check_access(self):
        from .models import Classroom, ClassroomMembership
        try:
            classroom = Classroom.objects.get(id=self.classroom_id)
            if classroom.teacher == self.user:
                return True
            return ClassroomMembership.objects.filter(
                classroom=classroom,
                student=self.user,
                status__in=['approved', 'pending'],
            ).exists()
        except Classroom.DoesNotExist:
            return False
