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
        subprotocols = self.scope.get("subprotocols", [])

        target = f"{LIVEKIT_INTERNAL}{lk_path}"
        if qs:
            target += f"?{qs}"

        proxy_logger.info(f"[LiveKitProxy] Connecting to LiveKit: {target} (Protocols: {subprotocols})")

        try:
            # Connect to LiveKit, only passing subprotocols if the browser provided them
            connect_kwargs = {
                "ping_interval": 20,
                "ping_timeout": 20,
                "max_size": 10 * 1024 * 1024,
                "open_timeout": 10,
            }
            if subprotocols:
                connect_kwargs["subprotocols"] = subprotocols

            self._lk_ws = await websockets.connect(target, **connect_kwargs)
            
            # Negotiated subprotocol
            selected_proto = getattr(self._lk_ws, 'subprotocol', None)
            proxy_logger.info(f"[LiveKitProxy] Connected (Selected Protocol: {selected_proto})")
            
            # Accept the browser connection
            await self.accept(subprotocol=selected_proto)
            
        except Exception as e:
            proxy_logger.error(f"[LiveKitProxy] Connection FAILED to {target}: {type(e).__name__}: {str(e)}")
            await self.close(code=1011)
            return

        self._lk_task = asyncio.ensure_future(self._lk_to_browser())

    async def disconnect(self, code):
        proxy_logger.info(f"[LiveKitProxy] Browser disconnected (code: {code})")
        if hasattr(self, "_lk_task"):
            self._lk_task.cancel()
        if hasattr(self, "_lk_ws"):
            await self._lk_ws.close()

    async def receive(self, text_data=None, bytes_data=None):
        if not hasattr(self, "_lk_ws"): return
        try:
            if bytes_data is not None:
                await self._lk_ws.send(bytes_data)
            else:
                await self._lk_ws.send(text_data)
        except Exception as e:
            proxy_logger.warning(f"[LiveKitProxy] Browser -> LiveKit failed: {str(e)}")
            await self.close()

    async def _lk_to_browser(self):
        try:
            async for msg in self._lk_ws:
                try:
                    if isinstance(msg, bytes):
                        await self.send(bytes_data=msg)
                    else:
                        await self.send(text_data=msg)
                except Exception as e:
                    # This often happens if the browser closes the connection mid-stream
                    proxy_logger.debug(f"[LiveKitProxy] Send to browser failed: {str(e)}")
                    break 
        except Exception as e:
            proxy_logger.error(f"[LiveKitProxy] LiveKit -> Browser stream error: {str(e)}")
        finally:
            proxy_logger.info("[LiveKitProxy] Session finished")
            await self.close()
