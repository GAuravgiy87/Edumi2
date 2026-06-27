<div align="center">

<img src="https://github.com/tarunkumar-sys/tarunkumar-sys/blob/main/matrix.svg" alt="Matrix Animation" width="100%"/>

<br/>

<h1>
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=36&duration=3000&pause=1000&color=00C58E&center=true&vCenter=true&width=600&lines=🎓+EduMi+2;Academic+Command+Center;Built+for+Better+Classrooms" alt="Typing SVG" />
</h1>

<p align="center">
  <strong>A unified, self-hosted educational platform combining virtual classrooms,<br/>AI-powered attendance, real-time engagement analytics, and non-destructive video editing —<br/>all secured over HTTPS with end-to-end encryption.</strong>
</p>

<br/>

<!-- Badges Row 1 -->
<p align="center">
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/></a>
  <a href="https://djangoproject.com"><img src="https://img.shields.io/badge/Django-4.2-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django"/></a>
  <a href="https://github.com/django/daphne"><img src="https://img.shields.io/badge/Daphne-ASGI%20%2F%20HTTPS-7B3F85?style=for-the-badge" alt="Daphne"/></a>
  <a href="https://livekit.io"><img src="https://img.shields.io/badge/LiveKit-WebRTC%20SFU-00C58E?style=for-the-badge" alt="LiveKit"/></a>
</p>

<!-- Badges Row 2 -->
<p align="center">
  <a href="https://opencv.org"><img src="https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" alt="OpenCV"/></a>
  <a href="https://ffmpeg.org"><img src="https://img.shields.io/badge/FFmpeg-Video%20Processing-007808?style=for-the-badge" alt="FFmpeg"/></a>
  <a href="https://redis.io"><img src="https://img.shields.io/badge/Redis-Celery%20Queue-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis"/></a>
  <img src="https://img.shields.io/badge/HTTPS-SSL%20%2F%20TLS-4CAF50?style=for-the-badge&logo=letsencrypt&logoColor=white" alt="HTTPS"/>
</p>

<!-- Badges Row 3 -->
<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License"/>
  <img src="https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge" alt="Status"/>
  <img src="https://img.shields.io/badge/PRs-Welcome-orange?style=for-the-badge" alt="PRs Welcome"/>
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Docker-blue?style=for-the-badge" alt="Platform"/>
</p>

<br/>

</div>

---

## 📌 Table of Contents

<details open>
<summary><b>Click to expand / collapse</b></summary>

- [What is EduMi 2?](#-what-is-edumi-2)
- [Why EduMi 2?](#-why-edumi-2)
- [Key Features](#-key-features)
- [Technology Stack](#️-technology-stack)
- [System Architecture](#-system-architecture)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Environment Variables](#️-environment-variables)
- [Running the App](#-running-the-app-https)
- [Accessing the App](#-accessing-the-app)
- [Trusting the SSL Certificate](#-trusting-the-ssl-certificate)
- [Production Deployment (Docker)](#-production-deployment-docker)
- [Default Credentials & Ports](#-default-credentials--ports)
- [Contributing](#-contributing)

</details>

---

## 🎯 What is EduMi 2?

> **EduMi 2** replaces the fragmented patchwork of tools schools rely on today — video conferencing software, manual attendance registers, surveillance dashboards, and standalone video editors — with a **single, self-hosted platform**.

Everything runs over **HTTPS**. Biometrics are **encrypted at rest**. Real-time features are powered by **WebSockets** and **WebRTC**. No third-party cloud dependencies required.

---

## 💡 Why EduMi 2?

<div align="center">

| ❌ Problem | ✅ EduMi 2 Solution |
|---|---|
| Manual roll call wastes 5–10 min per class | AI face-recognition attendance — **fully automated** |
| Zero visibility into student attention | Real-time engagement scoring with **emotion detection** |
| 5+ fragmented tools to manage | **One platform** for meetings, cameras, recordings & editing |
| Raw biometric data stored in plaintext | **Fernet AES-256 encryption** for all face embeddings |
| Expensive dedicated camera hardware | Use any **Android / iPhone** as a live classroom camera |
| Meetings served over plain HTTP | Full **HTTPS** via self-signed cert + Daphne ASGI |

</div>

---

## ✨ Key Features

<details open>
<summary><b>🔐 HTTPS Everywhere</b></summary>

- Daphne ASGI server runs with a self-signed SSL/TLS certificate
- All session and CSRF cookies are `HTTPS-only` (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`)
- One-click PowerShell script installs the cert as a **trusted root CA** on Windows — no browser warnings

</details>

<details open>
<summary><b>🤖 AI-Powered Attendance</b></summary>

- Students register their face **once** via the browser — no app required
- Face encodings (128-d embeddings from `dlib`) are **Fernet-encrypted** before being written to the database
- During class, the camera service continuously matches live frames against stored embeddings
- Attendance is only recorded after **sustained verified presence** (configurable duration in seconds)

</details>

<details open>
<summary><b>📊 Real-Time Engagement Analytics</b></summary>

- Every few seconds, per-student **emotional state** and **attention data** is captured from camera feeds
- `StudentEngagementSnapshot` records are aggregated into an `EngagementReport` automatically after class
- Teachers access a **post-class dashboard** showing attention scores, emotion breakdowns, and trend graphs

</details>

<details open>
<summary><b>🎥 Dual Camera System</b></summary>

- **RTSP Cameras** — register hardware IP cameras by URL; stream live **MJPEG in-browser**
- **Mobile Cameras** — use any phone running IP Webcam (Android) or DroidCam as a live feed
- Both feeds pipe into the same **AI pipeline** — head counting, engagement scoring, face recognition

</details>

<details open>
<summary><b>🖥️ Virtual Classrooms (LiveKit WebRTC)</b></summary>

- Persistent virtual classrooms with student membership and **teacher-controlled approval**
- Low-latency video/audio via **LiveKit SFU** (Selective Forwarding Unit)
- In-meeting controls: mute all, kick participant, raise hand queue, live chat
- Attendance **auto-logged** from join/leave WebRTC events

</details>

<details open>
<summary><b>✂️ Non-Destructive Video Editor</b></summary>

- Edit recordings **without touching the original file** — source is always preserved
- Actions (trim, mute, rotate, add text overlay, add audio) stored as an ordered sequence in the database
- Final export applies all actions as a **single FFmpeg pipeline pass** — no generation loss

</details>

<details open>
<summary><b>⚡ Real-Time Everything</b></summary>

- **WebSocket** notifications for meetings, messages, and attendance events
- **Celery** background task queue for face processing, report generation, and recording management
- **Redis** channel layer for multi-consumer pub/sub across all services

</details>

---

## 🛠️ Technology Stack

<div align="center">

| Layer | Technologies |
|---|---|
| **Web Framework** | Django 4.2, Python 3.11+ |
| **ASGI Server** | Daphne 4.0 + Twisted (SSL endpoint) |
| **Real-Time** | Django Channels 4.0, WebSockets |
| **Video Conferencing** | LiveKit WebRTC SFU |
| **Computer Vision** | OpenCV, face_recognition, dlib |
| **Video Processing** | FFmpeg (subprocess pipeline) |
| **Background Tasks** | Celery 5.3 + Redis |
| **Encryption** | cryptography (Fernet AES-256) |
| **Database** | SQLite (dev) / PostgreSQL (prod) |
| **Static Files** | WhiteNoise |
| **Web Server (prod)** | Nginx (reverse proxy + SSL termination) |
| **Deployment** | Docker, Docker Compose |

</div>

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                       Browser / Client                       │
│           HTTPS  ·  WebSocket (wss://)  ·  WebRTC            │
└────────────────────────────┬─────────────────────────────────┘
                             │
               ┌─────────────▼─────────────┐
               │   Nginx : 443   (prod)     │  ← SSL termination + static files
               │   Daphne : 8002 (dev)      │  ← HTTPS + WSS direct
               └─────────────┬─────────────┘
                             │
            ┌────────────────▼────────────────┐
            │          Django Main App          │
            │        school_project/            │
            │  ┌──────────┐   ┌─────────────┐  │
            │  │ accounts │   │  meetings   │  │  ← Auth, profiles, messaging
            │  │          │   │  (LiveKit)  │  │  ← Virtual classrooms
            │  ├──────────┤   ├─────────────┤  │
            │  │attendance│   │   cameras   │  │  ← Face AI + engagement
            │  │          │   │   (RTSP)    │  │  ← Hardware camera mgmt
            │  ├──────────┤   ├─────────────┤  │
            │  │  videos  │   │video_editing│  │  ← Upload & storage
            │  │          │   │             │  │  ← Non-destructive editor
            │  ├──────────┤   ├─────────────┤  │
            │  │  mobile  │   │   common    │  │  ← Phone cameras
            │  │ cameras  │   │             │  │  ← Shared utilities
            │  └──────────┘   └─────────────┘  │
            └────────────┬──────────┬───────────┘
                         │          │
               ┌──────────▼──┐  ┌───▼──────┐
               │  SQLite /    │  │  Redis   │
               │ PostgreSQL   │  │  :6379   │
               └─────────────┘  └────┬─────┘
                                      │
                       ┌──────────────┴─────────────┐
                       │                             │
           ┌───────────▼──────────┐   ┌─────────────▼──────┐
           │    Celery Worker     │   │   Camera Service    │
           │  (face processing,   │   │   :8003 (Waitress)  │
           │   report gen,        │   │   ─ MJPEG proxy     │
           │   recording mgmt)    │   │   ─ Head counting   │
           └──────────────────────┘   │   ─ Face detection  │
                                      └──────────┬──────────┘
                                                 │
                                    ┌────────────▼────────────┐
                                    │   LiveKit SFU : 7880    │
                                    │   WebRTC peer routing   │
                                    └─────────────────────────┘
```

---

## 📁 Project Structure

```
Edumi2/
│
├── school_project/          # Django project root
│   ├── settings.py          # Master configuration
│   ├── urls.py              # Root URL routing
│   ├── asgi.py              # ASGI entry (Daphne + Channels)
│   ├── wsgi.py              # WSGI entry (production alt.)
│   ├── celery.py            # Celery application init
│   └── middleware.py        # DatabaseErrorMiddleware
│
├── accounts/                # Auth, profiles, messaging, notifications
├── attendance/              # Face recognition attendance + engagement analytics
├── cameras/                 # RTSP hardware camera management
├── mobile_cameras/          # Phone camera integration
├── meetings/                # LiveKit virtual classrooms
├── videos/                  # Video upload and storage
├── video_editing/           # Non-destructive video editor
├── common/                  # Shared models, utils, template tags
│
├── camera_service/          # AI microservice (port 8003, Waitress)
│
├── templates/               # HTML templates (per-app subfolders)
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
│   ├── trust_ssl_cert.ps1   # Install cert as trusted root CA (Windows)
│   ├── trust_ssl_cert.bat   # Double-click launcher for above
│   ├── allow_firewall.ps1   # Open Windows Firewall ports
│   ├── allow_firewall.bat   # Launcher for above
│   └── deploy.sh            # Linux Docker deployment
│
├── livekit-bin/             # LiveKit server binary (Windows) — see Prerequisites
├── database/                # SQLite DB + media files (gitignored)
├── logs/                    # Application logs (gitignored)
│
├── manage.py                # Django management CLI
├── requirements.txt         # Python dependencies (52 packages)
├── Dockerfile               # Main app container
├── docker-compose.yml       # Full-stack orchestration
├── run_ssl_server.py        # HTTPS server launcher (Daphne + SSL)
├── run_https.bat            # Quick HTTPS-only start (Windows)
├── start_app.bat            # Full system start (Windows, double-click)
├── start_app.ps1            # Full system start script (PowerShell)
├── start.sh                 # Full system start (Linux / Docker)
├── .env                     # Environment variables (gitignored)
└── .gitignore
```

---

## 📋 Prerequisites

Install all of the following **before** cloning the repository.

### 1. 🐍 Python 3.11+

```
https://python.org/downloads/
```

```bash
python --version   # Should output Python 3.11.x or higher
```

### 2. 🔴 Redis

<table>
<tr><th>Platform</th><th>Command</th></tr>
<tr>
<td><b>Windows</b></td>
<td>

Download from [microsoftarchive/redis](https://github.com/microsoftarchive/redis/releases), or use WSL2:
```bash
sudo apt install redis-server
```
</td>
</tr>
<tr>
<td><b>Ubuntu / Debian</b></td>
<td>

```bash
sudo apt install redis-server
```
</td>
</tr>
<tr>
<td><b>macOS</b></td>
<td>

```bash
brew install redis
```
</td>
</tr>
</table>

```bash
redis-cli ping   # Expected response: PONG
```

### 3. 🎬 FFmpeg

**Windows** — Download from [ffmpeg.org](https://ffmpeg.org/download.html), extract the archive, and add the `bin/` directory to your system `PATH`.

**Linux:**

```bash
sudo apt install ffmpeg
```

```bash
ffmpeg -version   # Verify installation
```

### 4. 🧠 dlib Build Dependencies (Face Recognition)

**Windows** — `dlib-bin` in `requirements.txt` installs a pre-built wheel. **No build tools needed.**

**Linux:**

```bash
sudo apt install cmake build-essential libopenblas-dev liblapack-dev libx11-dev
```

### 5. 📡 LiveKit Server (WebRTC SFU)

The `livekit-bin/` folder is excluded from version control. Download the binary manually:

1. Create a folder named `livekit-bin` in the project root
2. Download the latest release for your OS from [LiveKit GitHub Releases](https://github.com/livekit/livekit/releases)
3. Extract and place the `livekit-server` executable (e.g., `livekit-server.exe` on Windows) inside `Edumi2\livekit-bin/`
---

## 🚀 Installation

### Step 1 — Clone the Repository

```bash
git clone -b new_edumi https://github.com/GAuravgiy87/Edumi2.git
cd Edumi2
```

### Step 2 — Create & Activate a Virtual Environment

```powershell
# Windows (PowerShell)
python -m venv venv
venv\Scripts\activate
```

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

> Installs all **52 packages** including OpenCV, face_recognition, dlib, Daphne, Celery, LiveKit SDK, and more.

### Step 4 — Configure Environment Variables

```bash
cp config/.env.example .env
```

Open `.env` and populate all required values. Full reference in the [Environment Variables](#️-environment-variables) section below.

### Step 5 — Run Database Migrations

```bash
python manage.py migrate
```

### Step 6 — Create a Superuser (Admin Account)

```bash
python manage.py createsuperuser
```

### Step 7 — Generate SSL Certificate *(first time only)*

```bash
python scripts/generate_ssl_cert.py
```

Creates `certs/edumi.crt` and `certs/edumi.key` — valid for **10 years**, covering `localhost`, `127.0.0.1`, and `edumi.ac.in`.

### Step 8 — Trust the SSL Certificate *(removes browser security warnings)*

```batch
:: Windows — double-click this file and approve the UAC prompt
scripts\trust_ssl_cert.bat
```

After completing this step, Chrome and Edge will display the connection as **🔒 Secure** with no warnings.

### Step 9 — Add `edumi.ac.in` to Your Hosts File *(optional)*

`start_app.ps1` handles this automatically. To add it manually:

```
# Append to: C:\Windows\System32\drivers\etc\hosts
127.0.0.1    edumi.ac.in    www.edumi.ac.in
```

---

## ⚙️ Environment Variables

Copy `config/.env.example` to `.env` and configure every value below.

```env
# ── Django Core ─────────────────────────────────────────────────────────────
SECRET_KEY=your-very-long-random-secret-key-here
DEBUG=True                          # Set to False in production
ALLOWED_HOSTS=*                     # Restrict in production, e.g. edumi.ac.in

# ── HTTPS Security ──────────────────────────────────────────────────────────
SESSION_COOKIE_SECURE=True          # Cookies transmitted over HTTPS only
CSRF_COOKIE_SECURE=True             # CSRF token transmitted over HTTPS only
SECURE_SSL_REDIRECT=False           # Set True if you have a plain-HTTP port to redirect
CSRF_TRUSTED_ORIGINS=https://localhost:8002,https://127.0.0.1:8002,https://edumi.ac.in:8002

# ── LiveKit WebRTC ───────────────────────────────────────────────────────────
LIVEKIT_URL=ws://localhost:8002/livekit-proxy
LIVEKIT_INTERNAL_URL=ws://localhost:7880
LIVEKIT_INTERNAL_HTTP_URL=http://localhost:7880
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret-32-chars-min

# ── Redis (Celery + Channels) ────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Face Recognition & Encryption ───────────────────────────────────────────
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FACE_ENCRYPTION_KEY=your-fernet-encryption-key-here
FACE_MATCH_THRESHOLD=0.50           # 0 = identical · 1 = completely different · lower = stricter
FACE_PRESENCE_DURATION=30           # Seconds of continuous verified presence to mark attendance

# ── Camera Service ───────────────────────────────────────────────────────────
CAMERA_SERVICE_URL=http://localhost:8003

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
```

**Generate a `SECRET_KEY`:**

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Generate a `FACE_ENCRYPTION_KEY`:**

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 🔒 Running the App (HTTPS)

### ▶️ Option A — Full System Start *(Recommended)*

Starts Redis, generates the SSL cert if missing, runs migrations, collects static files, starts Celery, the Camera Service, the LiveKit SFU, and the Daphne HTTPS server — all in one command.

```powershell
# Windows — double-click or run from PowerShell:
.\start_app.bat

# Or directly via PowerShell:
powershell -ExecutionPolicy Bypass -File start_app.ps1
```

<details>
<summary><b>What does it do, step by step?</b></summary>

| # | Step |
|---|---|
| 1 | Adds `edumi.ac.in → 127.0.0.1` to the Windows hosts file (auto UAC prompt) |
| 2 | Generates SSL certificate if `certs/` doesn't exist |
| 3 | Checks Redis is running (starts it if not) |
| 4 | Starts the LiveKit SFU server |
| 5 | Runs `manage.py migrate` |
| 6 | Runs `manage.py collectstatic` |
| 7 | Starts Celery worker (threads mode, background) |
| 8 | Starts Camera Service on port `8003` (background) |
| 9 | Starts Daphne HTTPS server on port `8002` (foreground) |

</details>

### ▶️ Option B — Quick HTTPS-Only Start

Use when Redis, Celery, and LiveKit are already running (e.g., after a code change).

```powershell
.\run_https.bat
```

Or directly:

```bash
venv\Scripts\python.exe run_ssl_server.py
```

### ▶️ Option C — Manual Start (Advanced)

```powershell
# Terminal 1 — Redis
redis-server

# Terminal 2 — Celery worker
venv\Scripts\celery.exe -A school_project worker -l info -P threads

# Terminal 3 — Camera service
venv\Scripts\python.exe camera_service/serve.py

# Terminal 4 — LiveKit SFU
livekit-bin\livekit-server.exe --config config\livekit.yaml

# Terminal 5 — Django HTTPS (Daphne)
venv\Scripts\python.exe run_ssl_server.py
```

### 🐧 Linux / Docker

```bash
# Without Docker
chmod +x start.sh && ./start.sh

# With Docker Compose
bash scripts/deploy.sh
# or
docker-compose up --build
```

---

## 🌐 Accessing the App

Once the server is running, open your browser and navigate to any of the following:

<div align="center">

| URL | Purpose |
|---|---|
| `https://127.0.0.1:8002` | Main application (IP direct) |
| `https://localhost:8002` | Main application (localhost) |
| `https://edumi.ac.in:8002` | Main application (named domain — requires hosts entry) |
| `https://127.0.0.1:8002/admin/` | Django admin panel |

</div>

> **First visit:** Chrome / Edge will show *"Your connection is not private"* if the certificate hasn't been trusted yet.
> - **Quick bypass:** Click **Advanced → Proceed to 127.0.0.1 (unsafe)**
> - **Permanent fix:** Run `scripts\trust_ssl_cert.bat` (recommended)

---

## 🔑 Trusting the SSL Certificate

The self-signed certificate triggers `NET::ERR_CERT_AUTHORITY_INVALID` in browsers. Install it as a trusted root CA to eliminate this permanently.

**Windows** *(installs for all users)*:

```batch
:: Double-click:
scripts\trust_ssl_cert.bat
```

```powershell
# Or from an elevated PowerShell session:
powershell -ExecutionPolicy Bypass -File scripts\trust_ssl_cert.ps1
```

Approve the UAC prompt, then perform a **full restart** of Chrome (`chrome://restart`).

**Ubuntu / Debian:**

```bash
sudo cp certs/edumi.crt /usr/local/share/ca-certificates/edumi.crt
sudo update-ca-certificates
```

**macOS:**

```bash
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain certs/edumi.crt
```

After trusting, the browser address bar will display a **🔒 Secure** padlock.

---

## 🐳 Production Deployment (Docker)

The Docker Compose stack provisions: **Nginx** (SSL + reverse proxy), **Django** (Daphne), **Camera Service**, **Celery Worker**, **Redis**, and **LiveKit**.

```bash
# 1. Copy and configure environment
cp config/.env.example .env
#    → Set DEBUG=False, a strong SECRET_KEY, LiveKit credentials, etc.

# 2. Build and launch the full stack
docker-compose up --build -d

# 3. Apply database migrations
docker-compose exec web python manage.py migrate

# 4. Create the admin superuser
docker-compose exec web python manage.py createsuperuser

# 5. Tail logs
docker-compose logs -f
```

> Nginx handles SSL termination on port **443**. Django runs on port `8002` internally and is **not** exposed publicly. Nginx proxies `/ws/` and `/livekit-proxy/` as WebSocket upgrades.

---

## 🔢 Default Credentials & Ports

<div align="center">

| Service | Port | Protocol | Notes |
|---|---|---|---|
| Django / Daphne | **8002** | HTTPS / WSS | Main app — always use `https://` |
| Camera Service (Waitress) | **8003** | HTTP | AI microservice — internal only |
| LiveKit SFU | **7880** | WS / HTTP | WebRTC server — internal only |
| Redis | **6379** | TCP | Channel layer + Celery broker |
| Nginx (production) | **443** | HTTPS | Reverse proxy + SSL termination |

</div>

> **Default admin credentials:** Created during `python manage.py createsuperuser`. **No credentials are hardcoded** in the codebase.

> **Firewall:** Run `scripts\allow_firewall.bat` to open ports `8002` and `8003` in Windows Firewall for LAN access.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. **Fork** the repository
2. Create your branch: `git checkout -b feature/your-feature-name`
3. Commit your changes: `git commit -m 'feat: add some feature'`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Open a **Pull Request**

Please follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages.

---

<div align="center">

**Built for better classrooms.**

Run `.\start_app.bat` and go. 🚀

<br/>

<sub>Made with ❤️ by <a href="https://github.com/GAuravgiy87">GAuravgiy87</a> · <a href="https://github.com/tarunkumar-sys">tarunkumar-sys</a></sub>

</div>