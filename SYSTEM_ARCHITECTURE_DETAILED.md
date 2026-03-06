# DETAILED SYSTEM ARCHITECTURE - EDUMI PLATFORM
## Complete Backend Communication Flow & Packet Analysis

```
================================================================================
                        COMPLETE SYSTEM ARCHITECTURE
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Browser    │  │  Mobile App  │  │  IP Webcam   │  │  DroidCam    │   │
│  │  (Chrome/    │  │  (Android/   │  │   App        │  │    App       │   │
│  │   Firefox)   │  │    iOS)      │  │              │  │              │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                  │                  │            │
│         │ HTTP/HTTPS      │ HTTP/HTTPS       │ HTTP/MJPEG      │ HTTP/MJPEG │
│         │ WebSocket       │ WebSocket        │ Stream          │ Stream     │
│         │                 │                  │                  │            │
└─────────┼─────────────────┼──────────────────┼──────────────────┼────────────┘
          │                 │                  │                  │
          │                 │                  │                  │
          ▼                 ▼                  ▼                  ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                         NETWORK/FIREWALL LAYER                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LAN: 10.17.2.47 (Development)                                              │
│  Ports: 8000 (Main), 8001 (Camera Service), 8080 (Mobile Cameras)          │
│  Firewall: Windows Firewall (allow_firewall.bat)                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          │
          ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                    PRODUCTION: NGINX REVERSE PROXY                           │
│                         (Port 80/443)                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  NGINX Configuration                                                │    │
│  │  ────────────────────                                               │    │
│  │                                                                      │    │
│  │  • SSL/TLS Termination (Let's Encrypt)                             │    │
│  │  • HTTP → HTTPS Redirect (Port 80 → 443)                           │    │
│  │  • Static File Serving (/static/)                                  │    │
│  │  • Media File Serving (/media/)                                    │    │
│  │  • Request Routing & Load Balancing                                │    │
│  │  • WebSocket Upgrade Handling                                      │    │
│  │  • Proxy Buffering Control                                         │    │
│  │                                                                      │    │
│  │  Upstream Servers:                                                  │    │
│  │  ├─ django_main: 127.0.0.1:8000                                    │    │
│  │  └─ camera_service: 127.0.0.1:8001                                 │    │
│  │                                                                      │    │
│  │  Location Routing:                                                  │    │
│  │  ├─ /static/      → Direct file serving (expires 30d)              │    │
│  │  ├─ /media/       → Direct file serving (expires 7d)               │    │
│  │  ├─ /api/cameras/ → Proxy to camera_service:8001                   │    │
│  │  ├─ /ws/          → WebSocket proxy to django_main:8000            │    │
│  │  └─ /             → Proxy to django_main:8000                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────┬───────────────────────────────┬───────────────────────────────┘
               │                               │
               │                               │
               ▼                               ▼

┌──────────────────────────────────┐  ┌──────────────────────────────────┐
│   MAIN DJANGO APPLICATION        │  │   CAMERA SERVICE                 │
│   (Port 8000)                    │  │   (Port 8001)                    │
│   ─────────────────────          │  │   ─────────────────              │
│                                  │  │                                  │
│   ASGI Server: Daphne            │  │   WSGI Server: Django Dev        │
│   Protocol: HTTP/1.1, WS         │  │   Protocol: HTTP/1.1             │
│                                  │  │                                  │
└──────────────┬───────────────────┘  └──────────────┬───────────────────┘
               │                                     │
               │                                     │
               ▼                                     ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                        APPLICATION LAYER DETAILS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  MAIN DJANGO APP (school_project) - Port 8000                      │    │
│  │  ═══════════════════════════════════════════════════════           │    │
│  │                                                                      │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  PROTOCOL ROUTER (ASGI)                                       │  │    │
│  │  │  ─────────────────────                                        │  │    │
│  │  │                                                                │  │    │
│  │  │  ┌─────────────────┐         ┌─────────────────────────────┐ │  │    │
│  │  │  │  HTTP Protocol  │         │  WebSocket Protocol         │ │  │    │
│  │  │  │  (Django Views) │         │  (Channels + Consumers)     │ │  │    │
│  │  │  └────────┬────────┘         └────────┬────────────────────┘ │  │    │
│  │  │           │                           │                       │  │    │
│  │  └───────────┼───────────────────────────┼───────────────────────┘  │    │
│  │              │                           │                          │    │
│  │              ▼                           ▼                          │    │
│  │                                                                      │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  HTTP REQUEST ROUTING (Django URLs)                          │  │    │
│  │  │  ──────────────────────────────────                          │  │    │
│  │  │                                                                │  │    │
│  │  │  /                    → accounts.urls                         │  │    │
│  │  │  /accounts/           → accounts.urls                         │  │    │
│  │  │  /cameras/            → cameras.urls                          │  │    │
│  │  │  /mobile-cameras/     → mobile_cameras.urls                   │  │    │
│  │  │  /meetings/           → meetings.urls                         │  │    │
│  │  │  /admin/              → Django Admin                          │  │    │
│  │  │  /static/             → Static files (dev only)               │  │    │
│  │  │  /media/              → Media files (dev only)                │  │    │
│  │  │                                                                │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │                                                                      │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  WEBSOCKET ROUTING (Channels)                                │  │    │
│  │  │  ────────────────────────────                                │  │    │
│  │  │                                                                │  │    │
│  │  │  ws://host/ws/meeting/<code>/  → MeetingConsumer             │  │    │
│  │  │                                                                │  │    │
│  │  │  Channel Layer: InMemoryChannelLayer                          │  │    │
│  │  │  (Production: Redis Channel Layer)                            │  │    │
│  │  │                                                                │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │                                                                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  CAMERA SERVICE (Isolated) - Port 8001                             │    │
│  │  ═══════════════════════════════════════                           │    │
│  │                                                                      │    │
│  │  API Endpoints:                                                     │    │
│  │  ├─ GET  /api/cameras/                  → List cameras             │    │
│  │  ├─ GET  /api/cameras/<id>/feed/        → RTSP stream (MJPEG)      │    │
│  │  ├─ GET  /api/cameras/<id>/test/        → Test RTSP connection     │    │
│  │  ├─ GET  /api/mobile-cameras/<id>/feed/ → Mobile stream (MJPEG)    │    │
│  │  └─ GET  /api/mobile-cameras/<id>/test/ → Test mobile connection   │    │
│  │                                                                      │    │
│  │  Background Threads:                                                │    │
│  │  ├─ CameraStreamer (per RTSP camera)                               │    │
│  │  └─ MobileCameraStreamer (per mobile camera)                       │    │
│  │                                                                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
               │                                     │
               │                                     │
               ▼                                     ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                          DJANGO APPS LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   accounts   │  │   cameras    │  │mobile_cameras│  │   meetings   │   │
│  │              │  │              │  │              │  │              │   │
│  │  • Auth      │  │  • RTSP Mgmt │  │  • HTTP Mgmt │  │  • WebRTC    │   │
│  │  • Profile   │  │  • Proxy     │  │  • Proxy     │  │  • WebSocket │   │
│  │  • Roles     │  │  • Perms     │  │  • Perms     │  │  • Chat      │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                  │                  │            │
│         └─────────────────┴──────────────────┴──────────────────┘            │
│                                     │                                        │
│                                     ▼                                        │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  DJANGO ORM (Object-Relational Mapping)                            │    │
│  │  ──────────────────────────────────────                            │    │
│  │                                                                      │    │
│  │  Models:                                                            │    │
│  │  ├─ User (Django Auth)                                              │    │
│  │  ├─ UserProfile (accounts)                                          │    │
│  │  ├─ Camera (cameras)                                                │    │
│  │  ├─ CameraPermission (cameras)                                      │    │
│  │  ├─ MobileCamera (mobile_cameras)                                   │    │
│  │  ├─ MobileCameraPermission (mobile_cameras)                         │    │
│  │  ├─ Meeting (meetings)                                              │    │
│  │  └─ MeetingParticipant (meetings)                                   │    │
│  │                                                                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
└─────────────────────────────────────┼────────────────────────────────────────┘
                                      │
                                      ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATABASE LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  SQLite3 (Development)                                              │    │
│  │  ─────────────────────                                              │    │
│  │                                                                      │    │
│  │  File: db.sqlite3                                                   │    │
│  │  Location: Project Root                                             │    │
│  │                                                                      │    │
│  │  Tables:                                                            │    │
│  │  ├─ auth_user                                                       │    │
│  │  ├─ accounts_userprofile                                            │    │
│  │  ├─ cameras_camera                                                  │    │
│  │  ├─ cameras_camerapermission                                        │    │
│  │  ├─ mobile_cameras_mobilecamera                                     │    │
│  │  ├─ mobile_cameras_mobilecamerapermission                           │    │
│  │  ├─ meetings_meeting                                                │    │
│  │  ├─ meetings_meetingparticipant                                     │    │
│  │  └─ django_session                                                  │    │
│  │                                                                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  PostgreSQL (Production)                                            │    │
│  │  ───────────────────                                                │    │
│  │                                                                      │    │
│  │  Host: localhost:5432                                               │    │
│  │  Database: edumi                                                    │    │
│  │  User: edumi_user                                                   │    │
│  │                                                                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SYSTEMS & PROTOCOLS                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  RTSP CAMERAS (IP Cameras)                                          │    │
│  │  ─────────────────────────                                          │    │
│  │                                                                      │    │
│  │  Protocol: RTSP (Real Time Streaming Protocol)                     │    │
│  │  Port: 554 (default)                                                │    │
│  │  Codec: H.264, MPEG-4                                               │    │
│  │  Transport: TCP/UDP (RTP)                                           │    │
│  │                                                                      │    │
│  │  URL Format: rtsp://user:pass@ip:port/path                         │    │
│  │  Example: rtsp://admin:pass@192.168.1.100:554/live                 │    │
│  │                                                                      │    │
│  │  Connection Flow:                                                   │    │
│  │  1. DESCRIBE → Get stream info                                     │    │
│  │  2. SETUP    → Setup transport                                     │    │
│  │  3. PLAY     → Start streaming                                     │    │
│  │  4. RTP      → Receive video packets                               │    │
│  │                                                                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  MOBILE CAMERAS (IP Webcam / DroidCam)                              │    │
│  │  ─────────────────────────────────────────                          │    │
│  │                                                                      │    │
│  │  Protocol: HTTP/MJPEG (Motion JPEG)                                 │    │
│  │  Port: 8080 (default)                                               │    │
│  │  Format: Multipart JPEG stream                                      │    │
│  │  Transport: HTTP/1.1                                                │    │
│  │                                                                      │    │
│  │  URL Format: http://ip:port/video                                  │    │
│  │  Example: http://192.168.1.101:8080/video                          │    │
│  │                                                                      │    │
│  │  Stream Format:                                                     │    │
│  │  Content-Type: multipart/x-mixed-replace; boundary=--frame         │    │
│  │  --frame                                                            │    │
│  │  Content-Type: image/jpeg                                           │    │
│  │  [JPEG DATA]                                                        │    │
│  │  --frame                                                            │    │
│  │  ...                                                                │    │
│  │                                                                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  WEBRTC (Peer-to-Peer Video/Audio)                                  │    │
│  │  ─────────────────────────────────                                  │    │
│  │                                                                      │    │
│  │  Signaling: WebSocket (via Django Channels)                         │    │
│  │  Media: Direct P2P (STUN/TURN)                                      │    │
│  │  Protocols: UDP (preferred), TCP (fallback)                         │    │
│  │  Codecs: VP8, VP9, H.264, Opus                                      │    │
│  │                                                                      │    │
│  │  Connection Flow:                                                   │    │
│  │  1. WebSocket Connect → Join meeting room                          │    │
│  │  2. Exchange SDP Offer/Answer → Negotiate capabilities             │    │
│  │  3. Exchange ICE Candidates → Find best connection path            │    │
│  │  4. P2P Media Stream → Direct audio/video                          │    │
│  │                                                                      │    │
│  │  Signaling Messages:                                                │    │
│  │  ├─ user_joined                                                     │    │
│  │  ├─ user_left                                                       │    │
│  │  ├─ offer (SDP)                                                     │    │
│  │  ├─ answer (SDP)                                                    │    │
│  │  ├─ ice_candidate                                                   │    │
│  │  └─ chat                                                            │    │
│  │                                                                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘


================================================================================
                    DETAILED PACKET FLOW ANALYSIS
================================================================================
