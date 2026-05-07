# 🎓 Edumi2: High-Level System Architecture & Engineering Documentation

This document provides a deep, theoretical dive into the architecture and internal mechanics of the **Edumi2** platform. It is designed to guide senior developers through the "Why" and "How" of the system's design.

---

## 1. Project Overview
### The Problem
Traditional virtual classrooms often suffer from "passive attendance"—students join a call but are not physically or mentally present. Tracking attendance manually in large online sessions is time-consuming and prone to fraud. Additionally, monitoring student engagement (whether they are focused or distracted) is nearly impossible for a teacher focused on delivering a lecture.

### The Solution
**Edumi2** is an AI-powered educational command center that bridges the gap between high-performance video conferencing and academic integrity. It automates attendance using **Biometric Face-ID** and provides real-time **Engagement Analytics** (attention tracking, emotion detection) during live sessions.

---

## 2. System Architecture: Comprehensive Component Mapping

Edumi2 follows a **4-Layer Decoupled Model** designed to isolate heavy AI/Video processing from the core application logic.

![System Architecture Diagram](architecture_digram/v4%20(1).png)

### 📐 Layer 1: Presentation & Clients (The Edge)
This is the interface layer where users and hardware interact with the system.
*   **Web Browsers (Students & Teachers)**: The primary dashboard for attending classes. It handles real-time attendance via WebSockets, chat collaboration, and viewing analytical reports.
*   **Mobile Devices**: Used as secondary "IP Cameras" (via DroidCam/IP Webcam). Note: There is no native mobile app for meetings; they join via the mobile browser.
*   **IP / Physical Cameras**: Professional hardware used for classroom monitoring and automated head counting/surveillance.

### 🛡️ Layer 2: Gateway & Security (The Entry Point)
Manages traffic ingress, routing, and protocol enforcement.
*   **Public Ingress (Ngrok / Cloud Gateway)**: Provides the secure tunnel for local development or cloud access. It handles **TLS Termination**, secure tunneling, and initial DDoS protection.
*   **Nginx Reverse Proxy**: The system's primary router.
    *   **Static & Media Serving**: Efficiently serves CSS, JS, and profile images.
    *   **Sticky Sessions (`ip_hash`)**: Essential for WebSockets to ensure users stay connected to the same worker instance.
    *   **Security Headers**: Enforces CORS and CSP policies to prevent cross-site scripting.
*   **Load Balancer (HAProxy / Cloud LB)**: Distributes HTTP (Least Connections) and WebSocket (IP Hash) traffic across the application core.

### 🧠 Layer 3: Application & Processing Core (The Brain)
Divided into synchronous handlers and asynchronous specialist workers.
*   **A. Request Handlers (Synchronous)**:
    *   **Daphne (ASGI WebSocket Server)**: Manages persistent WebSocket endpoints, auth/permissions, and connection state.
    *   **Main Application (Django / API Server)**: Handles business logic, authentication, and meeting governance.
    *   **LiveKit Proxy Consumer**: A binary bridge that forwards Protobuf packets between clients and the LiveKit SFU.
*   **B. Specialist Workers (Async / Sync)**:
    *   **Consumer for Live HLS Viewing**: Handles RTSP/HTTP ingest using FFmpeg, converting it to HLS with an **Idle Shutdown** logic to save CPU.
    *   **Consumer for Analytical Processing**: The AI engine. Performs face detection, 128-d embedding extraction, anti-spoofing (liveness), and similarity matching.
    *   **Celery Worker**: Manages report generation, heavy analytics, and periodic cleanup jobs.
*   **Redis (Broker / Channel Layer)**: Bridging Layer 3 and 4.
    *   > [!NOTE]
    *   **Redis** appears in both Layer 3 and Layer 4 because it serves two distinct architectural purposes:
    *   **In Layer 3**, it acts as the **Active Channel Layer** (Signaling Bus) for moving real-time messages between Daphne and Django workers.
    *   **In Layer 4**, it acts as the **Stateful Store** for caching session tokens, rate limiting data, and the Celery task queue.

### 💾 Layer 4: Data Persistence & Messaging (The Memory)
The foundation where all system state and permanent records are stored.
*   **PostgreSQL / SQLite (Database)**: Stores user profiles, classroom data, attendance records, and **AES-256 encrypted** face embeddings.
*   **Redis (Cache & Messaging)**: Stores session tokens, room states, and acts as the broker for the task queue.

---

## 3. Full Project File Structure & Functional Mapping

Below is the complete engineering structure of Edumi2, mapped to the architectural components.

```text
Edumi2/
├── accounts/               # Identity & User Management
│   ├── consumers.py        # Real-time notification socket handlers
│   ├── models.py           # UserProfile, Student/Teacher definitions
│   ├── messaging_models.py # Chat & Private Messaging database schemas
│   ├── services.py         # Business logic for user registration & auth
│   └── views.py            # Profile management & dashboard logic
│
├── attendance/             # AI & Biometric Core
│   ├── face_service.py     # AI Pipeline: Face detection & comparison logic
│   ├── engagement_service.py # Engagement AI: EAR & Head-pose analysis
│   ├── encryption_service.py # Security: AES-256 Fernet implementation
│   ├── face_tracking_consumer.py # WebSocket: Receives frames, returns AI results
│   ├── models.py           # Encrypted Face Embeddings & Attendance Logs
│   └── tasks.py            # Celery: Batch processing of attendance reports
│
├── camera_service/         # Video Microservice (Micro-Django)
│   ├── camera_api/
│   │   ├── hls_proxy.py    # FFmpeg management & Idle Shutdown logic
│   │   └── views.py        # API endpoints for requesting video streams
│   └── manage.py           # Independent entry point for the microservice
│
├── meetings/               # Video Conferencing Logic
│   ├── livekit_proxy.py    # Signaling bridge for WebRTC media server
│   ├── consumers.py        # Master Socket: Chat, Hand-raise, Host control
│   ├── models.py           # Classroom, Meeting, and Participant schemas
│   └── views.py            # Logic for creating/joining rooms & governance
│
├── school_project/         # The Central Hub (Settings & Routing)
│   ├── asgi.py             # ASGI Routing (The entry point for Daphne)
│   ├── settings.py         # Global configuration & environment switching
│   └── urls.py             # Root URL routing table
│
├── static/                 # Frontend Assets
│   └── js/
│       ├── webrtc_handler.js # Logic for browser-side video/audio
│       ├── ai_capture.js     # Logic for capturing webcam frames for the AI
│       └── signaling.js      # Logic for WebSocket communication
│
├── templates/              # UI Layouts
│   ├── base.html           # Main dashboard wrapper
│   ├── meetings/           # Classroom & Video call templates
│   └── attendance/         # AI Analytics & Report templates
│
├── start_all.ps1           # Orchestration Script
├── docker-compose.yml      # Container Orchestration
└── requirements.txt        # System manifest
```

---

## 4. Engineering Theory & Performance

### Why Remuxing vs Transcoding?
In `camera_service`, we use `-c:v copy`.
*   **Theoretical**: Transcoding (re-encoding) requires heavy CPU for every frame. Remuxing (copying the stream into a new container) is almost "free". This allows a single server to handle 50+ camera streams instead of just 5.

### Biometric Encryption Strategy
Student biometrics are sensitive. We do not save raw photos. We save 128-d vectors. By encrypting these with **AES-256**, we ensure that even if the database is leaked, a student's facial identity remains protected.

---

## 5. Debugging and Troubleshooting
- **Logs**: Django logs to console. Check for "Handshake Errors" in Daphne logs.
- **`ws_debug.log`**: Records every signaling message. Essential for debugging "Why can't this student see the teacher?"
- **Common Issue**: "Camera not starting" — Usually means FFmpeg is missing from the system PATH.

---

## 6. Major Modules and Classes

This section provides a theoretical breakdown of the core software components and how they interact.

### 🧠 `attendance.face_service.FaceService`
*   **Role**: The central AI coordinator.
*   **Purpose**: It abstracts the complexity of OpenCV and Dlib. It handles the loading of models, face detection, and the "matching" logic that compares a live frame against a saved 128-d vector.
*   **Interaction**: It is called by the `FaceTrackingConsumer` every time a new video frame arrives.

### 🔐 `attendance.encryption_service.FaceEncryptionService`
*   **Role**: The Security Layer.
*   **Purpose**: Implements **Fernet (AES-256)** encryption for biometric data. It ensures that the 128 floating-point numbers representing a student's face are never stored in plain text.
*   **Interaction**: Sits between the `FaceService` and the `PostgreSQL` database. It encrypts data on registration and decrypts it on verification.

### 📡 `attendance.face_tracking_consumer.FaceTrackingConsumer`
*   **Role**: The Real-Time Frame Processor.
*   **Purpose**: A WebSocket consumer that receives binary image data from the student's browser. It coordinates the "Liveness" check and the recognition process.
*   **Interaction**: Communicates with the client's browser for frame intake and broadcasts the "Present/Absent" status to the teacher via the **Redis Channel Layer**.

### 📽️ `camera_service.camera_api.hls_proxy.HLSStreamer`
*   **Role**: The Video Micro-Processor.
*   **Purpose**: Manages individual FFmpeg subprocesses. It is responsible for the "Remuxing" logic that converts RTSP into HLS without hitting the CPU hard.
*   **Interaction**: Triggered by the dashboard when a teacher opens a camera feed. It automatically shuts down after 30 seconds of inactivity to reclaim system memory.

---

## 7. Key Files and Their Responsibilities

| File Path | Responsibility | Why it exists? |
| :--- | :--- | :--- |
| `attendance/face_service.py` | AI matching logic | To isolate biometric algorithms from the web framework. |
| `meetings/livekit_proxy.py` | Secure media signaling | To prevent direct browser access to the LiveKit server secrets. |
| `school_project/asgi.py` | Async routing hub | To direct HTTP traffic to Django and WebSocket traffic to Channels. |
| `static/js/ai_capture.js` | Browser-side frame capture | To optimize bandwidth by only sending frames when a face is detected locally. |
| `attendance/tasks.py` | Background report generation | To prevent the web server from freezing during heavy PDF creation. |

---

## 8. Glossary: Project-Specific Terms

*   **SFU (Selective Forwarding Unit)**: A modern WebRTC server (LiveKit) that routes video packets efficiently instead of making users connect directly to each other.
*   **128-d Vector**: A mathematical "fingerprint" of a face. It is a list of 128 numbers that represent unique facial features.
*   **Zero-CPU Remuxing**: The technique of changing a video's "envelope" (e.g., from RTSP to HLS) without re-encoding the actual video data.
*   **Sticky Sessions**: A load-balancing technique where a student is "stuck" to one specific server instance so their WebSocket connection doesn't drop.
*   **Anti-Spoofing (Liveness)**: The AI logic that checks if the camera is looking at a real 3D face or just a flat photo.
*   **Fernet (AES-256)**: The specific encryption standard used to lock student face data.
*   **Proactive Idle Shutdown**: The logic that kills unused video streams to prevent the server from running out of RAM/CPU.

---
---

## 9. Detailed System Workflows

This section outlines the step-by-step logic for the system's most critical operations.

### 🔄 Workflow: Joining a Meeting (The Handshake)
1.  **Request**: Student clicks "Join" in the Classroom dashboard.
2.  **Auth Check**: Django verifies `ClassroomMembership` status.
3.  **Token Generation**:
    *   Backend contacts **LiveKit Server** via `livekit_proxy.py`.
    *   Generates a JWT signed with `LIVEKIT_API_SECRET`.
    *   Returns the Token and the Proxy WebSocket URL to the browser.
4.  **Media Link**: Browser establishes a WebRTC connection via the **Nginx/Daphne Proxy**.

### 📸 Workflow: Automated Attendance (The AI Loop)
1.  **Trigger**: Every 15 seconds (configurable via `AttendanceSettings`), the student's browser captures a webcam frame.
2.  **Ingest**: The frame is sent as binary data over a dedicated **WebSocket** to `FaceTrackingConsumer`.
3.  **Recognition**:
    *   `FaceTrackingConsumer` calls `FaceService`.
    *   `FaceService` fetches the **encrypted** 128-d vector from `StudentFaceProfile`.
    *   AI performs detection, liveness check, and similarity matching.
4.  **Outcome**:
    *   **Success**: `AttendanceRecord` is updated (e.g., marked "Present").
    *   **Feedback**: A real-time notification is sent back to the student's "Attendance Badge" and the teacher's "Participants List".

---

## 10. Comprehensive Database Schema

| Table Name | Primary Responsibility | Key Fields |
| :--- | :--- | :--- |
| `User` | Identity | `username`, `email`, `is_staff` |
| `Classroom` | Academic Container | `class_code`, `teacher_id`, `password` |
| `Meeting` | Active Session | `meeting_code`, `status` (live/ended), `sleep_status` |
| `MeetingParticipant` | Session State | `user_id`, `joined_at`, `audio_permitted` |
| `StudentFaceProfile` | Biometric Vault | `face_embedding_encrypted` (Binary), `checksum` |
| `AttendanceRecord` | Academic Result | `status` (Present/Late/Absent), `face_match_confidence` |
| `EngagementReport` | Post-session Analytics | `class_engagement_score`, `student_data` (JSON) |

---

## 11. Environment Configuration Reference

The system relies on a `.env` file for behavior steering.

*   **`DEBUG`**: Set to `False` in production to enable Nginx-level security and static file compression.
*   **`REDIS_URL`**: Points to the Redis instance. Crucial for **WebSocket signaling** (Layer 3) and **Celery Tasks** (Layer 4).
*   **`LIVEKIT_API_SECRET`**: Must be a 32-character string. Used to sign meeting tokens.
*   **`FACE_MATCH_THRESHOLD`**: Defaults to `0.55`. Lowering this makes recognition "easier" but increases the risk of false positives.
*   **`FACE_PRESENCE_DURATION`**: Number of seconds a student must be "visible" to the AI before being officially marked as **Present**.
*   **`CAMERA_SERVICE_URL`**: The endpoint for the HLS remuxing microservice.

---

## 12. Internal API & Signaling Reference

### WebSocket Endpoints
*   `/ws/meeting/<code_id>/`: The signaling hub for chat, hand-raising, and teacher controls (mute/kick).
*   `/ws/attendance/tracking/`: The high-frequency AI pipe for image frame intake.

### Critical API Endpoints
*   `GET /meetings/token/<code_id>/`: Fetches the LiveKit JWT.
*   `POST /meetings/kick/<id>/`: Teacher-only endpoint to ban a student from a live session.
*   `GET /camera-service/stream/<id>/`: Requests an HLS mount point for a specific camera feed.

---

## 13. Frontend State & UI Logic Deep-Dive

Although the frontend uses **Vanilla JavaScript**, it follows a **State-Driven Architecture** similar to React:

*   **Global `room` Object**: The source of truth for the meeting. All UI updates (mute icons, participant lists) are triggered by listeners on `RoomEvent`.
*   **Media State Machine**: Managed in `meeting_room.html`. It tracks `isMicOn`, `isCameraOn`, and `isScreenSharing` to ensure the UI icons and the LiveKit tracks stay in sync.
*   **Overlay Logic**: Uses a high-performance `<canvas>` overlay for AI emotion badges. This prevents unnecessary DOM reflows when the AI detects a new emotion every few seconds.

---

## 14. Onboarding: The First 30 Minutes

If you are new to Edumi2, follow this "First 30 Minutes" guide:
1.  **Clone & Start**: Run `./start_all.ps1` and ensure 3 separate terminal windows open (Daphne, Redis, Camera-Service).
2.  **Create a Classroom**: Log in as a teacher and create your first "Subject".
3.  **The AI Check**: Try to register your face. If it fails, check your `FFMPEG` and `DLIB` installations first—these are the most common bottlenecks.
4.  **The "Ghost Student" Test**: Open a Private/Incognito window and join your own class as a student to see the teacher-student interaction in real-time.

---

## 15. Contribution Best Practices

*   **Async First**: Use `async/await` for all WebSocket logic. Never block the main thread with synchronous `time.sleep()`.
*   **Encryption**: Never log decrypted face vectors to the console.
*   **Resource Management**: Always check the `Idle Shutdown` logic when adding new camera features to prevent server RAM exhaustion.

---
