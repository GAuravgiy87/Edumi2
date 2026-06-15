"""
MeetingConsumer — Django Channels WebSocket consumer.

Responsibilities (post-SFU migration):
  - Presence: join/leave notifications, participant list
  - Chat messages
  - Meeting state: sleep/unfreeze, end
  - Attendance recording

WebRTC signaling is handled entirely by the mediasoup SFU (Socket.IO).
This consumer no longer relays offer/answer/ICE.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class MeetingConsumer(AsyncWebsocketConsumer):

    # ── Connect ───────────────────────────────────────────────────────────────

    async def connect(self):
        try:
            self.meeting_code   = self.scope['url_route']['kwargs']['meeting_code'].upper()
            self.room_group     = f'meeting_{self.meeting_code}'
            self.user           = self.scope['user']

            if not self.user.is_authenticated:
                await self.close()
                return

            await self.channel_layer.group_add(self.room_group, self.channel_name)

            user_data           = await self._record_join()
            active_participants = await self._get_active_participants()

            await self.accept()

            # Send current participant list to the joiner
            await self.send(text_data=json.dumps({
                'type':         'participant_list',
                'participants': active_participants,
            }))

            # Notify others
            await self.channel_layer.group_send(self.room_group, {
                'type':      'user_joined',
                'user_id':   user_data['id'],
                'username':  user_data['username'],
                'is_host':   user_data['is_host'],
                'is_admin':  user_data['is_admin'],
            })

        except Exception as exc:
            logger.error('WS connect error: %s', exc)
            await self.close()

    # ── Disconnect ────────────────────────────────────────────────────────────

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_send(self.room_group, {
                'type':     'user_left',
                'user_id':  self.user.id,
                'username': self.user.username,
            })
            await self.channel_layer.group_discard(self.room_group, self.channel_name)
            await self._record_leave()
        except Exception as exc:
            logger.error('WS disconnect error: %s', exc)

    # ── Receive ───────────────────────────────────────────────────────────────

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get('type')

        if msg_type == 'chat':
            message = data.get('message', '').strip()
            if message:
                await self._save_chat(message)
                await self.channel_layer.group_send(self.room_group, {
                    'type':      'chat_message',
                    'message':   message,
                    'username':  self.user.username,
                    'user_id':   self.user.id,
                    'timestamp': data.get('timestamp', timezone.now().isoformat()),
                })

        elif msg_type == 'screen_share_started':
            await self.channel_layer.group_send(self.room_group, {
                'type':     'screen_share_started',
                'user_id':  self.user.id,
                'username': self.user.username,
            })

        elif msg_type == 'screen_share_stopped':
            await self.channel_layer.group_send(self.room_group, {
                'type':     'screen_share_stopped',
                'user_id':  self.user.id,
                'username': self.user.username,
            })

        elif msg_type == 'request_participants':
            participants = await self._get_active_participants()
            await self.send(text_data=json.dumps({
                'type':         'participant_list',
                'participants': participants,
            }))

    # ── Group message handlers ────────────────────────────────────────────────

    async def user_joined(self, event):
        await self.send(text_data=json.dumps({
            'type':     'user_joined',
            'user_id':  event['user_id'],
            'username': event['username'],
            'is_host':  event.get('is_host', False),
            'is_admin': event.get('is_admin', False),
        }))

    async def user_left(self, event):
        await self.send(text_data=json.dumps({
            'type':     'user_left',
            'user_id':  event['user_id'],
            'username': event['username'],
        }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type':      'chat',
            'message':   event['message'],
            'username':  event['username'],
            'user_id':   event['user_id'],
            'timestamp': event.get('timestamp'),
        }))

    async def screen_share_started(self, event):
        await self.send(text_data=json.dumps({
            'type':     'screen_share_started',
            'user_id':  event['user_id'],
            'username': event['username'],
        }))

    async def screen_share_stopped(self, event):
        await self.send(text_data=json.dumps({
            'type':     'screen_share_stopped',
            'user_id':  event['user_id'],
            'username': event['username'],
        }))

    async def meeting_sleeping(self, event):
        await self.send(text_data=json.dumps({
            'type':    'meeting_sleeping',
            'message': event.get('message', 'Meeting has been put to sleep'),
        }))

    async def meeting_unfrozen(self, event):
        await self.send(text_data=json.dumps({
            'type':    'meeting_unfrozen',
            'message': event.get('message', 'Meeting is now active'),
        }))

    # ── DB helpers ────────────────────────────────────────────────────────────

    @database_sync_to_async
    def _record_join(self):
        from .models import Meeting, MeetingParticipant, MeetingAttendanceLog
        meeting = Meeting.objects.get(meeting_code=self.meeting_code)
        participant, _ = MeetingParticipant.objects.get_or_create(
            meeting=meeting, user=self.user
        )
        participant.joined_at = timezone.now()
        participant.is_active = True
        participant.save()
        MeetingAttendanceLog.objects.create(participant=participant, event_type='join')
        return {
            'id':       self.user.id,
            'username': self.user.username,
            'is_host':  meeting.teacher == self.user or self.user.is_superuser,
            'is_admin': self.user.is_superuser,
        }

    @database_sync_to_async
    def _get_active_participants(self):
        from .models import Meeting, MeetingParticipant
        try:
            meeting = Meeting.objects.get(meeting_code=self.meeting_code)
            active  = (
                MeetingParticipant.objects
                .filter(meeting=meeting, is_active=True)
                .exclude(user=self.user)
                .select_related('user')
            )
            return [
                {
                    'user_id':  p.user.id,
                    'username': p.user.username,
                    'is_host':  meeting.teacher == p.user or p.user.is_superuser,
                    'is_admin': p.user.is_superuser,
                }
                for p in active
            ]
        except Exception as exc:
            logger.error('get_active_participants error: %s', exc)
            return []

    @database_sync_to_async
    def _record_leave(self):
        from .models import Meeting, MeetingParticipant, MeetingAttendanceLog
        try:
            meeting     = Meeting.objects.get(meeting_code=self.meeting_code)
            participant = MeetingParticipant.objects.get(meeting=meeting, user=self.user)
            now         = timezone.now()
            last_join   = participant.attendance_logs.filter(event_type='join').last()
            if last_join:
                duration = (now - last_join.timestamp).total_seconds()
                participant.total_duration_seconds += int(duration)
            participant.left_at   = now
            participant.is_active = False
            participant.save()
            MeetingAttendanceLog.objects.create(participant=participant, event_type='leave')
        except Exception as exc:
            logger.error('record_leave error: %s', exc)

    @database_sync_to_async
    def _save_chat(self, message):
        from .models import Meeting, MeetingChat
        try:
            meeting = Meeting.objects.get(meeting_code=self.meeting_code)
            MeetingChat.objects.create(meeting=meeting, user=self.user, message=message)
        except Exception as exc:
            logger.error('save_chat error: %s', exc)
