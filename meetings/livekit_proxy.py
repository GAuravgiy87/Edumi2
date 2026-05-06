"""
WebSocket proxy: browser <-> Django/Channels <-> LiveKit (localhost:7880)

Browser connects to:  wss://<ngrok>/livekit-proxy/rtc?access_token=...
Proxy forwards to:    ws://localhost:7880/rtc?access_token=...

Key requirements for LiveKit SDK v2:
- Forward Sec-WebSocket-Protocol header (LiveKit SDK sends 'livekit')
- Forward query string (contains access_token)
- Handle binary protobuf messages (not text)
- Keep connection alive with ping/pong
"""
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
import websockets

logger = logging.getLogger('meetings.livekit_proxy')

LIVEKIT_INTERNAL = "ws://localhost:7880"


class LiveKitProxyConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        # ── Build target URL ──────────────────────────────────────────────────
        lk_path = self.scope["url_route"]["kwargs"].get("lk_path") or "/rtc"
        qs      = self.scope.get("query_string", b"").decode()

        # lk_path may include query string if regex captured it — strip it
        if "?" in lk_path:
            lk_path = lk_path.split("?")[0]

        target = f"{LIVEKIT_INTERNAL}{lk_path}"
        if qs:
            target += f"?{qs}"

        # ── Forward subprotocols from browser ─────────────────────────────────
        # LiveKit JS SDK v2 sends Sec-WebSocket-Protocol: livekit
        # We must forward it so LiveKit accepts the connection
        subprotocols = []
        for name, value in self.scope.get("headers", []):
            if name.lower() == b"sec-websocket-protocol":
                subprotocols = [p.strip() for p in value.decode().split(",")]
                break

        logger.info(f"LiveKit proxy → {target}  subprotocols={subprotocols}")

        # ── Connect to LiveKit ────────────────────────────────────────────────
        try:
            connect_kwargs = dict(
                ping_interval = 20,
                ping_timeout  = 20,
                max_size      = 16 * 1024 * 1024,   # 16 MB for large video frames
                open_timeout  = 10,
            )
            if subprotocols:
                connect_kwargs["subprotocols"] = subprotocols

            self._lk_ws = await websockets.connect(target, **connect_kwargs)

        except Exception as e:
            logger.error(f"LiveKit proxy connect failed: {e}")
            await self.close(code=1011)
            return

        # ── Accept browser connection ─────────────────────────────────────────
        # If LiveKit negotiated a subprotocol, echo it back to the browser
        negotiated = getattr(self._lk_ws, "subprotocol", None)
        if negotiated:
            await self.accept(subprotocol=negotiated)
        else:
            await self.accept()

        # ── Start LiveKit → browser forwarding task ───────────────────────────
        self._lk_task = asyncio.ensure_future(self._lk_to_browser())

    async def disconnect(self, code):
        # Cancel the forwarding task
        task = getattr(self, "_lk_task", None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Close LiveKit connection
        lk_ws = getattr(self, "_lk_ws", None)
        if lk_ws:
            try:
                await lk_ws.close()
            except Exception:
                pass

    async def receive(self, text_data=None, bytes_data=None):
        """Browser → LiveKit"""
        lk_ws = getattr(self, "_lk_ws", None)
        if not lk_ws:
            return
        try:
            if bytes_data is not None:
                await lk_ws.send(bytes_data)
            elif text_data is not None:
                await lk_ws.send(text_data)
        except Exception as e:
            logger.warning(f"Proxy → LiveKit send error: {e}")
            await self.close()

    async def _lk_to_browser(self):
        """LiveKit → Browser  (runs as a background task)"""
        lk_ws = getattr(self, "_lk_ws", None)
        if not lk_ws:
            return
        try:
            async for msg in lk_ws:
                if isinstance(msg, bytes):
                    await self.send(bytes_data=msg)
                else:
                    await self.send(text_data=msg)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"LiveKit → proxy ended: {e}")
        finally:
            # LiveKit closed — close browser connection too
            try:
                await self.close()
            except Exception:
                pass
