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

        # Detailed debug logging to a file
        debug_log = os.path.join(os.getcwd(), "livekit_proxy_debug.log")
        def log_debug(msg):
            with open(debug_log, "a") as f:
                f.write(f"{msg}\n")
            proxy_logger.info(msg)

        log_debug(f"--- New Connection attempt for {lk_path} ---")

        targets = [
            f"{LIVEKIT_INTERNAL}{lk_path}",
            f"ws://localhost:7880{lk_path}",
            f"ws://127.0.0.1:7880{lk_path}"
        ]
        if qs:
            targets = [f"{t}?{qs}" for t in targets]

        connected = False
        for target in targets:
            try:
                log_debug(f"Attempting: {target}")
                connect_kwargs = {
                    "ping_interval": 10,
                    "ping_timeout": 10,
                    "max_size": 10 * 1024 * 1024,
                    "open_timeout": 15,
                }
                if subprotocols:
                    connect_kwargs["subprotocols"] = subprotocols

                self._lk_ws = await websockets.connect(target, **connect_kwargs)
                connected = True
                log_debug(f"SUCCESS: Connected to {target}")
                break
            except Exception as e:
                log_debug(f"FAILED {target}: {type(e).__name__}: {str(e)}")

        if not connected:
            log_debug(f"CRITICAL: All targets failed for {lk_path}")
            await self.close(code=1011)
            return

        # Warm-up delay to stabilize the tunnel
        await asyncio.sleep(0.5)
        
        # Negotiate subprotocol strictly
        selected_proto = getattr(self._lk_ws, 'subprotocol', None)
        if not selected_proto and "v1.livekit.io" in subprotocols:
            selected_proto = "v1.livekit.io"
            
        await self.accept(subprotocol=selected_proto)
        
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
                    with open("livekit_proxy_debug.log", "a") as f:
                        f.write(f"SEND ERROR: {str(e)}\n")
                    break 
        except Exception as e:
            with open("livekit_proxy_debug.log", "a") as f:
                f.write(f"STREAM ERROR: {str(e)}\n")
        finally:
            with open("livekit_proxy_debug.log", "a") as f:
                f.write("--- Session finished ---\n")
            await self.close()
