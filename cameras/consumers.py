import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import LiveClass

class LiveClassConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.stream_key = self.scope['url_route']['kwargs']['stream_key']
        self.room_group_name = f'live_class_{self.stream_key}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        
        # Increment viewer count
        await self.update_viewer_count(1)

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Decrement viewer count
        await self.update_viewer_count(-1)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get('message')
        username = self.scope['user'].username if self.scope['user'].is_authenticated else "Anonymous"

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username
            }
        )

    async def chat_message(self, event):
        message = event['message']
        username = event['username']

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat',
            'message': message,
            'username': username
        }))

    async def viewer_update(self, event):
        count = event['count']
        await self.send(text_data=json.dumps({
            'type': 'viewer_count',
            'count': count
        }))

    @database_sync_to_async
    def update_viewer_count(self, delta):
        from django.core.cache import cache
        cache_key = f"live_viewers_{self.stream_key}"
        
        try:
            # 1. Update Redis counter (Fast)
            new_count = cache.get(cache_key, 0) + delta
            if new_count < 0: new_count = 0
            cache.set(cache_key, new_count, 3600) # Expire in 1 hour
            
            # 2. Periodically sync to DB (Slow)
            # To keep it simple but performant, we only write to DB every 5 viewers or on disconnect
            if new_count % 5 == 0 or delta < 0:
                live_class = LiveClass.objects.get(stream_key=self.stream_key, status='active')
                live_class.viewer_count = new_count
                live_class.save()
            
            # 3. Broadcast update to group
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                self.room_group_name,
                {
                    'type': 'viewer_update',
                    'count': new_count
                }
            )
        except Exception as e:
            print(f"Error updating viewer count: {e}")
