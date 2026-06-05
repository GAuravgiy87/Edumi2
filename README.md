<div align="center">

<img src="static/logo.svg" alt="EduMi2 Logo" width="380" />

<br/>

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=26&duration=2800&pause=2000&color=6366F1&center=true&vCenter=true&width=940&lines=Edumi2+%E2%80%94+Real-Time+AI+Monitoring+%26+Meetings;Academic+Integrity+at+Scale;One+Complete+Source+of+Truth" alt="Typing SVG" />

<br/>

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![LiveKit](https://img.shields.io/badge/LiveKit-WebRTC-FF6B6B?style=for-the-badge&logo=webrtc&logoColor=white)](https://livekit.io)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![Celery](https://img.shields.io/badge/Celery-5.3-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![OpenCV](https://img.shields.io/badge/OpenCV-AI-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)

<br/>

> **Edumi2** is a professional-grade, AI-powered academic platform that fuses high-performance WebRTC video conferencing with real-time face recognition, attention tracking, and automated attendance — all in one unified system.

</div>

---

## 📑 Table of Contents

- [👥 Authors](#-authors)

- [✨ Features](#-features)
- [🏗️ System Architecture](#️-system-architecture)
- [🛠️ Technology Stack](#️-technology-stack)
- [📦 Prerequisites](#-prerequisites)
- [⚡ Quick Start (Windows)](#-quick-start-windows)
- [🔧 Manual Setup — Step by Step](#-manual-setup--step-by-step)
- [🐳 Docker Deployment](#-docker-deployment)
- [⚙️ Environment Variables](#️-environment-variables)
- [🗂️ Project Structure](#️-project-structure)
- [🧩 Module Reference](#-module-reference)
- [📡 Real-Time Signaling](#-real-time-signaling)
- [🔐 Security](#-security)
- [🔧 Troubleshooting](#-troubleshooting)
- [🤝 Contributing](#-contributing)

---

## ✨ Features

### 🎥 Professional Video Meetings (LiveKit SFU)
| Feature | Detail |
|---|---|
| HD WebRTC Streaming | Low-latency simulcast video/audio via LiveKit SFU |
| Teacher Console | Centralized room control — kick/ban students, mute all |
| Granular Permissions | Real-time server-side A/V/Screen share control per participant |
| Interactive Tools | Screen sharing, emoji reactions, real-time chat with file attachments |

### 🧠 AI Attendance & Monitoring
| Feature | Detail |
|---|---|
| Face ID Verification | Mandatory biometric enrollment before joining any live session |
| Attention Tracking | AI-driven focus scoring based on head pose estimation |
| Automated Attendance | Passive duration-based logging with encrypted biometric storage |
| IP Camera Support | RTSP / HTTP classroom camera feeds processed via dedicated microservice |

### ⚡ Real-Time Auto-Update System
| Feature | Detail |
|---|---|
| Global Signal Bridge | WebSocket push for messages, meeting events, kicks — zero reloads |
| No-Reload Dashboard | AJAX + WebSocket driven dynamic updates |
| Toast Notifications | Non-intrusive system-wide event alerts |
| Kick & Ban Flow | 1-hour enforced ban with database-backed expiry |

---

## 🏗️ System Architecture

Edumi2 follows a **4-Layer Decoupled Architecture** ensuring AI processing never degrades video quality.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1 · PRESENTATION — Clients & Edge Devices                            │
│  [ Web Browser  ]  ←──(WSS / WebRTC / HTTPS)──→  [ Teacher / Student ]     │
│  [ IP Cameras   ]  ←──(RTSP / HTTP)────────────→  [ Classroom Hardware ]   │
└──────────────────────────┬────────────────────────────┬─────────────────────┘
                           │                            │
                           ▼                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2 · GATEWAY — Security & Traffic Management                          │
│  [ Ngrok Tunnel ]  →  Secure HTTPS/WSS public entry point                   │
│  [ Nginx Proxy  ]  →  Static delivery, WebSocket upgrade, media serving     │
└──────────────────────────┬────────────────────────────┬─────────────────────┘
                           │                            │
                           ▼                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3 · APPLICATION — Services & AI Logic                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   Main App      │  │  Camera Service │  │  LiveKit SFU    │             │
│  │ (Django / ASGI) │  │  (OpenCV / AI)  │  │  (WebRTC Engine)│             │
│  │ · Auth & RBAC   │  │ · Face Recog.   │  │ · Video Routing │             │
│  │ · WebSocket Hub │  │ · Attn. Tracking│  │ · Simulcasting  │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           └───────────────────┬┴───────────────────┘                       │
│                               ▼                                             │
│                    ┌─────────────────────┐                                  │
│                    │   Celery Worker     │  ← Analytics & Background Tasks  │
│                    └─────────────────────┘                                  │
└──────────────────────────┬────────────────────────────┬─────────────────────┘
                           │                            │
                           ▼                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4 · DATA — Persistence & Infrastructure                              │
│  [ SQLite / PostgreSQL ]  →  Users, Rooms, Meetings, Attendance Logs        │
│  [ Redis               ]  →  Channel Layers (WebSocket) & Celery Broker     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

| Category | Technology | Version | Role |
|---|---|---|---|
| **Language** | Python | 3.11 | Core runtime |
| **Framework** | Django | 4.2.9 | Web framework, ORM, Auth, RBAC |
| **ASGI Server** | Daphne | 4.0.0 | ASGI server for HTTP + WebSockets |
| **WebSockets** | Django Channels | 4.0.0 | Real-time duplex communication |
| **Task Queue** | Celery | 5.3.6 | Background jobs & analytics |
| **Media Engine** | LiveKit SFU | v1.5.2 | WebRTC simulcast video/audio |
| **AI / ML** | OpenCV | 4.13 | Face recognition & attention scoring |
| **Cache / Broker** | Redis | 7 | Channel layers & Celery broker |
| **Database** | SQLite / PostgreSQL | — | Data persistence |
| **Proxy** | Nginx | latest | Static files, reverse proxy |
| **Container** | Docker Compose | — | Multi-service orchestration |
| **Frontend** | Vanilla JS / CSS3 / HTML5 | — | Responsive academic UI |

---

## 📦 Prerequisites

Ensure the following are installed before proceeding:

| Requirement | Minimum Version | Notes |
|---|---|---|
| Python | 3.9+ | 3.11 recommended |
| Redis | 7.x | Must be running before the app starts |
| Git | any | For cloning the repo |
| Docker & Docker Compose | 24+ | Only for containerized deployment |
| LiveKit Server Binary | v1.5.2 | Included in `livekit-bin/` for Windows local dev |

> **Windows users:** Redis can be installed via `winget install Redis.Redis` or by using the pre-built Windows binary.

---

## ⚡ Quick Start (Windows)

The fastest way to run the full system locally on Windows:

```powershell
# 1. Clone the repository
git clone https://github.com/GAuravgiy87/Edumi2.git
cd Edumi2

# 2. Create and activate the virtual environment
python -m venv .venv
.venv\Scripts\Activate

# 3. Install all dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Install AI Face Recognition Models (Required)
pip install git+https://github.com/ageitgey/face_recognition_models.git

# 5. Copy the environment config and fill in your values
copy .env.example .env

# 6. Apply database migrations
python manage.py migrate

# 7. Launch all services with the master script
#    Right-click → "Run with PowerShell" OR:
powershell -ExecutionPolicy Bypass -File .\start_app.ps1
```

Then open **http://localhost:8000** in your browser.

| Credential | Value |
|---|---|
| Default Admin Username | `EdumiAdmin` |
| Default Admin Password | `Gaurav@0000` |
| Admin Panel | http://localhost:8000/admin/ |
| Camera Service | http://localhost:8001 |

---

## 🔧 Manual Setup — Step by Step

Follow these steps if you need fine-grained control over each service.

### Step 1 — Clone & Virtual Environment

```bash
git clone https://github.com/GAuravgiy87/Edumi2.git
cd Edumi2

# Windows
python -m venv .venv
.venv\Scripts\Activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### Step 2 — Install Dependencies

```bash
# Main application
pip install --upgrade pip
pip install -r requirements.txt

# Install AI Face Recognition Models (Required for attendance & tracking)
pip install git+https://github.com/ageitgey/face_recognition_models.git

# Camera microservice (separate Django sub-project)
pip install -r camera_service/requirements.txt
```

### Step 3 — Configure Environment

```bash
# Copy the example and edit values
copy .env.example .env   # Windows
cp .env.example .env     # macOS / Linux
```

Edit `.env` — see [Environment Variables](#️-environment-variables) for all options.

### Step 4 — Database Migration

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 5 — Create Superuser (First Run Only)

```bash
python manage.py createsuperuser
# OR use the bundled setup script:
python setup_admin.py
```

### Step 6 — Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### Step 7 — Start Redis

```bash
# Windows (if Redis is installed via winget/binary)
redis-server

# Docker (quick option)
docker run -d -p 6379:6379 redis:7-alpine
```

### Step 8 — Start LiveKit SFU

```bash
# Windows — using the bundled binary
.\livekit-bin\livekit-server.exe --config livekit.yaml

# Docker
docker run --rm -p 7880:7880 -p 7881:7881 -p 50000-50200:50000-50200/udp \
  -v $(pwd)/livekit.yaml:/etc/livekit/config.yaml \
  livekit/livekit-server:v1.5.2 --config /etc/livekit/config.yaml
```

### Step 9 — Start Celery Worker

```bash
# Windows (solo pool required)
celery -A school_project worker -l info -P solo

# macOS / Linux
celery -A school_project worker -l info
```

### Step 10 — Start Camera Microservice

```bash
python camera_service/manage.py runserver 0.0.0.0:8001
```

### Step 11 — Start Main Application

```bash
# Development (Django dev server)
python manage.py runserver 0.0.0.0:8000

# Production (Daphne ASGI — required for WebSockets)
daphne -b 0.0.0.0 -p 8000 school_project.asgi:application
```

---

## 🐳 Docker Deployment

For a fully containerized production deployment (PostgreSQL + Redis + LiveKit + Nginx):

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with production values (strong SECRET_KEY, LIVEKIT credentials, etc.)

# 2. Build and start all services
docker compose up --build -d

# 3. Verify all containers are healthy
docker compose ps

# 4. View live logs
docker compose logs -f web
```

**Services launched by Docker Compose:**

| Service | Port | Description |
|---|---|---|
| `web` | 8000 | Django/Daphne ASGI main application |
| `worker` | — | Celery background task worker |
| `camera_service` | 8001 | AI camera processing microservice |
| `livekit` | 7880, 7881 | LiveKit SFU WebRTC media engine |
| `redis` | 6379 (internal) | Channel layer & Celery broker |
| `db` | 5432 (internal) | PostgreSQL 15 database |
| `nginx` | 80 | Reverse proxy + static file serving |

To stop all services:

```bash
docker compose down
```

To reset volumes (⚠️ destroys all data):

```bash
docker compose down -v
```

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Core Django
SECRET_KEY=your-secret-key-here            # Min 50 chars in production
DEBUG=True                                  # Set to False in production
ALLOWED_HOSTS=localhost,127.0.0.1           # Add your server IP/domain

# Redis
REDIS_URL=redis://localhost:6379/0

# LiveKit SFU
LIVEKIT_URL=ws://localhost:7880             # Use wss:// in production
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=devsecret               # Min 32 chars in production

# Database (Docker only)
DATABASE_URL=postgres://edumi:edumi@db:5432/edumi

# CSRF (Docker / Production)
CSRF_TRUSTED_ORIGINS=https://yourdomain.com
```

> **Production Note:** Always use a strong `SECRET_KEY`, set `DEBUG=False`, and use `wss://` for LiveKit in any internet-facing deployment.

---

## 🗂️ Project Structure

```
Edumi2/
├── accounts/               # Auth, user profiles, dashboards, WebSocket consumers
│   ├── models.py           # UserProfile, FaceID, Notifications
│   ├── consumers.py        # NotificationWS — global signaling hub
│   ├── views.py            # Teacher & Student dashboards
│   └── notification_utils.py
├── meetings/               # LiveKit proxy, room management, host controls
│   ├── models.py           # Meeting, MeetingParticipant, KickedParticipant
│   └── views.py            # Token generation, kick/ban logic
├── attendance/             # Face recognition, attention tracking, logs
│   └── services.py         # Biometric matching & attendance aggregation
├── camera_service/         # Standalone RTSP/HTTP camera processing microservice
├── cameras/                # IP camera model & management
├── mobile_cameras/         # Mobile camera stream support
├── pages/                  # Static/general pages
├── school_project/         # Django project config (settings, ASGI, routing)
│   ├── settings.py
│   ├── asgi.py
│   └── urls.py
├── templates/              # Jinja2 / Django HTML templates
├── static/                 # CSS, JS, images, logo
├── staticfiles/            # Collected static (auto-generated)
├── nginx/                  # Nginx reverse proxy configuration
├── livekit-bin/            # LiveKit server binary (Windows local dev)
├── livekit.yaml            # LiveKit server configuration
├── docker-compose.yml      # Multi-service container orchestration
├── Dockerfile              # Main app container build
├── requirements.txt        # Python dependencies
├── start_app.ps1           # Windows one-click startup script
├── .env.example            # Environment variable template
└── manage.py
```

---

## 🧩 Module Reference

### `accounts` — Identity & Notification Hub
- **UserProfile**: Extends Django's User with role (Teacher/Student), Face-ID biometrics, and profile data.
- **NotificationWS** (`consumers.py`): Global WebSocket consumer that routes real-time events (messages, kicks, alerts) to specific users.
- **Dashboards**: Separate "Command Centers" — Teachers get room controls, Students get session overview.

### `meetings` — Room Governance
- **LiveKit Proxy**: Generates signed JWT tokens for WebRTC session authentication.
- **Host Controls**: `kick_user` WebSocket handler creates a `KickedParticipant` record with a 1-hour expiry.
- **Signaling**: Real-time `permission_update` events control per-participant A/V/Screen permissions.

### `attendance` — AI Monitoring
- **Face Recognition**: Matches live video frames against encrypted student biometric encodings.
- **Attention Tracking**: Scores focus level from head pose estimation using OpenCV.
- **Attendance Service**: Background Celery task that aggregates "Presence Minutes" into final attendance records.

### `camera_service` — RTSP Microservice
- A **standalone Django sub-project** that captures RTSP/HTTP IP camera feeds independently.
- Prevents heavy video processing from blocking the main application thread.

---

## 📡 Real-Time Signaling

Edumi2 uses a **Global Signaling Bridge** to eliminate any manual page refreshes:

```
User Action (e.g. Send Message)
        │
        ▼  AJAX POST
Django View ── saves to DB ──► Broadcast WebSocket Event
                                        │
                                        ▼
                              NotificationWS Consumer
                                        │
                           ┌────────────┴────────────┐
                           ▼                         ▼
                    Student Browser           Teacher Browser
                  (DOM updates instantly)   (Dashboard updates)
```

### Key WebSocket Event Types

| Event | Direction | Description |
|---|---|---|
| `new_message` | Server → Client | Pushes a new chat message to recipients |
| `kick_user` | Client → Server | Teacher initiates a kick action |
| `kicked` | Server → Client | Disconnects target student's socket |
| `permission_update` | Server → Client | Updates participant A/V/Screen state |
| `meeting_started` | Server → Client | Notifies enrolled students of a new session |

---

## 🔐 Security

| Layer | Mechanism |
|---|---|
| **Transport** | HTTPS/WSS enforced for all WebRTC and WebSocket traffic |
| **Authentication** | Django session-based auth + 2FA support via `django-two-factor-auth` |
| **Biometrics** | Face encodings encrypted at rest; never transmitted in plaintext |
| **Meeting Access** | LiveKit JWT with short-lived signed tokens per session |
| **Bans** | Database-backed `KickedParticipant` records with server-side expiry validation |
| **CSRF** | Django CSRF middleware + configurable trusted origins |
| **WebRTC (Ngrok)** | Ngrok tunnel provides HTTPS entry point required by browser camera APIs |

> **For LAN access:** Students joining via local IP must enable `chrome://flags/#unsafely-treat-insecure-origin-as-secure` and add the server IP, because browsers require HTTPS for camera/microphone APIs.

---

## 🔧 Troubleshooting

| Issue | Root Cause | Solution |
|---|---|---|
| Camera / Microphone blocked | Browser requires HTTPS for media APIs | Use `start_app.ps1` to launch **Ngrok**, or add IP to Chrome's insecure origin allowlist |
| `WebSocket connection failed` | Redis not running | Start Redis (`redis-server`) and verify `REDIS_URL` in `.env` |
| `Database is locked` | SQLite contention under AI load | The built-in middleware handles retries; switch to PostgreSQL for production |
| `LiveKit token invalid` | Secret mismatch or expired token | Ensure `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` match in `.env` and `livekit.yaml` |
| `Face ID not recognized` | Poor lighting or registration issue | Re-register Face ID in a well-lit environment; check OpenCV camera index |
| `Celery tasks not running` | Worker not started or broker unreachable | Start `celery -A school_project worker -l info -P solo` and confirm Redis is up |
| `Static files 404` | `collectstatic` not run | Run `python manage.py collectstatic --noinput` |
| `.venv activation fails` | Wrong path prefix | Use `.venv\Scripts\Activate` (note the dot prefix on Windows) |

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feat/your-feature`
3. **Commit** your changes: `git commit -m "feat: add your feature"`
4. **Push** to the branch: `git push origin feat/your-feature`
5. **Open** a Pull Request

Please follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages.

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## 👥 Authors

| Name | GitHub |
|---|---|
| **Tarun Kumar** | [@tarunkumar-sys](https://github.com/tarunkumar-sys) |
| **Gaurav Singh** | [@GAuravgiy87](https://github.com/GAuravgiy87) |

---

<div align="center">

**Edumi2 — Engineering the Future of Academic Interaction.**

<sub>Built with ❤️ by <a href="https://github.com/tarunkumar-sys">Tarun Kumar</a> &amp; <a href="https://github.com/GAuravgiy87">Gaurav Singh</a></sub>

</div>
