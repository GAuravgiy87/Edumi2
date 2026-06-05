# 🎓 Edumi Complete Analysis - All Features & Functions

---

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [Directory Structure](#directory-structure)
3. [Core Apps & Features](#core-apps-features)
4. [Complete File Breakdown](#complete-file-breakdown)
5. [Database Models](#database-models)
6. [API & Views](#api-views)
7. [Services & Business Logic](#services-business-logic)
8. [WebSocket Consumers](#websocket-consumers)
9. [Docker & Deployment](#docker-deployment)

---

---

## <a name="project-overview">1. Project Overview</a>

**Edumi** is a comprehensive educational platform with:
- 📹 Live video conferencing via LiveKit
- 🎥 Camera management (RTSP, IP Webcam, DroidCam)
- 👤 Face recognition attendance tracking
- 📊 Head counting & engagement analytics
- 📹 Recording & playback
- 💬 Messaging system
- 📢 Notifications
- 🗂️ Classroom management

---

---

## <a name="directory-structure">2. Directory Structure</a>

```
Edumi2/
├── accounts/                    # User management, authentication, profiles
├── attendance/                  # Face recognition, attendance tracking, engagement
├── cameras/                     # Camera management, recording, head counting
├── meetings/                    # Classroom, meeting, video conferencing
├── mobile_cameras/              # Mobile camera integration
├── school_project/              # Django project settings & config
├── templates/                   # HTML templates
├── static/                      # Static assets (CSS, JS)
├── camera_service/              # Separate camera microservice
├── docker-compose.yml           # Docker orchestration
└── requirements.txt             # Python dependencies
```

---

---

## <a name="core-apps-features">3. Core Apps & Features</a>

| App Name | Features | Status |
|----------|----------|--------|
| **accounts** | User registration, login, profiles, messaging, notifications, admin panel | ✅ Working |
| **attendance** | Face registration, face recognition, attendance tracking, engagement reports | ✅ Working |
| **cameras** | Camera management, recording, live streaming, head counting | ✅ Working |
| **meetings** | Classroom management, meeting creation, LiveKit integration | ✅ Working |
| **mobile_cameras** | Mobile camera support | ✅ Working |

---

---

## <a name="complete-file-breakdown">4. Complete File Breakdown</a>

### <a name="accounts-app">4.1 `accounts/` - User Management App</a>

#### `accounts/models.py`
| Function/Model | Description | Code Snippet |
|----------------|-------------|--------------|
| **UserProfile** | Extended user profile with user type (student/teacher) | ```python\nclass UserProfile(models.Model):\n    USER_TYPE_CHOICES = (\n        ('student', 'Student'),\n        ('teacher', 'Teacher'),\n    )\n    user = models.OneToOneField(User, on_delete=models.CASCADE)\n    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)\n    # ... profile fields\n``` |
| **StudentPhoto** | Admin-only student photo storage | ```python\nclass StudentPhoto(models.Model):\n    student = models.ForeignKey(User, on_delete=models.CASCADE)\n    photo = models.ImageField(upload_to='student_photos/')\n``` |
| **Conversation & Message** | Direct messaging system | ```python\nclass Conversation(models.Model):\n    participants = models.ManyToManyField(User)\n    created_at = models.DateTimeField(auto_now_add=True)\n\nclass Message(models.Model):\n    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)\n    sender = models.ForeignKey(User, on_delete=models.CASCADE)\n    content = models.TextField()\n``` |
| **Notification** | Notification system for events | ```python\nclass Notification(models.Model):\n    recipient = models.ForeignKey(User, on_delete=models.CASCADE)\n    notification_type = models.CharField(max_length=30, choices=[...])\n    title = models.CharField(max_length=200)\n    # ...\n``` |

---

#### `accounts/views.py`
| Function | Purpose |
|----------|---------|
| `login_view` | User authentication |
| `register` | User registration |
| `profile_view` | View user profile |
| `home` | Home page |
| `teacher_dashboard` | Teacher dashboard |
| `student_dashboard` | Student dashboard |
| `inbox` | Message inbox |
| `conversation_detail` | View conversation |
| `send_message` | Send message |
| `admin_panel` | Admin dashboard |
| `architecture_view` | System architecture visualization |

---

#### `accounts/consumers.py`
| Consumer | Purpose |
|----------|---------|
| **NotificationConsumer** | WebSocket for real-time notifications |
| | ```python\nclass NotificationConsumer(AsyncWebsocketConsumer):\n    async def connect(self):\n        self.user_id = self.scope['user'].id\n        self.group_name = f"user_{self.user_id}"\n        await self.channel_layer.group_add(self.group_name, self.channel_name)\n``` |

---

#### `accounts/notification_utils.py`
| Function | Purpose |
|----------|---------|
| `send_ws_notification` | Send WebSocket notification to user |
| `notify_new_message` | New message notification |
| `notify_meeting_scheduled` | Meeting scheduled notification |
| `notify_meeting_started` | Meeting started notification |
| `notify_meeting_cancelled` | Meeting cancelled notification |
| `notify_classroom_join_request` | Join request notification |
| `notify_classroom_request_approved/denied` | Request approval/denial notification |
| `notify_student_joined_classroom` | Student joined notification |

---

#### `accounts/services.py`
| Function | Purpose |
|----------|---------|
| `get_profile_completion` | Calculate profile completion percentage |
| `get_teacher_stats` | Teacher dashboard statistics |
| `get_student_stats` | Student dashboard statistics |
| `get_admin_stats` | Admin panel statistics |

---

#### `accounts/urls.py`
| URL Route | View |
|-----------|------|
| `/` | `login_view` |
| `/register/` | `register` |
| `/home/` | `home` |
| `/profile/` | `profile_view` |
| `/inbox/` | `inbox` |
| `/admin-panel/` | `admin_panel` |
| `/notifications/` | Notifications list |

---

---

### <a name="attendance-app">4.2 `attendance/` - Attendance & Face Recognition</a>

#### `attendance/models.py`
| Model | Purpose |
|-------|---------|
| **StudentFaceProfile** | Encrypted face embedding storage |
| **ClassSchedule** | Classroom schedule definition |
| **AttendanceRecord** | Attendance entry with status |
| **FaceRecognitionLog** | Audit log for recognition attempts |
| **AttendanceSettings** | Per-classroom face recognition settings |
| **EngagementReport** | Post-meeting engagement analysis |
| **StudentEngagementSnapshot** | Raw engagement snapshots |
| **FaceResetRequest** | Student request to reset face profile |

---

#### `attendance/face_service.py`
| Function/Class | Purpose | Code Snippet |
|-----------------|---------|--------------|
| **FaceService** | Main face recognition service | ```python\nclass FaceService:\n    def extract_embedding(self, image_bytes, live=False):\n        # Extract face embedding\n        # Anti-spoofing checks\n    \n    def compare_frame_to_stored(self, frame_bytes, encrypted_embedding, threshold):\n        # Compare live frame with stored embedding\n``` |
| `extract_embedding` | Extract face embedding from image | - |
| `compare_frame_to_stored` | Compare live frame with stored profile | - |
| `get_face_service()` | Get singleton instance | - |

---

#### `attendance/views.py`
| Function | Purpose |
|----------|---------|
| `face_setup` | Student face registration |
| `upload_face_photo` | Upload face photo |
| `capture_face_photo` | Capture photo via webcam |
| `engagement_report_view` | View engagement report |
| Daily attendance report views | - |

---

#### `attendance/services.py`
| Function | Purpose |
|----------|---------|
| `get_daily_report_context` | Generate daily attendance report |
| `get_classroom_attendance_stats` | Overall attendance statistics |

---

---

### <a name="cameras-app">4.3 `cameras/` - Camera Management & Recording</a>

#### `cameras/models.py`
| Model | Purpose |
|-------|---------|
| **Camera** | RTSP/IP/DroidCam camera definition |
| **CameraPermission** | Teacher access to cameras |
| **CameraRecording** | Recording record |
| **RecordingChunk** | Chunked recording storage |
| **HeadCountLog** | Head count history |
| **HeadCountSession** | Active head counting session |

---

#### `cameras/recording_engine.py`
| Class/Function | Purpose |
|----------------|---------|
| **RecordingEngine** | FFmpeg-based recording engine |
| `start_recording` | Start camera recording |
| `stop_recording` | Stop recording & finalize |
| `is_recording` | Check if recording active |
| `cleanup_orphaned_recordings` | Fix stuck recordings |

---

#### `cameras/head_count_service.py`
| Class/Function | Purpose |
|----------------|---------|
| **HeadDetector** | Multi-model head/face detection |
| **HeadCountManager** | Manage head counting sessions |
| `start_session` | Start counting for camera |
| `stop_session` | Stop counting session |

---

---

### <a name="meetings-app">4.4 `meetings/` - Classrooms & Video Conferences</a>

#### `meetings/models.py`
| Model | Purpose |
|-------|---------|
| **Classroom** | Persistent classroom with members |
| **ClassroomMembership** | Student membership & approval |
| **Meeting** | Video conference session |
| **MeetingParticipant** | Meeting participant details |
| **MeetingAttendanceLog** | Entry/exit log per participant |
| **MeetingChat** | Meeting chat messages |
| **MeetingSummary** | Post-meeting summary |
| **KickedParticipant** | Kicked/banned users |

---

#### `meetings/consumers.py`
| Consumer | Purpose |
|----------|---------|
| **MeetingConsumer** | WebSocket for real-time meeting |
| | - Participant join/leave<br>- WebRTC signaling<br>- Chat<br>- Permission controls |

---

#### `meetings/services.py`
| Function | Purpose |
|----------|---------|
| `get_classroom_detail_context` | Context data for classroom page |

---

---

### <a name="docker-files">4.5 Docker & Deployment Files</a>

#### `docker-compose.yml`
| Service | Purpose |
|---------|---------|
| **db** | PostgreSQL database |
| **redis** | Redis cache/message broker |
| **livekit** | LiveKit video conferencing server |
| **web** | Main Django app |
| **worker** | Celery background worker |
| **camera_service** | Camera microservice |
| **nginx** | Reverse proxy & static files |

---

#### `Dockerfile`
```dockerfile
FROM python:3.11-slim
# ... installs dependencies, collects static
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "school_project.asgi:application"]
```

---

#### `camera_service/Dockerfile`
```dockerfile
FROM python:3.11-slim
# ... installs OpenCV, FFmpeg
CMD ["python", "manage.py", "runserver", "0.0.0.0:8001"]
```

---

---

## <a name="database-models">5. Complete Database Schema Overview</a>

### User & Account Tables
| Table | Purpose |
|-------|---------|
| `auth_user` | Django built-in user |
| `accounts_userprofile` | Extended user profile |
| `accounts_studentphoto` | Admin photos |
| `accounts_conversation` | Message threads |
| `accounts_message` | Messages |
| `accounts_notification` | Notifications |

---

### Attendance Tables
| Table | Purpose |
|-------|---------|
| `attendance_studentfaceprofile` | Encrypted face embeddings |
| `attendance_classschedule` | Class schedules |
| `attendance_attendancerecord` | Attendance entries |
| `attendance_facerecognitionlog` | Recognition audit |
| `attendance_attendancesettings` | FR settings |
| `attendance_engagementreport` | Engagement reports |
| `attendance_studentengagementsnapshot` | Snapshots |
| `attendance_faceresetrequest` | Reset requests |

---

### Camera Tables
| Table | Purpose |
|-------|---------|
| `cameras_camera` | Camera definitions |
| `cameras_camerapermission` | Teacher access |
| `cameras_camerarecording` | Recordings |
| `cameras_recordingchunk` | Chunks |
| `cameras_headcountlog` | Head count history |
| `cameras_headcountsession` | Active sessions |

---

### Meeting Tables
| Table | Purpose |
|-------|---------|
| `meetings_classroom` | Classrooms |
| `meetings_classroommembership` | Memberships |
| `meetings_meeting` | Meetings |
| `meetings_meetingparticipant` | Participants |
| `meetings_meetingattendancelog` | Entry/exit logs |
| `meetings_meetingchat` | Chat |
| `meetings_meetingsummary` | Summaries |
| `meetings_kickedparticipant` | Kicked users |

---

---

## <a name="api-views">6. Main Views & Routes Summary</a>

### Authentication Routes (accounts)
| Path | Method | Purpose |
|------|--------|---------|
| `/` | GET/POST | Login |
| `/register/` | GET/POST | Register |
| `/logout/` | POST | Logout |
| `/profile/` | GET | View profile |

---

### Classroom & Meeting Routes (meetings)
| Path | Purpose |
|------|---------|
| `/meetings/classrooms/` | List classrooms |
| `/meetings/classroom/<id>/` | View classroom |
| `/meetings/join/<code>/` | Join meeting |

---

### Camera Routes (cameras)
| Path | Purpose |
|------|---------|
| `/cameras/` | Camera management |
| `/cameras/<id>/stream/` | Watch live stream |
| `/cameras/recordings/` | Recording management |

---

---

## <a name="services-business-logic">7. Core Services & Business Logic</a>

### 7.1 Face Recognition Pipeline (`attendance/face_service.py`)
```
Image Input → Low-light Enhancement → Face Detection
    ↓
Extract Embedding → Compare with Stored → Attendance Logged
    ↓
Anti-spoofing (motion, static check)
```

---

### 7.2 Recording Flow (`cameras/recording_engine.py`)
```
Start → FFmpeg Process → Chunked/Direct File
    ↓
Background Monitoring → Auto-save on Crash
    ↓
Finalize → Process → Save to DB
```

---

### 7.3 Meeting Flow (`meetings/consumers.py`)
```
Join → WS Connect → Participant List
    ↓
WebRTC Signaling (Offer/Answer/Candidate)
    ↓
Audio/Video/Share → Chat → Leave
```

---

---

## <a name="websocket-consumers">8. WebSocket Consumers</a>

| Consumer | Path | Events Handled |
|----------|------|----------------|
| `NotificationConsumer` | `/ws/notifications/` | Notifications, new messages |
| `MeetingConsumer` | `/ws/meeting/<code>/` | Join/Leave, WebRTC, Chat, Controls |

---

---

## <a name="docker-deployment">9. Docker & Production Setup</a>

### 9.1 Complete `docker-compose.yml` Services
| Container | Image | Ports | Volumes |
|-----------|-------|-------|---------|
| **db** | `postgres:15-alpine` | - | `postgres_data` |
| **redis** | `redis:7-alpine` | - | `redis_data` |
| **livekit** | `livekit/livekit-server:v1.5.2` | `7880, 7881, 50000-50200` | Config file |
| **web** | `edumi-web` (built) | `8000` | `media_data, static_data` |
| **worker** | `edumi-web` (built) | - | Same as web |
| **camera_service** | `edumi-camera` (built) | `8001` | - |
| **nginx** | `nginx:alpine` | `80` | Static, media |

---

### 9.2 Environment Variables
| Variable | Purpose |
|----------|---------|
| `DEBUG` | Production: `False` |
| `SECRET_KEY` | Django secret |
| `ALLOWED_HOSTS` | `*` for development |
| `DATABASE_URL` | PostgreSQL connection |
| `REDIS_URL` | Redis connection |
| `LIVEKIT_URL` | LiveKit proxy URL |
| `LIVEKIT_INTERNAL_URL` | LiveKit internal WS URL |

---

---

## 📊 Quick Feature Matrix

| Feature | Status | Dependencies |
|---------|--------|--------------|
| User Auth | ✅ | Django Auth |
| Classroom Mgmt | ✅ | Django ORM |
| Live Video Calls | ✅ | LiveKit |
| Camera RTSP/IP | ✅ | OpenCV |
| Face Recognition | ✅ | face_recognition, OpenCV |
| Attendance Tracking | ✅ | Attendance app |
| Head Counting | ✅ | OpenCV HOG |
| Recording | ✅ | FFmpeg |
| Notifications | ✅ | Django Channels + Redis |
| Messaging | ✅ | Database |
| Engagement Reports | ✅ | Face Analysis |

---

---

## 🔗 Key Integration Points

1. **LiveKit ↔ Django** via WebSocket proxy (`nginx.conf`)
2. **Camera ↔ Main App** via dedicated microservice on `:8001`
3. **Background Tasks** via Celery + Redis
4. **Real-time** via Django Channels + Redis

---

---

## 📝 Notes for Developers

- **NumPy Version**: Use `< 2.0.0` for OpenCV compatibility
- **Static Files**: Served via WhiteNoise & Nginx
- **Database**: PostgreSQL (Docker) for production
- **Security**: Production: `DEBUG=False`, CSRF trusted origins, etc.

---

**Document generated**: 2026-05-29
