# DETAILED PACKET FLOW ANALYSIS

## 1. USER LOGIN FLOW (HTTP)

```
CLIENT                    NGINX                   DJANGO (Port 8000)         DATABASE
  │                         │                           │                        │
  │  GET /accounts/login/   │                           │                        │
  ├────────────────────────>│                           │                        │
  │                         │  Proxy Request            │                        │
  │                         ├──────────────────────────>│                        │
  │                         │                           │  Render Template       │
  │                         │                           │  (login.html)          │
  │                         │  HTTP 200 + HTML          │                        │
  │  HTTP 200 + HTML        │<──────────────────────────┤                        │
  │<────────────────────────┤                           │                        │
  │                         │                           │                        │
  │  POST /accounts/login/  │                           │                        │
  │  username=admin         │                           │                        │
  │  password=****          │                           │                        │
  │  csrftoken=xyz          │                           │                        │
  ├────────────────────────>│                           │                        │
  │                         │  Proxy POST               │                        │
  │                         ├──────────────────────────>│                        │
  │                         │                           │  Validate CSRF         │
  │                         │                           │  Authenticate User     │
  │                         │                           ├───────────────────────>│
  │                         │                           │  SELECT * FROM         │
  │                         │                           │  auth_user WHERE       │
  │                         │                           │  username='admin'      │
  │                         │                           │<───────────────────────┤
  │                         │                           │  User Record           │
  │                         │                           │  Check Password Hash   │
  │                         │                           │  Create Session        │
  │                         │                           ├───────────────────────>│
  │                         │                           │  INSERT INTO           │
  │                         │                           │  django_session        │
  │                         │  HTTP 302 Redirect        │<───────────────────────┤
  │                         │  Set-Cookie: sessionid    │                        │
  │  HTTP 302 + Cookie      │<──────────────────────────┤                        │
  │<────────────────────────┤                           │                        │
  │                         │                           │                        │
```

### Packet Details:
- Protocol: HTTP/1.1 over TCP
- Headers: Cookie, CSRF Token, Content-Type: application/x-www-form-urlencoded
- Session: Stored in django_session table
- Cookie: sessionid (httponly, secure in production)


## 2. RTSP CAMERA STREAMING FLOW

```
BROWSER              NGINX           DJANGO:8000        CAMERA_SERVICE:8001      RTSP CAMERA
  │                    │                  │                      │                    │
  │  GET /cameras/1/   │                  │                      │                    │
  │  feed/             │                  │                      │                    │
  ├───────────────────>│                  │                      │                    │
  │                    │  Proxy           │                      │                    │
  │                    ├─────────────────>│                      │                    │
  │                    │                  │  Check Permission    │                    │
  │                    │                  │  (DB Query)          │                    │
  │                    │                  │                      │                    │
  │                    │                  │  Proxy to Camera Svc │                    │
  │                    │                  ├─────────────────────>│                    │
  │                    │                  │                      │  Get/Create        │
  │                    │                  │                      │  CameraStreamer    │
  │                    │                  │                      │                    │
  │                    │                  │                      │  RTSP DESCRIBE     │
  │                    │                  │                      ├───────────────────>│
  │                    │                  │                      │<───────────────────┤
  │                    │                  │                      │  SDP (Stream Info) │
  │                    │                  │                      │                    │
  │                    │                  │                      │  RTSP SETUP        │
  │                    │                  │                      ├───────────────────>│
  │                    │                  │                      │<───────────────────┤
  │                    │                  │                      │  Transport: RTP    │
  │                    │                  │                      │                    │
  │                    │                  │                      │  RTSP PLAY         │
  │                    │                  │                      ├───────────────────>│
  │                    │                  │                      │<───────────────────┤
  │                    │                  │                      │  RTP Packets       │
  │                    │                  │                      │  (H.264 Video)     │
  │                    │                  │                      │                    │
  │                    │                  │                      │  [Background       │
  │                    │                  │                      │   Thread Reads     │
  │                    │                  │                      │   Frames via       │
  │                    │                  │                      │   OpenCV]          │
  │                    │                  │                      │                    │
  │                    │                  │  HTTP 200            │                    │
  │                    │                  │  Content-Type:       │                    │
  │                    │                  │  multipart/x-mixed-  │                    │
  │                    │                  │  replace             │                    │
  │  HTTP 200          │<─────────────────┤<─────────────────────┤                    │
  │<───────────────────┤                  │                      │                    │
  │                    │                  │                      │                    │
  │  --frame           │                  │                      │                    │
  │  Content-Type:     │                  │                      │                    │
  │  image/jpeg        │                  │                      │                    │
  │  [JPEG DATA]       │<─────────────────┴──────────────────────┤                    │
  │<───────────────────┤                                         │                    │
  │  --frame           │                                         │                    │
  │  [JPEG DATA]       │<────────────────────────────────────────┤                    │
  │<───────────────────┤                                         │                    │
  │  ...               │                                         │                    │
```


### RTSP Camera Packet Details:

**RTSP Protocol (Port 554):**
- DESCRIBE: Get stream capabilities (SDP)
- SETUP: Configure transport (RTP/UDP or RTP/TCP)
- PLAY: Start streaming
- TEARDOWN: Stop streaming

**RTP Packets (Video):**
- Protocol: RTP over UDP (port range 16384-32767)
- Payload: H.264 NAL units
- Frame Rate: 25-30 FPS
- Resolution: Original (e.g., 1920x1080)

**OpenCV Processing:**
- Reads RTP packets via FFmpeg
- Decodes H.264 to raw frames
- Resizes to 640x360 (performance)
- Encodes to JPEG (quality 60)
- Frame rate: ~20 FPS (0.05s delay)

**HTTP Response (MJPEG):**
- Content-Type: multipart/x-mixed-replace; boundary=frame
- Each frame: ~15-30 KB (JPEG compressed)
- Bandwidth: ~300-600 KB/s per camera
- Cache-Control: no-cache
- X-Accel-Buffering: no (disable nginx buffering)


## 3. MOBILE CAMERA STREAMING FLOW

```
BROWSER              NGINX           DJANGO:8000        CAMERA_SERVICE:8001    MOBILE PHONE
  │                    │                  │                      │                  │
  │  GET /mobile-      │                  │                      │                  │
  │  cameras/1/feed/   │                  │                      │                  │
  ├───────────────────>│                  │                      │                  │
  │                    │  Proxy           │                      │                  │
  │                    ├─────────────────>│                      │                  │
  │                    │                  │  Check Permission    │                  │
  │                    │                  │                      │                  │
  │                    │                  │  Proxy to Camera Svc │                  │
  │                    │                  ├─────────────────────>│                  │
  │                    │                  │                      │  Get/Create      │
  │                    │                  │                      │  MobileCam       │
  │                    │                  │                      │  Streamer        │
  │                    │                  │                      │                  │
  │                    │                  │                      │  HTTP GET        │
  │                    │                  │                      │  /video          │
  │                    │                  │                      ├─────────────────>│
  │                    │                  │                      │<─────────────────┤
  │                    │                  │                      │  HTTP 200        │
  │                    │                  │                      │  multipart/      │
  │                    │                  │                      │  x-mixed-replace │
  │                    │                  │                      │                  │
  │                    │                  │                      │  --frame         │
  │                    │                  │                      │  [JPEG]          │
  │                    │                  │                      │<─────────────────┤
  │                    │                  │                      │  --frame         │
  │                    │                  │                      │  [JPEG]          │
  │                    │                  │                      │<─────────────────┤
  │                    │                  │                      │                  │
  │                    │                  │                      │  [Background     │
  │                    │                  │                      │   Thread         │
  │                    │                  │                      │   Processes]     │
  │                    │                  │                      │                  │
  │  HTTP 200          │                  │                      │                  │
  │  multipart/        │<─────────────────┴──────────────────────┤                  │
  │<───────────────────┤                                         │                  │
  │  --frame           │                                         │                  │
  │  [JPEG]            │<────────────────────────────────────────┤                  │
  │<───────────────────┤                                         │                  │
  │  ...               │                                         │                  │
```

### Mobile Camera Packet Details:

**HTTP/MJPEG Stream (Port 8080):**
- Protocol: HTTP/1.1
- URL: http://phone_ip:8080/video
- Content-Type: multipart/x-mixed-replace; boundary=--jpgboundary
- Authentication: Basic Auth (optional)

**MJPEG Format:**
```
--jpgboundary
Content-Type: image/jpeg
Content-Length: 25000

[JPEG Binary Data]
--jpgboundary
Content-Type: image/jpeg
Content-Length: 24500

[JPEG Binary Data]
--jpgboundary
...
```

**Processing:**
- Requests library streams HTTP response
- Finds JPEG markers (0xFFD8 start, 0xFFD9 end)
- Decodes JPEG to numpy array
- Resizes to 640x360
- Re-encodes to JPEG (quality 60)
- Frame rate: ~15-20 FPS

**Bandwidth:**
- Original: ~500-800 KB/s
- Processed: ~300-500 KB/s


## 4. WEBRTC MEETING FLOW (WebSocket + P2P)

```
USER A (Browser)     NGINX          DJANGO:8000         USER B (Browser)
  │                    │                  │                      │
  │  WS Connect        │                  │                      │
  │  /ws/meeting/ABC/  │                  │                      │
  ├───────────────────>│                  │                      │
  │                    │  WS Upgrade      │                      │
  │                    ├─────────────────>│                      │
  │                    │                  │  MeetingConsumer     │
  │                    │                  │  .connect()          │
  │                    │                  │  Join Channel Group  │
  │                    │                  │  "meeting_ABC"       │
  │                    │  WS 101          │                      │
  │  WS 101 Switching  │<─────────────────┤                      │
  │<───────────────────┤                  │                      │
  │                    │                  │                      │
  │                    │                  │                      │  WS Connect
  │                    │                  │                      │  /ws/meeting/ABC/
  │                    │                  │<─────────────────────┤
  │                    │                  │  MeetingConsumer     │
  │                    │                  │  .connect()          │
  │                    │                  │  Join Channel Group  │
  │                    │                  │                      │
  │                    │                  │  Broadcast:          │
  │                    │                  │  user_joined         │
  │  {type:            │<─────────────────┤                      │
  │   user_joined,     │                  ├─────────────────────>│  {type:
  │   user_id: 2}      │                  │                      │   user_joined}
  │<───────────────────┤                  │                      │
  │                    │                  │                      │
  │  Create RTCPeer    │                  │                      │
  │  Connection        │                  │                      │
  │                    │                  │                      │
  │  {type: offer,     │                  │                      │
  │   sdp: "v=0..."}   │                  │                      │
  ├───────────────────>│                  │                      │
  │                    ├─────────────────>│                      │
  │                    │                  │  Forward to User B   │
  │                    │                  ├─────────────────────>│  {type: offer,
  │                    │                  │                      │   sdp: "v=0..."}
  │                    │                  │                      │
  │                    │                  │                      │  Create Answer
  │                    │                  │                      │
  │                    │                  │  {type: answer,      │
  │                    │                  │<─────────────────────┤  sdp: "v=0..."}
  │                    │                  │  Forward to User A   │
  │  {type: answer,    │<─────────────────┤                      │
  │   sdp: "v=0..."}   │                  │                      │
  │<───────────────────┤                  │                      │
  │                    │                  │                      │
  │  {type:            │                  │                      │
  │   ice_candidate}   │                  │                      │
  ├───────────────────>├─────────────────>├─────────────────────>│
  │                    │                  │                      │
  │                    │                  │  {type:              │
  │                    │                  │<─────────────────────┤  ice_candidate}
  │  {type:            │<─────────────────┤                      │
  │   ice_candidate}   │                  │                      │
  │<───────────────────┤                  │                      │
  │                    │                  │                      │
  │  ═══════════════════════════════════════════════════════════│
  │                    P2P CONNECTION ESTABLISHED                │
  │  ═══════════════════════════════════════════════════════════│
  │                                                               │
  │  RTP (Audio/Video) ──────────────────────────────────────────>│
  │<──────────────────────────────────────────────────────────────│
  │                                                               │
```


### WebSocket Packet Details:

**WebSocket Handshake:**
```
GET /ws/meeting/ABC/ HTTP/1.1
Host: 10.17.2.47:8000
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
Cookie: sessionid=xyz

HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
```

**WebSocket Messages (JSON):**

1. User Joined:
```json
{
  "type": "user_joined",
  "user_id": 2,
  "username": "teacher1"
}
```

2. WebRTC Offer (SDP):
```json
{
  "type": "offer",
  "offer": {
    "type": "offer",
    "sdp": "v=0\r\no=- 123456 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n..."
  },
  "from_user_id": 1,
  "to_user_id": 2
}
```

3. WebRTC Answer (SDP):
```json
{
  "type": "answer",
  "answer": {
    "type": "answer",
    "sdp": "v=0\r\no=- 789012 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n..."
  },
  "from_user_id": 2,
  "to_user_id": 1
}
```

4. ICE Candidate:
```json
{
  "type": "ice_candidate",
  "candidate": {
    "candidate": "candidate:1 1 UDP 2130706431 192.168.1.100 54321 typ host",
    "sdpMLineIndex": 0,
    "sdpMid": "0"
  },
  "from_user_id": 1,
  "to_user_id": 2
}
```

5. Chat Message:
```json
{
  "type": "chat",
  "message": "Hello everyone!",
  "username": "teacher1",
  "user_id": 1,
  "timestamp": "2026-03-03T10:30:00Z"
}
```

**Channel Layer (In-Memory):**
- Group: "meeting_ABC"
- Members: All connected users in meeting
- Message routing: Broadcast or targeted (to_user_id)

**WebRTC P2P Media:**
- Protocol: RTP over UDP (SRTP for encryption)
- Ports: Dynamic (49152-65535)
- Codecs: VP8/VP9 (video), Opus (audio)
- Bandwidth: 500 KB/s - 2 MB/s per peer
- NAT Traversal: STUN/TURN servers


## 5. PERMISSION CHECK FLOW

```
USER (Teacher)       DJANGO:8000                    DATABASE
  │                      │                              │
  │  GET /cameras/1/     │                              │
  │  feed/               │                              │
  ├─────────────────────>│                              │
  │                      │  Extract sessionid           │
  │                      │  from Cookie                 │
  │                      │                              │
  │                      │  SELECT * FROM               │
  │                      │  django_session              │
  │                      │  WHERE session_key=?         │
  │                      ├─────────────────────────────>│
  │                      │<─────────────────────────────┤
  │                      │  Session Data                │
  │                      │  (user_id=2)                 │
  │                      │                              │
  │                      │  SELECT * FROM               │
  │                      │  auth_user                   │
  │                      │  WHERE id=2                  │
  │                      ├─────────────────────────────>│
  │                      │<─────────────────────────────┤
  │                      │  User Object                 │
  │                      │                              │
  │                      │  SELECT * FROM               │
  │                      │  accounts_userprofile        │
  │                      │  WHERE user_id=2             │
  │                      ├─────────────────────────────>│
  │                      │<─────────────────────────────┤
  │                      │  UserProfile                 │
  │                      │  (user_type='teacher')       │
  │                      │                              │
  │                      │  SELECT * FROM               │
  │                      │  cameras_camerapermission    │
  │                      │  WHERE camera_id=1           │
  │                      │  AND teacher_id=2            │
  │                      ├─────────────────────────────>│
  │                      │<─────────────────────────────┤
  │                      │  Permission Record           │
  │                      │  (exists = True)             │
  │                      │                              │
  │                      │  ✓ Permission Granted        │
  │                      │  Proxy to Camera Service     │
  │  HTTP 200            │                              │
  │  [Stream Data]       │                              │
  │<─────────────────────┤                              │
```

### Permission Logic:

**Admin:**
- Username = 'Admin' OR is_superuser = True
- Access: ALL cameras, ALL features

**Teacher:**
- user_type = 'teacher'
- Access: Cameras with CameraPermission record
- Query: `CameraPermission.objects.filter(camera_id=X, teacher_id=Y).exists()`

**Student:**
- user_type = 'student'
- Access: ALL active cameras (is_active=True)
- No permission check needed


## 6. CAMERA SERVICE BACKGROUND THREAD

```
CAMERA SERVICE (Port 8001)
  │
  │  CameraManager.get_streamer(camera_id, rtsp_url)
  │  ├─ Check if streamer exists
  │  ├─ If not, create new CameraStreamer
  │  └─ Start background thread
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│  CameraStreamer Background Thread                       │
│  ─────────────────────────────────                      │
│                                                          │
│  while running:                                          │
│    │                                                     │
│    ├─ Check inactivity (90 seconds)                     │
│    │  └─ If inactive, stop thread                       │
│    │                                                     │
│    ├─ If not connected:                                 │
│    │  ├─ Attempt connection (max 5 attempts)            │
│    │  ├─ cv2.VideoCapture(rtsp_url)                     │
│    │  ├─ Set timeouts (5000ms)                          │
│    │  └─ Test frame read                                │
│    │                                                     │
│    ├─ Read frame from camera:                           │
│    │  ├─ cap.read() → ret, frame                        │
│    │  ├─ Resize: (960, 540) → (640, 360)                │
│    │  ├─ Encode: JPEG quality 60                        │
│    │  ├─ Store in self.frame (thread-safe)              │
│    │  └─ Sleep 0.05s (~20 FPS)                          │
│    │                                                     │
│    └─ On error:                                         │
│       ├─ Release capture                                │
│       ├─ Sleep 2s (reconnect delay)                     │
│       └─ Retry connection                               │
│                                                          │
└─────────────────────────────────────────────────────────┘
  │
  │  HTTP Request arrives
  │  ├─ camera_feed(request, camera_id)
  │  ├─ streamer.get_frame()
  │  └─ Yield frame in MJPEG format
  │
  ▼
```

### Thread Safety:
- Lock: `threading.Lock()`
- Protected: `self.frame` (shared between threads)
- Read: `with self.lock: return self.frame`
- Write: `with self.lock: self.frame = jpeg_data`


## 7. COMPLETE DATA FLOW SUMMARY

```
┌─────────────────────────────────────────────────────────────────────┐
│  REQUEST TYPE          │  PROTOCOL  │  PORT  │  BANDWIDTH          │
├─────────────────────────────────────────────────────────────────────┤
│  Web Pages (HTML)      │  HTTP/1.1  │  8000  │  10-100 KB/request  │
│  Static Files (CSS/JS) │  HTTP/1.1  │  8000  │  5-50 KB/file       │
│  Media Files (Images)  │  HTTP/1.1  │  8000  │  50-500 KB/file     │
│  API Requests (JSON)   │  HTTP/1.1  │  8000  │  1-10 KB/request    │
│  WebSocket (Signaling) │  WS        │  8000  │  1-5 KB/message     │
│  RTSP Camera Stream    │  HTTP/MJPEG│  8001  │  300-600 KB/s       │
│  Mobile Camera Stream  │  HTTP/MJPEG│  8001  │  300-500 KB/s       │
│  WebRTC Media (P2P)    │  RTP/UDP   │  Dynamic│ 500 KB/s - 2 MB/s  │
│  Database Queries      │  SQLite    │  Local │  N/A                │
└─────────────────────────────────────────────────────────────────────┘
```
