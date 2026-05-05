# Edumi — System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         CLIENTS                                             │
│                                                                                             │
│          Browser                  Mobile / Tablet                  ngrok                   │
│       HTTP · WSS · HLS          HTTP · WSS · HLS             HTTPS tunnel                  │
└──────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                           │
                                           │ HTTP :80   WSS :80
                                           │
┌──────────────────────────────────────────▼──────────────────────────────────────────────────┐
│                                    LAYER 1 · ENTRY                                          │
│                                                                                             │
│                          ┌──────────────────────────────┐                                  │
│                          │       Nginx  :80 / :443       │                                  │
│                          │                               │                                  │
│                          │  /static/  ──► staticfiles/   │                                  │
│                          │  /media/   ──► media/         │                                  │
│                          │  /ws/      ──► ip_hash        │                                  │
│                          │  /*        ──► least_conn     │                                  │
│                          └──────────────┬────────────────┘                                  │
│                                         │                                                   │
│                          ┌──────────────┼──────────────┐                                   │
│                          │              │              │                                    │
│                       :8010          :8011          :8012                                   │
│                      Worker 1       Worker 2       Worker 3                                 │
└──────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                           │
                                           │ ASGI  HTTP + WebSocket
                                           │
┌──────────────────────────────────────────▼──────────────────────────────────────────────────┐
│                               LAYER 2 · APPLICATION                                         │
│                               Django + Daphne ASGI                                          │
│                                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  HTTP  urls.py                                                                       │   │
│  │                                                                                      │   │
│  │  /                  ──► accounts     auth · profiles · inbox · notifications         │   │
│  │  /meetings/         ──► meetings     classrooms · video call · LiveKit token         │   │
│  │  /attendance/       ──► attendance   face setup · records · reports · export         │   │
│  │  /cameras/          ──► cameras      RTSP feed · live class · head count             │   │
│  │  /mobile-cameras/   ──► mobile_cam   IP Webcam · DroidCam feed                      │   │
│  │  /admin/            ──► Django admin                                                 │   │
│  │  /health/           ──► load balancer probe                                         │   │
│  └──────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  WebSocket  asgi.py                                                                  │   │
│  │                                                                                      │   │
│  │  ws/meeting/<code>/        ──► MeetingConsumer                                       │   │
│  │                                WebRTC signalling · chat · participant sync           │   │
│  │                                                                                      │   │
│  │  ws/attendance/<code>/     ──► FaceAttendanceConsumer                                │   │
│  │                                frame recv · face match · mark present                │   │
│  │                                                                                      │   │
│  │  ws/face-tracking/<code>/  ──► FaceTrackingConsumer                                  │   │
│  │                                engagement · emotion detection                        │   │
│  │                                                                                      │   │
│  │  ws/live-class/<key>/      ──► LiveClassConsumer                                     │   │
│  │                                viewer count sync                                     │   │
│  │                                                                                      │   │
│  │  livekit-proxy/            ──► LiveKitProxyConsumer                                  │   │
│  │                                WS proxy ──► LiveKit SFU :7880                        │   │
│  └──────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                │                                            │
│                                   internal HTTP :8001                                       │
└────────────────────────────────────────────────┼────────────────────────────────────────────┘
                                                 │
                                                 │
┌────────────────────────────────────────────────▼────────────────────────────────────────────┐
│                          LAYER 3 · CAMERA SERVICE  :8001                                    │
│                          isolated Django · not exposed to browser                           │
│                                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐   │
│   │  HLSProxyManager                                                                    │   │
│   │                                                                                     │   │
│   │   get_streamer(id, url)                                                             │   │
│   │          │                                                                          │   │
│   │          ▼                                                                          │   │
│   │   HLSStreamer  (one thread per camera)                                              │   │
│   │          │                                                                          │   │
│   │          ├── FFmpeg  ─c:v copy  (zero re-encode)                                   │   │
│   │          ├── rolling 3-segment window  (~6 s live only)                            │   │
│   │          ├── delete_segments  (no disk accumulation)                               │   │
│   │          └── idle shutdown after 30 s                                              │   │
│   └─────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                             │
│   /api/cameras/{id}/feed/          ──► .m3u8 manifest + .ts segments                       │
│   /api/cameras/{id}/test/          ──► ffprobe validation                                  │
│   /api/mobile-cameras/{id}/feed/   ──► mobile HTTP stream                                  │
│   /api/live-class/start|stop/      ──► RTMP ingest control                                 │
│                                                                                             │
└──────────────────────────┬──────────────────────────────────┬───────────────────────────────┘
                           │                                  │
                           │ RTSP / TCP                       │ HTTP
                           │                                  │
              ┌────────────▼────────────┐        ┌───────────▼───────────┐
              │     RTSP Camera         │        │    Mobile Camera      │
              │     IP : 554            │        │    IP : 8080 / 4747   │
              │     H.264 stream        │        │    MJPEG / HTTP       │
              └─────────────────────────┘        └───────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                               LAYER 4 · INFRASTRUCTURE                                      │
│                                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│  │  SQLite /       │  │  Redis  :6379   │  │  LiveKit  :7880 │  │  Celery         │        │
│  │  PostgreSQL     │  │                 │  │                 │  │  Worker         │        │
│  │                 │  │  WS channel     │  │  WebRTC SFU     │  │                 │        │
│  │  all models     │  │  layer          │  │  audio / video  │  │  recording      │        │
│  │  shared by      │  │                 │  │  rooms          │  │  processing     │        │
│  │  both Django    │  │  Celery broker  │  │                 │  │  tasks          │        │
│  │  apps           │  │                 │  │                 │  │                 │        │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```
