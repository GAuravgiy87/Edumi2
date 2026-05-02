import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Meeting, MeetingParticipant, MeetingAttendanceLog, MeetingChat

class MeetingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            self.meeting_code = self.scope['url_route']['kwargs']['meeting_code'].upper()
            self.room_group_name = f'meeting_{self.meeting_code}'
            self.user = self.scope['user']
            
            if not self.user.is_authenticated:
                await self.close()
                return

            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Record join and get user meta in one go
            user_data = await self.get_user_meta()
            
            # Get other active participants BEFORE accepting to ensure we have them
            active_participants = await self.get_active_participants()
            
            await self.accept()

            # Send current participant list to the joiner
            await self.send(text_data=json.dumps({
                'type': 'participant_list',
                'participants': active_participants
            }))

            # Notify others that user joined
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_joined',
                    'user_id': user_data['id'],
                    'username': user_data['username'],
                    'is_host': user_data['is_host'],
                    'is_admin': user_data['is_admin'],
                }
            )
        except Exception as e:
            # Avoid using self.user directly in strings to prevent DB access errors
            print(f"WS Connect Error: {str(e)}")
            await self.close()

    @database_sync_to_async
    def get_user_meta(self):
        meeting = Meeting.objects.get(meeting_code=self.meeting_code)
        # Record join while we are here
        participant, _ = MeetingParticipant.objects.get_or_create(
            meeting=meeting,
            user=self.user
        )
        participant.joined_at = timezone.now()
        participant.is_active = True
        participant.save()
        
        # Prevent log spam on reloads: only log join if last event was 'leave' or first time
        last_log = MeetingAttendanceLog.objects.filter(participant=participant).order_by('-timestamp').first()
        if not last_log or last_log.event_type == 'leave':
            MeetingAttendanceLog.objects.create(
                participant=participant,
                event_type='join'
            )
        
        return {
            'id': self.user.id,
            'username': self.user.username,
            'is_host': meeting.teacher == self.user or self.user.is_superuser,
            'is_admin': self.user.is_superuser
        }

    @database_sync_to_async
    def get_active_participants(self):
        try:
            meeting = Meeting.objects.get(meeting_code=self.meeting_code)
            # Find all users who are marked active in this meeting, excluding self
            active = MeetingParticipant.objects.filter(
                meeting=meeting, 
                is_active=True
            ).exclude(user=self.user).select_related('user')
            
            return [
                {
                    'user_id': p.user.id,
                    'username': p.user.username,
                    'is_host': meeting.teacher == p.user or p.user.is_superuser,
                    'is_admin': p.user.is_superuser
                } for p in active
            ]
        except Exception as e:
            print(f"Error fetching active participants: {e}")
            return []
    
    async def disconnect(self, close_code):
        # Notify others that user left
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_left',
                'user_id': self.user.id,
                'username': self.user.username
            }
        )
        
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Record leave in database
        await self.record_leave()
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            # Debug logging
            try:
                with open('ws_debug.log', 'a') as f:
                    f.write(f"RECV: {self.user.id} ({self.user.username}) - {message_type} to {data.get('to_user_id')}\n")
            except: pass

            if message_type == 'offer':
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'webrtc_offer',
                        'offer': data['offer'],
                        'from_user_id': self.user.id,
                        'from_username': self.user.username,
                        'to_user_id': data.get('to_user_id')
                    }
                )
            
            elif message_type == 'answer':
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'webrtc_answer',
                        'answer': data['answer'],
                        'from_user_id': self.user.id,
                        'from_username': self.user.username,
                        'to_user_id': data.get('to_user_id')
                    }
                )
            
            elif message_type == 'ice_candidate':
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'ice_candidate',
                        'candidate': data['candidate'],
                        'from_user_id': self.user.id,
                        'to_user_id': data.get('to_user_id')
                    }
                )
            
            elif message_type == 'chat':
                if 'message' in data:
                    await self.save_chat_message(data['message'])
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'chat_message',
                            'message': data['message'],
                            'username': self.user.username,
                            'user_id': self.user.id,
                            'timestamp': data.get('timestamp', timezone.now().isoformat())
                        }
                    )
            
            elif message_type == 'screen_share_started':
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'screen_share_started',
                        'user_id': self.user.id,
                        'username': self.user.username
                    }
                )
            
            elif message_type == 'screen_share_stopped':
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'screen_share_stopped',
                        'user_id': self.user.id,
                        'username': self.user.username
                    }
                )
            
            elif message_type == 'request_participants':
                active_participants = await self.get_active_participants()
                await self.send(text_data=json.dumps({
                    'type': 'participant_list',
                    'participants': active_participants
                }))
        except Exception as e:
            print(f"Receive error: {e}")
    
    async def user_joined(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user_id': event['user_id'],
            'username': event['username'],
            'is_host': event.get('is_host', False),
            'is_admin': event.get('is_admin', False),
        }))
    
    async def user_left(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user_id': event['user_id'],
            'username': event['username']
        }))
    
    async def webrtc_offer(self, event):
        # Only send to intended recipient
        if event.get('to_user_id') == self.user.id or event.get('to_user_id') is None:
            await self.send(text_data=json.dumps({
                'type': 'offer',
                'offer': event['offer'],
                'from_user_id': event['from_user_id'],
                'from_username': event['from_username']
            }))
    
    async def webrtc_answer(self, event):
        # Only send to intended recipient
        if event.get('to_user_id') == self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'answer',
                'answer': event['answer'],
                'from_user_id': event['from_user_id'],
                'from_username': event['from_username']
            }))
    
    async def ice_candidate(self, event):
        # Only send to intended recipient
        if event.get('to_user_id') == self.user.id or event.get('to_user_id') is None:
            await self.send(text_data=json.dumps({
                'type': 'ice_candidate',
                'candidate': event['candidate'],
                'from_user_id': event['from_user_id']
            }))
    
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat',
            'message': event['message'],
            'username': event['username'],
            'user_id': event['user_id'],
            'timestamp': event.get('timestamp')
        }))
    
    async def screen_share_started(self, event):
        await self.send(text_data=json.dumps({
            'type': 'screen_share_started',
            'user_id': event['user_id'],
            'username': event['username']
        }))
    
    async def screen_share_stopped(self, event):
        await self.send(text_data=json.dumps({
            'type': 'screen_share_stopped',
            'user_id': event['user_id'],
            'username': event['username']
        }))

    async def meeting_sleeping(self, event):
        """Handle meeting sleep notification"""
        await self.send(text_data=json.dumps({
            'type': 'meeting_sleeping',
            'message': event.get('message', 'Meeting has been put to sleep')
        }))
    
    async def meeting_unfrozen(self, event):
        """Handle meeting unfrozen notification"""
        await self.send(text_data=json.dumps({
            'type': 'meeting_unfrozen',
            'message': event.get('message', 'Meeting is now active')
        }))
    
    async def kick_user(self, event):
        """Handle user kick notification"""
        await self.send(text_data=json.dumps({
            'type': 'kick_user',
            'user_id': event['user_id'],
            'message': event['message']
        }))
        if self.user.id == event['user_id']:
            await self.close()

    async def permission_update(self, event):
        """Handle participant permission update"""
        await self.send(text_data=json.dumps({
            'type': 'permission_update',
            'user_id': event['user_id'],
            'permission_type': event['permission_type'],
            'value': event['value'],
            'message': event['message']
        }))

    async def global_control_update(self, event):
        """Handle global control update (mute all, etc.)"""
        await self.send(text_data=json.dumps({
            'type': 'global_control_update',
            'control_type': event['control_type'],
            'value': event['value'],
            'message': event['message']
        }))
    
    @database_sync_to_async
    def get_meeting(self):
        return Meeting.objects.get(meeting_code=self.meeting_code)

    @database_sync_to_async
    def get_last_log(self, participant):
        last = MeetingAttendanceLog.objects.filter(participant=participant).order_by('-timestamp').first()
        return last.event_type if last else None

    @database_sync_to_async
    def create_join_log(self, participant):
        MeetingAttendanceLog.objects.create(participant=participant, event_type='join')

    @database_sync_to_async
    def record_join(self):
        try:
            meeting = Meeting.objects.get(meeting_code=self.meeting_code)
            participant, created = MeetingParticipant.objects.get_or_create(
                meeting=meeting,
                user=self.user
            )
            participant.joined_at = timezone.now()
            participant.is_active = True
            participant.save()
            
            MeetingAttendanceLog.objects.create(
                participant=participant,
                event_type='join'
            )
        except Exception as e:
            print(f"Error recording join: {e}")

    @database_sync_to_async
    def record_leave(self):
        try:
            meeting = Meeting.objects.get(meeting_code=self.meeting_code)
            participant = MeetingParticipant.objects.get(
                meeting=meeting,
                user=self.user
            )
            now = timezone.now()
            
            # Calculate duration since last join
            last_join = participant.attendance_logs.filter(event_type='join').last()
            if last_join:
                duration = (now - last_join.timestamp).total_seconds()
                participant.total_duration_seconds += int(duration)
            
            participant.left_at = now
            participant.is_active = False
            participant.save()
            
            MeetingAttendanceLog.objects.create(
                participant=participant,
                event_type='leave'
            )
        except Exception as e:
            print(f"Error recording leave: {e}")
    @database_sync_to_async
    def save_chat_message(self, message):
        try:
            meeting = Meeting.objects.get(meeting_code=self.meeting_code)
            MeetingChat.objects.create(
                meeting=meeting,
                user=self.user,
                message=message
            )
        except Exception as e:
            print(f"Error saving chat message: {e}")
