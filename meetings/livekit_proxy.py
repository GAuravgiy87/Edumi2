"""
WebSocket proxy: browser <-> Django/ngrok <-> LiveKit (localhost:7880)

Browser connects to:  wss://<any-host>/livekit-proxy/rtc?access_token=...
Proxy forwards to:    ws://localhost:7880/rtc?access_token=...

LIVEKIT_INTERNAL_URL env var overrides the target (default: ws://localhost:7880).
"""
import asyncio
import os
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

# Use structured logging for production readiness
logging.basicConfig(level=logging.INFO)
proxy_logger = logging.getLogger("livekit_proxy")

LIVEKIT_INTERNAL = os.environ.get('LIVEKIT_INTERNAL_URL', 'ws://127.0.0.1:7880')

class LiveKitProxyConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        lk_path = self.scope["url_route"]["kwargs"].get("lk_path") or "/rtc"
        qs = self.scope.get("query_string", b"").decode()

        target = f"{LIVEKIT_INTERNAL}{lk_path}"
        if qs:
            target += f"?{qs}"

        proxy_logger.info(f"[LiveKitProxy] Attempting connection to internal LiveKit: {target}")

        try:
            self._lk_ws = await websockets.connect(
                target,
                ping_interval=20,
                ping_timeout=20,
                max_size=10 * 1024 * 1024,
                open_timeout=10,
            )
            proxy_logger.info(f"[LiveKitProxy] Successfully connected to LiveKit server")
        except Exception as e:
            proxy_logger.error(f"[LiveKitProxy] CRITICAL: Failed to connect to {target}. Reason: {str(e)}")
            # 1011: Internal Error. 
            # We close with 1011 so the frontend knows it's a server-side configuration issue.
            await self.close(code=1011)
            return

        await self.accept()
        proxy_logger.info(f"[LiveKitProxy] Browser <-> Proxy connection accepted")
        self._lk_task = asyncio.ensure_future(self._lk_to_browser())

    async def disconnect(self, code):
        proxy_logger.info(f"[LiveKitProxy] Disconnecting with code: {code}")
        if hasattr(self, "_lk_task"):
            self._lk_task.cancel()
        if hasattr(self, "_lk_ws"):
            try:
                await self._lk_ws.close()
            except Exception as e:
                proxy_logger.debug(f"[LiveKitProxy] Error closing LiveKit WS: {e}")

    async def receive(self, text_data=None, bytes_data=None):
        """Browser → LiveKit"""
        if not hasattr(self, "_lk_ws"):
            return
        try:
            if bytes_data is not None:
                await self._lk_ws.send(bytes_data)
            elif text_data is not None:
                await self._lk_ws.send(text_data)
        except ConnectionClosed:
            proxy_logger.warning("[LiveKitProxy] LiveKit connection closed while sending")
            await self.close()
        except Exception as e:
            proxy_logger.error(f"[LiveKitProxy] Browser → LiveKit send error: {str(e)}")
            await self.close()

    async def _lk_to_browser(self):
        """LiveKit → Browser"""
        try:
            async for msg in self._lk_ws:
                if isinstance(msg, bytes):
                    await self.send(bytes_data=msg)
                else:
                    await self.send(text_data=msg)
        except ConnectionClosed:
            proxy_logger.info("[LiveKitProxy] LiveKit server closed the connection")
        except Exception as e:
            proxy_logger.error(f"[LiveKitProxy] LiveKit → Browser stream error: {str(e)}")
        finally:
            proxy_logger.info("[LiveKitProxy] Closing proxy session")
            await self.close()
