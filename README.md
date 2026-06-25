<div align="center">

# 🎓 EduMi 2
### The Complete Academic Command Center

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![Daphne](https://img.shields.io/badge/Daphne-ASGI%2FHTTPS-7B3F85?style=for-the-badge)](https://github.com/django/daphne)
[![LiveKit](https://img.shields.io/badge/LiveKit-WebRTC%20SFU-00C58E?style=for-the-badge)](https://livekit.io)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Video%20Processing-007808?style=for-the-badge)](https://ffmpeg.org)
[![Redis](https://img.shields.io/badge/Redis-Celery%20Queue-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![HTTPS](https://img.shields.io/badge/HTTPS-SSL%2FTLS-green?style=for-the-badge&logo=letsencrypt&logoColor=white)](https://en.wikipedia.org/wiki/HTTPS)

A unified educational platform combining virtual classrooms, AI-powered attendance, real-time engagement analytics, hardware/mobile camera management, and non-destructive video editing — all served over HTTPS with end-to-end security.

</div>

---

## Table of Contents

- [What is EduMi 2?](#-what-is-edumi-2)
- [Key Features](#-key-features)
- [Technology Stack](#️-technology-stack)
- [System Architecture](#-system-architecture)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Environment Variables](#️-environment-variables)
- [Running the App (HTTPS)](#-running-the-app-https)
- [Accessing the App](#-accessing-the-app)
- [Trusting the SSL Certificate](#-trusting-the-ssl-certificate)
- [Production Deployment (Docker)](#-production-deployment-docker)
- [Default Credentials & Ports](#-default-credentials--ports)
- [Skill Badges](#-skill-badges)

---

## 🎯 What is EduMi 2?

EduMi 2 replaces the patchwork of tools schools use today — video conferencing, attendance registers, surveillance software, and video editors — with a single, self-hosted platform. Everything runs over HTTPS, biometrics are encrypted at rest, and real-time features are powered by WebSockets and WebRTC.

**Problems it solves:**

| Problem | EduMi 2 Solution |
|---|---|
| Manual roll call wastes 5–10 min per class | AI face-recognition attendance, fully automated |
| No visibility into student attention | Real-time engagement scoring with emotion detection |
| 5+ fragmented tools | One platform for meetings, cameras, recordings, editing |
| Raw biometric data stored in plaintext | Fernet AES-256 encryption for all face embeddings |
| Expensive dedicated camera hardware | Use any Android/iPhone as a live classroom camera |
| Meetings served over plain HTTP | Full HTTPS via self-signed cert + Daphne ASGI |

---

## ✨ Key Features

### 🔐 HTTPS Everywhere
- Daphne ASGI server runs with a self-signed SSL/TLS certificate
- All cookies (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`) are HTTPS-only
- One-click script installs the cert as a trusted root CA on Windows

### 🤖 AI Attendance
- Students register their face once via the browser (no app needed)
- Face encodings (128-d embeddings from dlib) are **Fernet-encrypted** before storage
- During class, the camera service continuously matches frames against stored embeddings
- Attendance is recorded only after sustained verified presence (configurable seconds)

### 📊 Engagement Analytics
- Every few seconds, per-student emotional state and attention data is captured
- `StudentEngagementSnapshot` records are aggregated into an `EngagementReport` after class
- Teachers see a post-class dashboard: attention scores, emotion breakdown, trend graphs

### 🎥 Dual Camera System
- **RTSP cameras** — register hardware IP cameras by URL, stream MJPEG in-browser
- **Mobile cameras** — use any phone running IP Webcam (Android) or DroidCam as a live feed
- Both feed into the same AI pipeline (head counting, engagement, face recognition)

### 🖥️ Virtual Classrooms (LiveKit WebRTC)
- Persistent classrooms with student membership and teacher approval
- Low-latency video/audio via LiveKit SFU (Selective Forwarding Unit)
- In-meeting controls: mute all, kick participant, raise hand, live chat
- Attendance auto-logged from join/leave events

### ✂️ Non-Destructive Video Editor
- Edit recordings without touching the original file
- Actions (trim, mute, rotate, add text, add audio) are stored as a sequence in the DB
- Final export applies all actions as a single FFmpeg pipeline

### ⚡ Real-Time Everything
- WebSocket notifications for meetings, messages, attendance events
- Celery background tasks for face processing, report generation, recording
- Redis channel layer for multi-consumer pub/sub

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| Web Framework | Django 4.2, Python 3.11+ |
| ASGI Server | Daphne 4.0 + Twisted (SSL endpoint) |
| Real-Time | Django Channels 4.0, WebSockets |
| Video Conferencing | LiveKit WebRTC SFU |
| Computer Vision | OpenCV, face_recognition, dlib |
| Video Processing | FFmpeg (subprocess) |
| Background Tasks | Celery 5.3 + Redis |
| Encryption | cryptography (Fernet AES-256) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Static Files | WhiteNoise |
| Web Server (prod) | Nginx (reverse proxy + SSL termination) |
| Deployment | Docker, Docker Compose |

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      Browser / Client                    │
│         HTTPS  ·  WebSocket (wss://)  ·  WebRTC          │
└────────────────────────┬─────────────────────────────────┘
                         │
             ┌───────────▼───────────┐
             │  Nginx : 443 (prod)   │  ← SSL termination, static files
             │  Daphne : 8002 (dev)  │  ← HTTPS + WSS direct
             └───────────┬───────────┘
                         │
          ┌──────────────▼──────────────┐
          │       Django Main App        │
          │   school_project/            │
          │  ┌──────────┐ ┌──────────┐  │
          │  │ accounts │ │meetings  │  │  ← Auth, profiles, messaging
          │  │          │ │(LiveKit) │  │  ← Virtual classrooms
          │  ├──────────┤ ├──────────┤  │
          │  │attendance│ │ cameras  │  │  ← Face AI, engagement
          │  │          │ │(RTSP)    │  │  ← Hardware camera mgmt
          │  ├──────────┤ ├──────────┤  │
          │  │ videos   │ │  video   │  │  ← Upload & storage
          │  │          │ │ editing  │  │  ← Non-destructive editor
          │  ├──────────┤ ├──────────┤  │
          │  │  mobile  │ │ common   │  │  ← Phone cameras
          │  │ cameras  │ │          │  │  ← Shared utilities
          │  └──────────┘ └──────────┘  │
          └───────┬───────────┬─────────┘
                  │           │
         ┌────────▼──┐   ┌────▼──────┐
         │  SQLite /  │   │   Redis   │
         │ PostgreSQL │   │  :6379    │
         └────────────┘   └──────┬────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
          ┌─────────▼────────┐   ┌────────────▼──────┐
          │  Celery Worker   │   │  Camera Service    │
          │ (background tasks│   │  :8003 (Waitress)  │
          │  face processing,│   │  ─ MJPEG proxy     │
          │  report gen,     │   │  ─ Head counting   │
          │  recording mgmt) │   │  ─ Face detection  │
          └──────────────────┘   └───────────────────┘
                                          │
                               ┌──────────▼──────────┐
                               │  LiveKit SFU : 7880  │
                               │  WebRTC peer routing │
                               └─────────────────────┘
```

---

## 📁 Project Structure

```
Edumi2/
├── school_project/          # Django project root
│   ├── settings.py          # Master configuration
│   ├── urls.py              # Root URL routing
│   ├── asgi.py              # ASGI entry (Daphne + Channels)
│   ├── wsgi.py              # WSGI entry (production alt.)
│   ├── celery.py            # Celery app init
│   └── middleware.py        # DatabaseErrorMiddleware
│
├── accounts/                # Auth, profiles, messaging, notifications
├── attendance/              # Face recognition attendance + engagement
├── cameras/                 # RTSP hardware camera management
├── mobile_cameras/          # Phone camera integration
├── meetings/                # LiveKit virtual classrooms
├── videos/                  # Video upload and storage
├── video_editing/           # Non-destructive video editor
├── common/                  # Shared models, utils, template tags
│
├── camera_service/          # AI microservice (port 8003, Waitress)
│
├── templates/               # All HTML templates (per-app folders)
├── static/                  # Source static files (CSS, JS, images)
├── staticfiles/             # Collected static files (auto-generated)
│
├── certs/                   # SSL certificate + private key
│   ├── edumi.crt
│   └── edumi.key
│
├── config/                  # Service configuration files
│   ├── livekit.yaml         # LiveKit server config
│   └── .env.example         # Environment variable template
│
├── nginx/                   # Nginx config (production)
│   └── nginx.conf
│
├── scripts/                 # Setup and deployment scripts
│   ├── generate_ssl_cert.py # Regenerate SSL certificates
│   ├── trust_ssl_cert.ps1   # Install cert as trusted CA (Windows)
│   ├── trust_ssl_cert.bat   # Double-click launcher for above
│   ├── allow_firewall.ps1   # Open Windows firewall ports
│   ├── allow_firewall.bat   # Launcher for above
│   └── deploy.sh            # Linux Docker deployment
│
├── livekit-bin/             # LiveKit server binary (Windows)
├── database/                # SQLite DB + media files (gitignored)
├── logs/                    # Application logs (gitignored)
│
├── manage.py                # Django management CLI
├── requirements.txt         # Python dependencies
├── Dockerfile               # Main app container
├── docker-compose.yml       # Full stack orchestration
├── run_ssl_server.py        # HTTPS server launcher (Daphne + SSL)
├── run_https.bat            # Quick HTTPS-only start (Windows)
├── start_app.bat            # Full system start (Windows, double-click)
├── start_app.ps1            # Full system start script (PowerShell)
├── start.sh                 # Full system start (Linux/Docker)
├── .env                     # Environment variables (gitignored)
└── .gitignore
```

---

## 📋 Prerequisites

Install these before anything else.

### 1. Python 3.11+
```
https://python.org/downloads/
```
Verify: `python --version`

### 2. Redis
**Windows** — Download and install from:
```
https://github.com/microsoftarchive/redis/releases
```
Or use WSL2: `sudo apt install redis-server`

**Linux/Mac:**
```bash
sudo apt install redis-server   # Ubuntu/Debian
brew install redis              # macOS
```
Verify: `redis-cli ping` → should return `PONG`

### 3. FFmpeg
**Windows** — Download from https://ffmpeg.org/download.html, extract, and add `bin/` to your PATH.

**Linux:**
```bash
sudo apt install ffmpeg
```
Verify: `ffmpeg -version`

### 4. dlib build dependencies (for face recognition)
**Windows** — `dlib-bin` in requirements.txt installs a pre-built wheel (no build tools needed).

**Linux:**
```bash
sudo apt install cmake build-essential libopenblas-dev liblapack-dev libx11-dev
```

---

## 🚀 Installation

### Step 1 — Clone the repo
```bash
git clone <repo-url>
cd Edumi2-my-work2
```

### Step 2 — Create and activate a virtual environment
```powershell
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```
> This installs all 52 packages including OpenCV, face_recognition, dlib, Daphne, Celery, LiveKit, etc.

### Step 4 — Configure environment variables
```bash
cp config/.env.example .env
```
Then open `.env` and fill in all required values. See the [Environment Variables](#️-environment-variables) section below.

### Step 5 — Run database migrations
```bash
python manage.py migrate
```

### Step 6 — Create a superuser (admin account)
```bash
python manage.py createsuperuser
```

### Step 7 — Generate SSL certificate (first time only)
```bash
python scripts/generate_ssl_cert.py
```
This creates `certs/edumi.crt` and `certs/edumi.key` — valid for 10 years, covering `localhost`, `127.0.0.1`, and `edumi.ac.in`.

### Step 8 — Trust the SSL certificate (removes browser warning)
```
# Windows — double-click this file, approve UAC prompt
scripts\trust_ssl_cert.bat
```
After this, Chrome/Edge will show the padlock as **green/secure** with no warnings.

### Step 9 — Add edumi.ac.in to hosts file (optional, for named domain)
The `start_app.ps1` does this automatically. To do it manually:
```
# Add this line to C:\Windows\System32\drivers\etc\hosts
127.0.0.1    edumi.ac.in    www.edumi.ac.in
```

---

## ⚙️ Environment Variables

Copy `config/.env.example` to `.env` and set all of these:

```env
# ── Django Core ────────────────────────────────────────────────────────────
SECRET_KEY=your-very-long-random-secret-key-here
DEBUG=True                          # Set to False in production
ALLOWED_HOSTS=*                     # Restrict in production, e.g. edumi.ac.in

# ── HTTPS Security ─────────────────────────────────────────────────────────
SESSION_COOKIE_SECURE=True          # Cookies sent over HTTPS only
CSRF_COOKIE_SECURE=True             # CSRF token sent over HTTPS only
SECURE_SSL_REDIRECT=False           # True if you have a plain-HTTP port to redirect
CSRF_TRUSTED_ORIGINS=https://localhost:8002,https://127.0.0.1:8002,https://edumi.ac.in:8002

# ── LiveKit WebRTC ─────────────────────────────────────────────────────────
LIVEKIT_URL=ws://localhost:8002/livekit-proxy
LIVEKIT_INTERNAL_URL=ws://localhost:7880
LIVEKIT_INTERNAL_HTTP_URL=http://localhost:7880
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret-32-chars-min

# ── Redis (Celery + Channels) ──────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Face Recognition & Encryption ─────────────────────────────────────────
# Generate key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FACE_ENCRYPTION_KEY=your-fernet-encryption-key-here
FACE_MATCH_THRESHOLD=0.50           # 0 = identical, 1 = completely different; lower = stricter
FACE_PRESENCE_DURATION=30           # Seconds of continuous verified presence to mark attendance

# ── Camera Service ─────────────────────────────────────────────────────────
CAMERA_SERVICE_URL=http://localhost:8003

# ── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
```

**Generate a SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Generate a FACE_ENCRYPTION_KEY:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 🔒 Running the App (HTTPS)

### Option A — Full System Start (Recommended)
Starts Redis check, SSL cert generation, migrations, static collection, Celery, Camera Service, and the Daphne HTTPS server all at once.

```powershell
# Windows — double-click or run from PowerShell:
.\start_app.bat    # or start_app.bat

# Or directly:
powershell -ExecutionPolicy Bypass -File start_app.ps1
```

What it does, step by step:
1. Checks/adds `edumi.ac.in` → `127.0.0.1` in the Windows hosts file (auto UAC)
2. Generates SSL cert if missing
3. Checks Redis is running (starts it if not)
4. Starts LiveKit SFU server
5. Runs `manage.py migrate`
6. Runs `manage.py collectstatic`
7. Starts Celery worker (threads mode, background)
8. Starts Camera Service on port 8003 (background)
9. Starts Daphne HTTPS server on port 8002 (foreground)

### Option B — Quick HTTPS-Only Start
Use when Redis, Celery, and LiveKit are already running (e.g., after a code change).

```powershell
.\run_https.bat
```
Or directly:
```bash
venv\Scripts\python.exe run_ssl_server.py
```

### Option C — Manual Start (advanced)
```powershell
# Terminal 1 — Redis (if not running as a service)
redis-server

# Terminal 2 — Celery worker
venv\Scripts\celery.exe -A school_project worker -l info -P threads

# Terminal 3 — Camera service
venv\Scripts\python.exe camera_service/serve.py

# Terminal 4 — LiveKit
livekit-bin\livekit-server.exe --config config\livekit.yaml

# Terminal 5 — Django HTTPS (Daphne)
venv\Scripts\python.exe run_ssl_server.py
```

### Linux / Docker
```bash
# Quick start (no Docker)
chmod +x start.sh
./start.sh

# Docker Compose (full stack)
bash scripts/deploy.sh
# or:
docker-compose up --build
```

---

## 🌐 Accessing the App

Once running, open your browser:

| URL | Purpose |
|---|---|
| `https://127.0.0.1:8002` | Main app (IP direct) |
| `https://localhost:8002` | Main app (localhost) |
| `https://edumi.ac.in:8002` | Main app (named domain, after hosts entry) |
| `https://127.0.0.1:8002/admin/` | Django admin panel |

**First visit:** Chrome/Edge will show "Your connection is not private" if the cert isn't trusted yet. Either:
- Click **Advanced → Proceed to 127.0.0.1 (unsafe)** to bypass once
- Or run `scripts\trust_ssl_cert.bat` to trust the cert permanently (recommended)

---

## 🔑 Trusting the SSL Certificate

The self-signed cert causes `NET::ERR_CERT_AUTHORITY_INVALID` in browsers. To eliminate this permanently:

**Windows (installs cert to Trusted Root CA for all users):**
```
# Double-click:
scripts\trust_ssl_cert.bat

# Or from PowerShell (as Administrator):
powershell -ExecutionPolicy Bypass -File scripts\trust_ssl_cert.ps1
```
Approve the UAC prompt, then **fully restart Chrome** (`chrome://restart`).

**Linux / macOS:**
```bash
# Ubuntu/Debian
sudo cp certs/edumi.crt /usr/local/share/ca-certificates/edumi.crt
sudo update-ca-certificates

# macOS
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain certs/edumi.crt
```

After trusting, the padlock in the address bar will show as **secure (green)**.

---

## 🐳 Production Deployment (Docker)

The Docker Compose stack includes: Nginx (SSL + reverse proxy), Django (Daphne), Camera Service, Celery Worker, Redis, LiveKit.

```bash
# Copy and configure environment
cp config/.env.example .env
# Edit .env — set DEBUG=False, proper SECRET_KEY, LiveKit keys, etc.

# Build and start everything
docker-compose up --build -d

# View logs
docker-compose logs -f

# Run migrations inside container
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser
```

The Nginx container handles SSL termination on port 443. Django runs on port 8002 internally (not exposed publicly). Nginx proxies `/ws/` and `/livekit-proxy/` as WebSocket upgrades.

---

## 🔢 Default Credentials & Ports

| Service | Port | Notes |
|---|---|---|
| Django (HTTPS/Daphne) | **8002** | Main app — use `https://` |
| Camera Service (Waitress) | **8003** | AI microservice — HTTP only, internal |
| LiveKit SFU | **7880** | WebRTC server — internal |
| Redis | **6379** | Channel layer + Celery broker |
| Nginx (production) | **443** | Reverse proxy |

**Default admin:** Created during `python manage.py createsuperuser` — no default credentials are hardcoded.

**Firewall:** Run `scripts\allow_firewall.bat` to open ports 8002 and 8003 in Windows Firewall for LAN access.

---

## 🏅 Skill Badges

Technologies used in this project:

### Backend
![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=flat-square&logo=django&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=flat-square&logo=celery&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white)

### Real-Time & Networking
![WebSockets](https://img.shields.io/badge/WebSockets-black?style=flat-square&logo=socketdotio&logoColor=white)
![WebRTC](https://img.shields.io/badge/WebRTC-333333?style=flat-square&logo=webrtc&logoColor=white)
![LiveKit](https://img.shields.io/badge/LiveKit-00C58E?style=flat-square)
![Daphne](https://img.shields.io/badge/Daphne_ASGI-7B3F85?style=flat-square)

### Security
![HTTPS](https://img.shields.io/badge/HTTPS-SSL/TLS-green?style=flat-square&logo=letsencrypt)
![Fernet](https://img.shields.io/badge/Fernet-AES--256-blue?style=flat-square&logo=gnupg)
![CSRF](https://img.shields.io/badge/CSRF-Protected-orange?style=flat-square)

### AI & Computer Vision
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=flat-square&logo=opencv&logoColor=white)
![dlib](https://img.shields.io/badge/dlib-face--recognition-lightgrey?style=flat-square)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=flat-square&logo=numpy&logoColor=white)

### Video & Media
![FFmpeg](https://img.shields.io/badge/FFmpeg-007808?style=flat-square&logo=ffmpeg&logoColor=white)
![RTSP](https://img.shields.io/badge/RTSP-streaming-blue?style=flat-square)
![MJPEG](https://img.shields.io/badge/MJPEG-proxy-blue?style=flat-square)

### Infrastructure
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![Nginx](https://img.shields.io/badge/Nginx-009639?style=flat-square&logo=nginx&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=flat-square&logo=postgresql&logoColor=white)

---

<div align="center">
  <sub>Built for better classrooms. Run <code>start_app.bat</code> and go.</sub>
</div>
