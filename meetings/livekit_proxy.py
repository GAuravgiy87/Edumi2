"""
WebSocket proxy: browser <-> Django (local/LAN) <-> LiveKit (127.0.0.1:7880)

Browser connects to:  ws://<host>/livekit-proxy/rtc?access_token=...
Proxy forwards to:    ws://127.0.0.1:7880/rtc?access_token=...

LIVEKIT_INTERNAL_URL env var overrides the target (default: ws://127.0.0.1:7880).
"""
import asyncio
import os
import logging
import traceback
from channels.generic.websocket import AsyncWebsocketConsumer
import websockets
import websockets.exceptions

logger = logging.getLogger(__name__)

LIVEKIT_INTERNAL = os.environ.get(
    'LIVEKIT_INTERNAL_URL',
    os.environ.get('LIVEKIT_URL', 'ws://127.0.0.1:7880')
)


class LiveKitProxyConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        lk_path = self.scope["url_route"]["kwargs"].get("lk_path") or "/rtc"
        qs = self.scope.get("query_string", b"").decode()

        target = f"{LIVEKIT_INTERNAL}{lk_path}"
        if qs:
            target += f"?{qs}"

        logger.info(f"[LKProxy] connect -> {target[:120]}")

        try:
            self._lk_ws = await websockets.connect(
                target,
                ping_interval=None,   # LiveKit manages its own keep-alive
                ping_timeout=None,
                max_size=10 * 1024 * 1024,
                open_timeout=10,
            )
            logger.info(f"[LKProxy] Successfully connected to LiveKit at {LIVEKIT_INTERNAL}")
        except websockets.exceptions.InvalidStatus as e:
            logger.error(f"[LKProxy] LiveKit rejected connection: HTTP {e.response.status_code} - {e.response.reason_phrase}")
            logger.error(f"[LKProxy] Request headers: {dict(e.response.headers)}")
            await self.close(code=1011)
            return
        except OSError as e:
            logger.error(f"[LKProxy] Cannot reach LiveKit at {LIVEKIT_INTERNAL}: {e}")
            logger.error(f"[LKProxy] Check if LiveKit server is running and accessible")
            await self.close(code=1011)
            return
        except Exception as e:
            logger.error(f"[LKProxy] Unexpected connection error: {type(e).__name__}: {e}")
            logger.error(f"[LKProxy] Full traceback: {traceback.format_exc()}")
            await self.close(code=1011)
            return

        await self.accept()
        logger.info(f"[LKProxy] accepted browser, forwarding to LiveKit")
        self._lk_task = asyncio.ensure_future(self._lk_to_browser())

    async def disconnect(self, code):
        logger.info(f"[LKProxy] browser disconnected, code={code}")
        if hasattr(self, "_lk_task"):
            self._lk_task.cancel()
        if hasattr(self, "_lk_ws"):
            try:
                await self._lk_ws.close()
            except Exception:
                pass

    async def receive(self, text_data=None, bytes_data=None):
        """Browser → LiveKit"""
        if not hasattr(self, "_lk_ws"):
            return
        try:
            if bytes_data is not None:
                await self._lk_ws.send(bytes_data)
            elif text_data is not None:
                await self._lk_ws.send(text_data)
        except Exception as e:
            logger.warning(f"[LKProxy] browser→LiveKit send error: {e}\n{traceback.format_exc()}")
            await self.close()

    async def _lk_to_browser(self):
        """LiveKit → Browser"""
        try:
            async for msg in self._lk_ws:
                if isinstance(msg, bytes):
                    await self.send(bytes_data=msg)
                else:
                    await self.send(text_data=msg)
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"[LKProxy] LiveKit closed connection: {e}")
        except Exception as e:
            logger.warning(f"[LKProxy] LiveKit→browser error: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        finally:
            await self.close()
