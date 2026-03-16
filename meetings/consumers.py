import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Meeting, MeetingParticipant, MeetingAttendanceLog, MeetingChat

class MeetingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.meeting_code = self.scope['url_route']['kwargs']['meeting_code']
        self.room_group_name = f'meeting_{self.meeting_code}'
        self.user = self.scope['user']
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Record join in database
        await self.record_join()

        await self.accept()
        
        # Notify others that user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_id': self.user.id,
                'username': self.user.username
            }
        )
    
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
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'offer':
            # Forward WebRTC offer to specific peer
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
            # Forward WebRTC answer to specific peer
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
            # Forward ICE candidate to specific peer
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
            # Save to database
            await self.save_chat_message(data['message'])
            
            # Broadcast chat message
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': data['message'],
                    'username': self.user.username,
                    'user_id': self.user.id,
                    'timestamp': data.get('timestamp')
                }
            )
        
        elif message_type == 'screen_share_started':
            # Broadcast screen share started
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'screen_share_started',
                    'user_id': self.user.id,
                    'username': self.user.username
                }
            )
        
        elif message_type == 'screen_share_stopped':
            # Broadcast screen share stopped
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'screen_share_stopped',
                    'user_id': self.user.id,
                    'username': self.user.username
                }
            )
    
    async def user_joined(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user_id': event['user_id'],
            'username': event['username']
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
