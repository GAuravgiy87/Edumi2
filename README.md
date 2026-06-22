<div align="center">
  <h1>🎓 EduMi2</h1>
  <h3>The Complete Academic Command Center</h3>
  
  <p>
    <img src="https://img.shields.io/badge/Python-3.14%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.14+">
    <img src="https://img.shields.io/badge/Django-4.2%2B-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django 4.2+">
    <img src="https://img.shields.io/badge/Daphne-ASGI-7B3F85?style=for-the-badge" alt="Daphne">
    <img src="https://img.shields.io/badge/LiveKit-WebRTC-00C58E?style=for-the-badge" alt="LiveKit">
    <img src="https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" alt="OpenCV">
    <img src="https://img.shields.io/badge/FFmpeg-Video%20Processing-007808?style=for-the-badge&logo=ffmpeg&logoColor=white" alt="FFmpeg">
    <img src="https://img.shields.io/badge/Redis-Celery%20Queue-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis + Celery">
  </p>

  <p>
    <a href="#-about-edumi2">About</a> •
    <a href="#-what-makes-edumi2-unique">What's Unique?</a> •
    <a href="#-technology-stack">Tech Stack</a> •
    <a href="#-problem-solution">Problem & Solution</a> •
    <a href="#-folder-breakdown">Folders</a> •
    <a href="#-quick-start">Quick Start</a>
  </p>

  <br>
</div>

---

## 🚀 About EduMi2

**EduMi2** is the **all-in-one academic command center** that transforms how classrooms are managed!
It combines virtual meetings, AI-powered attendance tracking, facial recognition, engagement monitoring, video management, and live streaming into a single, cohesive platform built for educational institutions.

---

## ✨ What Makes EduMi2 Unique?

EduMi2 stands out because of these features:

### 1. 🔄 Dual Camera System (RTSP + Mobile)
- Use dedicated **RTSP cameras** for fixed classroom setups
- Or use **mobile phones** via IP Webcam (Android) or DroidCam (iPhone) for flexible, wireless streaming
- Perfect for labs, outdoor classes, or rooms without permanent camera installations

### 2. 🔒 Encrypted Facial Recognition
- Student face encodings are **encrypted at rest** using Fernet symmetric encryption
- No raw biometric data is ever stored
- SHA-256 checksums ensure data integrity

### 3. 📊 Real-Time Engagement Monitoring
- Track student attention using facial emotion and gaze detection
- Auto-generate engagement reports after each class
- Alert teachers if engagement drops below a threshold

### 4. ✂️ Non-Destructive Video Editor
- Edit recordings without touching the original files
- Timeline-based editing with actions like trim, split, mute, rotate, add text, add audio
- Saves edit actions as a sequence, only compiles when you export

### 5. 🏗️ Microservice Architecture
- Heavy computer vision processing is offloaded to a separate `camera_service`
- Prevents blocking the main Django app
- Allows scaling the AI service independently

### 6. ⚡ Real-Time Everything
- WebSocket-based notifications, messages, and updates
- Live meeting controls (mute all, end meeting, etc.)
- In-meeting chat and hand raising
- Live stream viewing with <1s latency

---

## 🛠️ Technology Stack

| Layer                | Technologies                                                                 |
|----------------------|-----------------------------------------------------------------------------|
| **Backend**          | Django 4.2+, Python 3.14+                                                  |
| **Realtime Comms**   | Daphne (ASGI), Django Channels, LiveKit SFU (WebRTC)                       |
| **AI/Computer Vision**| OpenCV, face_recognition, dlib                                              |
| **Video Processing** | FFmpeg                                                                      |
| **Database**         | SQLite (centralized in `database/`)                                         |
| **Task Queue**       | Celery + Redis                                                              |
| **Web Server**       | Nginx (production), Daphne (dev)                                            |
| **Deployment**       | Docker, Docker Compose                                                      |

---

## 🎯 Problem & Solution

### The Problems Schools Face Today:
1. **⏰ Wasted Time**: Manual attendance takes 5-10 minutes per class
2. **❓ Invisible Engagement**: No way to track if students are paying attention
3. **🔀 Tool Chaos**: 5+ different apps for meetings, recordings, streaming
4. **🔒 Security Risks**: Unencrypted biometric data
5. **💸 High Costs**: Expensive dedicated camera hardware

### How EduMi2 Solves Them:
1. **🤖 AI Attendance**: 100% automated with facial recognition
2. **👀 Engagement Analytics**: Real-time attention monitoring via CV
3. **🏠 One Platform**: Everything in one place
4. **🔐 Encrypted Biometrics**: Fernet symmetric encryption for face data
5. **📱 Flexible Cameras**: Use mobile phones instead of expensive hardware!

---

## 📁 Complete Folder Breakdown

Here is a detailed breakdown of every folder in the project:

---

### 1. `accounts/` - Identity & Access Management (IAM)
**Purpose**: The core user authentication, profile management, messaging, and notifications system

**Key Files & Directories**:
- `models.py`: Defines `UserProfile`, `StudentPhoto`, `Conversation`, `Message`, and `Notification`
- `messaging_models.py`: Peer-to-peer direct messaging models
- `notification_models.py`: System-wide notification models
- `views/`: Views for auth, dashboard, messaging, and profiles
- `urls/`: URL routes for all account-related functionality
- `consumers.py`: WebSocket consumers for real-time notifications
- `admin_list_views.py`: Custom admin views
- `context_processors.py`: Adds common template variables (timestamps, face registration status)
- `services.py`: Helper services for account operations

**How it Works**:
- Extends Django's built-in `User` model with a one-to-one `UserProfile`
- `UserProfile` includes fields for role (student/teacher), avatar, bio, student/teacher-specific info
- Supports real-time messaging and notifications via Django Channels WebSockets
- Used by every other app for authentication and access control

**Tech Used**: Django ORM, Django Channels, WebSockets

---

### 2. `attendance/` - AI Attendance & Engagement Tracking
**Purpose**: Automated attendance tracking using facial recognition, plus real-time student engagement monitoring

**Key Files & Directories**:
- `models.py`: 
  - `StudentFaceProfile`: Stores encrypted face embeddings (Fernet encryption)
  - `ClassSchedule`: Defines which days classes run
  - `AttendanceRecord`: One per student per meeting
  - `FaceRecognitionLog`: Audit trail for every recognition attempt
  - `AttendanceSettings`: Per-classroom attendance configuration
  - `EngagementReport`: Auto-generated post-meeting reports
  - `FaceResetRequest`: Student requests to re-register their face
  - `StudentEngagementSnapshot`: Raw per-frame engagement data
- `face_service.py`: Core facial recognition logic (128-d embeddings, similarity thresholds)
- `encryption_service.py`: Handles Fernet encryption/decryption of biometric data
- `engagement_service.py`: Engagement analysis logic
- `tasks.py`: Celery tasks for attendance aggregation and report generation
- `views/`: Views for face registration, reports, and teacher dashboards
- `templates/attendance/`: HTML templates for attendance UI
- `face_tracking_consumer.py`: WebSocket consumer for real-time face tracking
- `signals.py`: Django signals for attendance events
- `management/commands/cleanup_engagement_logs.py`: Management command to clean up old logs

**How it Works**:
1. Students register their face via the UI
2. Their face encoding is encrypted and stored
3. During class, video feeds are processed (by `camera_service`)
4. Face matches are verified against encrypted embeddings
5. Attendance is automatically recorded
6. Engagement snapshots are collected every few seconds
7. After class, an engagement report is auto-generated

**Tech Used**: OpenCV, face_recognition, dlib, Celery, Fernet encryption

---

### 3. `bin/` - Binary Resources
**Purpose**: Stores miscellaneous binary files and keys
- SSH keys (`gaurav`, `gaurav.pub`)
- `livekit.zip`: LiveKit server archive

---

### 4. `camera_service/` - AI Processing Microservice
**Purpose**: **Independent microservice** for heavy computer vision processing to avoid blocking the main Django app

**Key Files & Directories**:
- `camera_service/settings.py`: Django settings configured to share the main app's database
- `camera_api/views/streamer.py`: Manages OpenCV `VideoCapture` for stream ingestion
- `camera_api/views/headcount_views.py`: Face detection and headcount/engagement analysis
- `camera_api/views/mobile_views.py`: Mobile camera-specific processing
- `camera_api/views/rtsp_views.py`: RTSP camera-specific processing
- `requirements.txt`: Separate requirements for the microservice
- `Dockerfile`: Containerization for the service
- `serve.py`: WSGI server entry point

**How it Works**:
- Runs as a separate Django app on a different port (default 8003)
- Receives commands from the main app via HTTP
- Processes video streams using OpenCV and face_recognition
- Sends results back to the main app via WebSockets or shared database
- Prevents blocking the main ASGI event loop with CPU-intensive CV operations

**Tech Used**: Django, OpenCV, face_recognition, dlib, WebSockets

---

### 5. `cameras/` - Hardware IP Camera Management
**Purpose**: Register, manage, stream, and record from dedicated hardware IP cameras (RTSP)

**Key Files & Directories**:
- `models.py`: 
  - `Camera`: Camera configuration (IP, port, credentials, stream path)
  - `CameraPermission`: Grants teachers access to specific cameras
  - `CameraRecording`: Recordings from cameras (supports chunked recording)
  - `RecordingChunk`: Individual video chunks for large recordings
  - `HeadCountLog`: Stores head count data from feeds
  - `HeadCountSession`: Active head counting sessions
- `views_logic/`: Core view logic separated for clarity
  - `camera_views.py`: Camera management views
  - `head_count_views.py`: Head counting views
  - `permissions_views.py`: Permission management views
  - `streaming_views.py`: MJPEG streaming views for browser viewing
  - `video_views.py`: Video recording management views
  - `utils.py`: Helper utilities
- `recording_engine.py`: Background FFmpeg-based recording to chunks
- `head_count_service.py`: Head counting and engagement analysis service
- `tasks.py`: Celery tasks for recording management
- `consumers.py`: WebSocket consumers for live camera updates
- `urls/`: URL routes
- `templatetags/camera_extras.py`: Custom template tags for cameras

**How it Works**:
1. Admins register cameras via the UI
2. Permissions are granted to teachers
3. Streams can be viewed in-browser via MJPEG proxying
4. Recordings can be started/stopped (saved as chunks for large files)
5. Feeds are passed to `camera_service` for AI processing
6. Can optionally inject camera feeds directly into LiveKit meetings

**Tech Used**: OpenCV, FFmpeg, Django, WebSockets

---

### 6. `certs/` - Security Certificates
**Purpose**: Stores SSL/TLS certificates for secure HTTPS connections (if present)

---

### 7. `common/` - Shared Utilities & Helpers
**Purpose**: Reusable code shared by all apps to promote DRY (Don't Repeat Yourself) principles

**Key Files & Directories**:
- `models.py`: Abstract base models like `TimeStampedModel` (adds `created_at` and `updated_at`)
- `utils.py`: Helper functions for file handling, timezone conversion, JSON responses
- `templatetags/common_tags.py`: Custom Django template filters and tags
- `tests.py`: Shared tests
- `admin.py`: Shared admin configurations
- `apps.py`: App config

**How it Works**:
- Imported by every other app
- Provides common utilities so code isn't duplicated
- Doesn't depend on any specific app, avoiding circular imports

**Tech Used**: Django Template Tags, Python utilities

---

### 8. `config/` - Configuration Files
**Purpose**: Environment and service configuration files
- `.env.example`: Example environment variables (copy to `.env` and fill in)
- `.gitignore`: Git ignore for config files
- `.pyre_configuration`: Pyre type checking config
- `livekit.yaml`: LiveKit server configuration
- `pyproject.toml`: Python project dependencies and config
- `pyrightconfig.json`: Pyright type checking config

---

### 9. `database/` - Central Data Storage
**Purpose**: Centralized storage for database and user-generated media files
- `db.sqlite3` (or `db/sqlite/db.sqlite3`): Main SQLite database
- `media/`: User-generated content
  - `face_photos/`: Student face registration photos
  - `recordings/`: Camera and meeting recordings
  - `videos/`: Uploaded videos
  - `edited_videos/`: Edited video outputs
  - `head_count_snapshots/`: Annotated head count frames
  - `profile_pictures/`: User profile pictures
  - `student_photos/`: Admin-only student photos

---

### 10. `docs/` - Project Documentation
**Purpose**: Complete project documentation
- `DEPLOY.md`: Deployment guide
- `EDUMI_COMPLETE_ANALYSIS.md`: Full system analysis
- `PROJECT_COMPLETE_GUIDE.md`: User guide
- `REFACTORING_COMPLETE.md`: Refactoring history
- `systemarchitecture.md`: System architecture diagrams and explanation
- `EduMi2_System_Analysis.xlsx`: System analysis spreadsheet

---

### 11. `livekit-bin/` - LiveKit Server Executable
**Purpose**: Stores the LiveKit WebRTC SFU (Selective Forwarding Unit) server binary
- `livekit-server.exe`: LiveKit server for Windows
- `LICENSE`: LiveKit license

**Tech Used**: LiveKit WebRTC SFU

---

### 12. `meetings/` - Virtual Classroom Orchestration
**Purpose**: Scheduling, managing, and running LiveKit-powered virtual meetings

**Key Files & Directories**:
- `models.py`:
  - `Classroom`: Persistent virtual classroom with membership
  - `ClassroomMembership`: Tracks student approval status
  - `Meeting`: Individual meeting session
  - `MeetingParticipant`: Per-participant info
  - `MeetingAttendanceLog`: Detailed join/leave logs
  - `MeetingChat`: In-meeting chat messages
  - `MeetingSummary`: Auto-generated meeting summaries
  - `KickedParticipant`: Tracks kicked/banned users
- `views/`:
  - `classroom_views.py`: Classroom management
  - `meeting_views.py`: Meeting join/start/end
  - `meeting_controls.py`: Host controls (mute all, end meeting, etc.)
  - `attendance_history_views.py`: Attendance history
- `urls/`: URL routes
- `templates/meetings/`: Meeting UI templates
- `livekit_proxy.py` / `livekit_http_proxy.py`: Secure API wrappers for LiveKit
- `services.py`: Meeting-related services
- `tasks.py`: Celery tasks for meeting management
- `consumers.py`: WebSocket consumers for real-time meeting updates
- `apps.py`: App config

**How it Works**:
1. Teachers create a persistent `Classroom`
2. Students request to join and are approved
3. Teachers start a `Meeting` in the classroom
4. LiveKit JWT tokens are generated for participants
5. Participants join the LiveKit room via the UI
6. Host controls (mute all, end meeting) are sent via LiveKit APIs
7. Attendance is tracked via join/leave events
8. Meetings can be recorded (if enabled)

**Tech Used**: LiveKit WebRTC, Django Channels, WebSockets

---

### 13. `mobile_cameras/` - Wireless Mobile Camera Integration
**Purpose**: Use smartphones as wireless IP cameras via IP Webcam (Android) or DroidCam (iPhone)

**Key Files & Directories**:
- `models.py`:
  - `MobileCamera`: Mobile camera configuration (IP, port, type, credentials)
  - `MobileCameraPermission`: Grants teachers access to specific mobile cameras
- `views/`:
  - `camera_views.py`: Mobile camera management
  - `headcount_views.py`: Head counting from mobile feeds
  - `permission_views.py`: Permission management
  - `utils.py`: Network reachability validation
- `urls/`: URL routes
- `templates/mobile_cameras/`: UI templates
- `apps.py`: App config

**How it Works**:
1. Teacher installs IP Webcam/DroidCam on their phone
2. Connects phone to the same network as the server
3. Registers the phone as a `MobileCamera` in EduMi2
4. Streams are accessed just like RTSP cameras
5. Supports AI processing, recording, and streaming

**Tech Used**: Django, network validation

---

### 14. `nginx/` - Web Server & Reverse Proxy
**Purpose**: Nginx configuration for production deployment
- `nginx.conf`: Nginx server config (reverse proxy, static/media serving, SSL termination)

**Tech Used**: Nginx

---

### 15. `school_project/` - Django Project Root
**Purpose**: The core Django project configuration and entry point

**Key Files & Directories**:
- `settings.py`: **Master config file** (database, security, LiveKit, Celery, etc.)
- `urls.py`: Master URL config (includes all app URLs)
- `asgi.py`: ASGI entry point for Daphne/Channels
- `wsgi.py`: WSGI entry point (for compatibility)
- `celery.py`: Celery app initialization
- `middleware.py`: Custom middleware (e.g., `DatabaseErrorMiddleware` for SQLite lock handling)
- `__init__.py`: Makes it a Python package
- `apps.py`: App config

**Tech Used**: Django, ASGI, Celery

---

### 16. `scripts/` - Utility & Deployment Scripts
**Purpose**: Helper scripts for setup and deployment
- `allow_firewall.bat`: Windows batch script to allow firewall rules
- `allow_firewall.ps1`: Windows PowerShell script to allow firewall rules
- `deploy.sh`: Linux deployment script

---

### 17. `staticfiles/` - Static Assets (Production)
**Purpose**: Collects and serves static files (CSS, JS, images) in production (populated via `collectstatic`)

---

### 18. `templates/` - HTML Templates
**Purpose**: All Django HTML templates for the entire application

**Key Directories**:
- `accounts/`: Auth, profile, admin, messaging, dashboard templates
- `attendance/`: Attendance and engagement UI
- `cameras/`: Camera management, streaming, recording UI
- `meetings/`: Virtual meeting UI
- `mobile_cameras/`: Mobile camera UI
- `video_editing/`: Video editor UI
- `videos/`: Video management UI
- `components/`: Reusable UI components (navbar, sidebar, etc.)
- `layouts/`: Base HTML layouts
- `partials/`: Reusable HTML partials

**Tech Used**: Django Template Language (DTL), HTML, CSS, JavaScript

---

### 19. `video_editing/` - In-Platform Video Editor
**Purpose**: Non-destructive timeline-based video editor for recorded and uploaded videos

**Key Files & Directories**:
- `models.py`:
  - `VideoEditSession`: Tracks an editing session
  - `VideoEditAction`: Individual edit steps (trim, mute, rotate, add text, etc.)
- `views_logic/`:
  - `core_views.py`: Main editor views
  - `action_views.py`: API for adding/removing/edit actions
  - `download_view.py`: Download edited videos
  - `utils.py`: **Core engine** that converts edit actions to FFmpeg commands
- `views.py`: Main views
- `urls.py`: URL routes
- `templates/video_editing/`: Editor UI templates
- `apps.py`: App config
- `tests.py`: Tests

**How it Works**:
1. User selects a video to edit
2. Creates a `VideoEditSession`
3. Adds edit actions (trim, split, mute, etc.) which are stored as `VideoEditAction` records
4. UI previews the edits client-side
5. When user clicks "Save & Process", the backend executes all actions using FFmpeg
6. Original file is never modified; edits are applied to a copy
7. Edited video is saved and available for download

**Tech Used**: FFmpeg, Django, subprocess

---

### 20. `videos/` - Video Management & Uploads
**Purpose**: Store, manage, and serve video recordings and uploaded content

**Key Files & Directories**:
- `models.py`: Video model
- `views.py`: Video views
- `urls.py`: URL routes
- `tasks.py`: Celery tasks for video processing
- `apps.py`: App config
- `admin.py`: Admin config
- `tests.py`: Tests

**Tech Used**: Django, file system storage

---

### Root Files
- `manage.py`: Django management script
- `requirements.txt`: Python dependencies
- `start_app.ps1`: Windows startup script
- `Dockerfile`: Docker container config for main app
- `docker-compose.yml`: Docker Compose config for full stack
- `.gitignore`: Git ignore rules
- `.dockerignore`: Docker ignore rules
- `README.md`: This file!

---

## 🚀 Quick Start

### Prerequisites
1. Python 3.14+
2. Redis server (running on port 6379)
3. FFmpeg (installed and in your PATH)
4. LiveKit server (optional for development, but required for meetings)

### Installation Steps

1. **Clone the repository**
2. **Set up environment variables**
   - Copy `config/.env.example` to `.env` in the root
   - Fill in all required secrets (especially `SECRET_KEY`, `LIVEKIT_*`, and `FACE_ENCRYPTION_KEY`)
3. **Install Python dependencies**
   ```powershell
   pip install -r requirements.txt
   ```
4. **Set up database**
   ```powershell
   python manage.py migrate
   ```
5. **Create a superuser (optional but recommended)**
   ```powershell
   python manage.py createsuperuser
   ```
6. **Start the application**
   - **Windows**: Run `start_app.ps1`
   - **Linux**: Run `./scripts/deploy.sh`
   - Or manually:
     ```powershell
     # Start Redis (if not already running)
     # Start LiveKit (optional for dev)
     # Start Django
     python manage.py runserver
     # Start Daphne (ASGI) for WebSockets
     daphne school_project.asgi:application
     # Start Celery worker
     celery -A school_project worker --loglevel=info
     ```

### Default Ports
- Main Django app: `8000`
- Daphne ASGI: `8001`
- LiveKit Proxy: `8002`
- Camera Service: `8003`
- LiveKit SFU: `7880`

---

## 🔧 Environment Variables

The app requires these environment variables (set in `.env`):
- `SECRET_KEY`: Django's secret key (generate one with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- `DEBUG`: `True` for development, `False` for production
- `LIVEKIT_URL`: LiveKit WebSocket URL (for clients)
- `LIVEKIT_INTERNAL_URL`: LiveKit internal WebSocket URL
- `LIVEKIT_INTERNAL_HTTP_URL`: LiveKit internal HTTP URL
- `LIVEKIT_API_KEY`: LiveKit API key
- `LIVEKIT_API_SECRET`: LiveKit API secret (must be 32+ characters)
- `REDIS_URL`: Redis URL for Celery and Channels (e.g., `redis://localhost:6379/0`)
- `FACE_ENCRYPTION_KEY`: Fernet key for biometrics (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- `FACE_MATCH_THRESHOLD`: Face similarity threshold (0-1, lower = stricter)
- `FACE_PRESENCE_DURATION`: Seconds of verified presence needed to mark attendance

---

---

<div align="center">
  <p>Built with ❤️ for better classrooms!</p>
</div>
