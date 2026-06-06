# EduMi2: Real-Time AI Monitoring & Academic Interaction Platform

<div align="center">
  <p>The Complete System for Modern Academic Interaction, AI Attendance, and Video Management.</p>
</div>

---

## 🎯 Core Application Features

This system integrates real-time communications, AI-based monitoring, and robust access controls into a single platform. Click on any feature below to expand its details.

<details>
<summary><b>🏫 Virtual Meeting Classroom Functionality</b></summary>

### Overview
Provides real-time, low-latency audio/video conferencing utilizing **LiveKit** WebRTC infrastructure. 

### Workflows
- **Creation**: Teachers generate classrooms with distinct schedules and metadata.
- **In-Meeting Controls**: Global mute, camera disable, screen sharing, and participant grid views.
- **Backend Sync**: LiveKit webhooks sync participant states (join, leave, speaking) back to the Django backend in real-time.
</details>

<details>
<summary><b>🚪 Classroom Joining Workflows</b></summary>

### Overview
A secure, multi-step process ensuring only authorized participants enter active sessions.

### Workflows
1. **Pre-Join Lobby**: Users configure and test their hardware (camera/mic).
2. **Token Generation**: Django securely requests a JWT from the LiveKit proxy.
3. **Connection**: The client connects to the WebRTC server using the generated JWT.
4. **Validation**: The system verifies the user's role and schedule against the active meeting.
</details>

<details>
<summary><b>🔐 Role-Based Access Control (RBAC) System</b></summary>

### Overview
A robust permissions architecture managed within the `accounts` module.

### Capabilities
- **Strict Separation**: Distinct dashboards and API endpoints for `Admin`, `Teacher`, and `Student`.
- **Inheritance**: Admins possess global override capabilities for classrooms and attendance.
- **Middleware Protections**: Views enforce role checks before yielding sensitive data or media files.
</details>

<details>
<summary><b>📊 Automated Attendance Tracking</b></summary>

### Overview
Tracks student presence seamlessly without manual roll calls.

### Workflows
- **Session Tracking**: Records exact timestamps for join/leave events.
- **Duration Calculation**: Aggregates total active seconds per participant.
- **Status Assignment**: Automatically categorizes as "Present", "Late", or "Absent" based on schedule enforcement rules.
</details>

<details>
<summary><b>🤖 Facial Recognition-Powered Attendance Verification</b></summary>

### Overview
Uses OpenCV and `face_recognition` to authenticate student presence via video streams.

### Workflows
1. **Enrollment**: Students upload reference photos (`face_photos/`), which are encrypted and stored.
2. **Stream Processing**: The `camera_service` ingests RTSP/WebRTC streams.
3. **Verification**: Frame intervals are analyzed against reference encodings.
4. **Attendance Logging**: Confirmed matches update the central database asynchronously via Celery.
</details>

<details>
<summary><b>📡 Live Streaming Capabilities</b></summary>

### Overview
Handles external hardware and software camera streams.

### Workflows
- **RTSP Ingestion**: Pulls feeds from hardware IP cameras.
- **Mobile Integration**: Supports DroidCam / IP Webcam feeds via `mobile_cameras`.
- **Proxying**: Re-streams RTSP over WebRTC or HLS to client browsers for low-latency viewing.
</details>

<details>
<summary><b>☁️ Cloud-Based Video Recording</b></summary>

### Overview
Captures ongoing virtual classes and live streams directly to the server.

### Workflows
- **Chunking**: Large recordings are automatically split into manageable chunks to prevent memory bloat.
- **Storage**: Saved securely within the central `database/media/recordings/` directory.
- **Status Tracking**: Database tracks recording states (`Processing`, `Completed`, `Failed`).
</details>

<details>
<summary><b>📤 Post-Recording Video Upload Workflows</b></summary>

### Overview
Allows educators to upload external supplementary materials.

### Workflows
- **Chunked Uploads**: UI supports resumable chunked uploads for large video files.
- **Validation**: Strict MIME-type and size validations.
- **Transcoding**: Automatically queues asynchronous FFmpeg tasks to standardize formats for web playback.
</details>

<details>
<summary><b>✂️ In-Platform Video Editing Tools</b></summary>

### Overview
Provides a non-destructive timeline editor for recorded and uploaded videos.

### Capabilities
- **Operations**: Trim, split, mute sections, rotate, add text overlays, and inject audio tracks.
- **Processing**: The `video_editing` app translates UI actions into exact FFmpeg commands.
- **Storage**: Outputs rendered videos to `database/media/videos/` without destroying the original source.
</details>

---

## 🏗️ Technical Stack Specifications

- **Core Backend**: Django 4.2+, Python 3.14+
- **Asynchronous Engine**: Daphne (ASGI), Django Channels
- **Real-Time Media**: LiveKit SFU (WebRTC)
- **Computer Vision**: OpenCV, `face_recognition`, `dlib`
- **Video Processing**: FFmpeg (via `subprocess` wrappers)
- **Database**: SQLite (Centralized in `database/db.sqlite3`)
- **Task Queue**: Celery + Redis

---

## 🚀 Deployment Procedures

### Prerequisites
1. Redis server running on port 6379.
2. FFmpeg installed and accessible in the system `PATH`.
3. Python 3.14+ installed.

### Execution
1. Clone the repository.
2. Ensure `database/db/sqlite/db.sqlite3` is in place.
3. Run `pip install -r requirements.txt`.
4. Run `python manage.py migrate`.
5. Execute `start_app.ps1` (Windows) or `deploy.sh` (Linux).

---

## ⚙️ Environment Variable Requirements

The application relies on a root `.env` file. Critical variables include:
- `SECRET_KEY`: Django cryptographic key.
- `DEBUG`: `True` or `False`.
- `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`: WebRTC configuration.
- `REDIS_URL`: Broker for Channels and Celery.
- `FACE_ENCRYPTION_KEY`: Fernet key for securing biometric templates.

---

## 🛡️ Security Protocols

- **Media Isolation**: All user-generated media resides strictly in `database/media/`. Access is governed by Django views, not served raw.
- **Biometric Encryption**: Reference face encodings are encrypted at rest using Fernet symmetric encryption.
- **WebSocket Auth**: Token-based authentication required for all ASGI connections.

---

## 🔧 Troubleshooting Guidelines

- **Database Locked Errors**: Ensure no overlapping processes are locking `database/db/sqlite/db.sqlite3`. Django's timeout is set to 30s.
- **LiveKit Connection Failures**: Verify `LIVEKIT_URL` in `.env`. Ensure the LiveKit service is running on port 7880.
- **Face Recognition Failures**: Ensure the image resolution is high enough and lighting is clear. Adjust `FACE_MATCH_THRESHOLD` in `.env` if false positives occur.
- **Video Processing Hangs**: Verify FFmpeg installation by running `ffmpeg -version` in the terminal.
