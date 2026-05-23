import json
import os
import subprocess
import asyncio
import threading
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from .models import Camera
from channels.db import database_sync_to_async

# Dictionary to store the first chunk (header) for each active camera audio stream
audio_headers = {}
# Active RTSP audio relay processes {camera_id: subprocess}
rtsp_relays = {}
# Number of listeners per camera {camera_id: count}
camera_listeners = {}

class AudioConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.camera_id = self.scope['url_route']['kwargs']['camera_id']
        self.room_group_name = f'camera_audio_{self.camera_id}'
        self.user = self.scope['user']
        
        # Get source from query string
        query_params = self.scope.get('query_string', b'').decode()
        self.source = 'pc'
        if 'source=mobile' in query_params:
            self.source = 'mobile'
        elif 'source=pc_monitor' in query_params:
            self.source = 'pc_monitor'
        
        self.is_teacher = await self.check_is_teacher()
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()

        # Track listeners for IP Camera audio
        if self.camera_id not in camera_listeners:
            camera_listeners[self.camera_id] = 0
        camera_listeners[self.camera_id] += 1

        # Start IP Camera Audio Relay if it's the first listener
        # Teachers can also start the relay if they are in 'pc_monitor' mode
        should_start_relay = (camera_listeners[self.camera_id] == 1 and 
                             (not self.is_teacher or self.source == 'pc_monitor'))
        
        if should_start_relay:
            asyncio.create_task(self.start_rtsp_audio_relay())
        
        # If a header exists for this camera, send it to the new joiner immediately
        if self.source == 'pc_monitor' or not self.is_teacher:
            if self.camera_id in audio_headers:
                await self.send(bytes_data=audio_headers[self.camera_id])
        
        if self.is_teacher and self.source != 'pc_monitor':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'mic_status',
                    'source': self.source,
                    'status': 'connected',
                    'user_id': self.user.id
                }
            )
            
            suffix = '_mobile' if self.source == 'mobile' else ''
            self.audio_file_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'audio_{self.camera_id}_{self.user.id}{suffix}.webm')
            os.makedirs(os.path.dirname(self.audio_file_path), exist_ok=True)
            self.audio_file = open(self.audio_file_path, 'wb')
        else:
            self.audio_file = None

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        if self.audio_file:
            self.audio_file.close()
            # Clear header if teacher disconnects
            if self.camera_id in audio_headers:
                del audio_headers[self.camera_id]
        
        # Update listener count and stop relay if last one
        if self.camera_id in camera_listeners:
            camera_listeners[self.camera_id] -= 1
            if camera_listeners[self.camera_id] <= 0:
                self.stop_rtsp_audio_relay()

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            # Teachers can only send audio if they are NOT in monitor mode
            if self.is_teacher and self.source != 'pc_monitor':
                # Store the first chunk as the header for new students
                if self.camera_id not in audio_headers:
                    audio_headers[self.camera_id] = bytes_data
                
                if self.audio_file:
                    self.audio_file.write(bytes_data)
                
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'audio_chunk',
                        'data': bytes_data,
                        'sender_channel_name': self.channel_name
                    }
                )

    async def audio_chunk(self, event):
        # Don't send back to the sender
        if self.channel_name != event.get('sender_channel_name'):
            await self.send(bytes_data=event['data'])

    async def mic_status(self, event):
        """Handle mic status updates (connected/disconnected)"""
        await self.send(text_data=json.dumps({
            'type': 'mic_status',
            'source': event['source'],
            'status': event['status'],
            'user_id': event['user_id']
        }))

    async def check_is_teacher(self):
        try:
            @database_sync_to_async
            def get_camera_teacher():
                try:
                    camera = Camera.objects.get(id=self.camera_id)
                    return camera.live_teacher == self.user or self.user.is_superuser
                except:
                    return False
            return await get_camera_teacher()
        except:
            return False

    async def start_rtsp_audio_relay(self):
        """Extracts audio from RTSP and broadcasts to group"""
        if self.camera_id in rtsp_relays:
            return

        try:
            camera = await database_sync_to_async(Camera.objects.get)(id=self.camera_id)
            rtsp_url = camera.get_full_rtsp_url()
            
            # Optimized FFmpeg command for ultra-low latency and perfect sync
            # Added -nostdin and -probesize to prevent hangs/errors
            cmd = [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-nostdin',
                '-probesize', '32k',
                '-rtsp_transport', 'tcp', '-i', rtsp_url,
                '-vn', # No video
                '-acodec', 'libopus', '-b:a', '64k', '-vbr', 'on',
                '-af', 'aresample=async=1:min_hard_comp=0.100000:first_pts=0',
                '-f', 'webm',
                'pipe:1'
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE # Capture stderr for better error reporting
            )
            rtsp_relays[self.camera_id] = process
            
            # Read from pipe and broadcast
            while self.camera_id in rtsp_relays:
                try:
                    chunk = await asyncio.wait_for(process.stdout.read(4096), timeout=5.0)
                    if not chunk:
                        # Check stderr if stdout is empty
                        err = await process.stderr.read()
                        if err: print(f"FFmpeg Relay Error: {err.decode()}")
                        break
                    
                    if self.camera_id not in audio_headers:
                        audio_headers[self.camera_id] = chunk

                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'audio_chunk',
                            'data': chunk,
                            'sender_channel_name': 'rtsp_relay'
                        }
                    )
                except asyncio.TimeoutError:
                    print(f"RTSP Audio Relay Timeout for camera {self.camera_id}")
                    break
        except Exception as e:
            print(f"RTSP Audio Relay Critical Error: {str(e)}")
        finally:
            self.stop_rtsp_audio_relay()

    def stop_rtsp_audio_relay(self):
        if self.camera_id in rtsp_relays:
            process = rtsp_relays.pop(self.camera_id)
            try:
                # Use standard termination
                process.terminate()
                # We can't await in a sync def, but the process will be reaped by OS
            except:
                pass
            # Don't clear headers here as other listeners might still need them 
            # unless this was the absolute last one
            if self.camera_id not in camera_listeners or camera_listeners[self.camera_id] <= 0:
                if self.camera_id in audio_headers:
                    del audio_headers[self.camera_id]
