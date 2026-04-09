<div align="center">

<img src="static/logo.svg" alt="EduMi Logo" width="400" />

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=28&duration=2800&pause=2000&color=6366F1&center=true&vCenter=true&width=940&lines=Edumi2+-+Real-Time+AI+Monitoring+%26+Meetings;Built+for+Schools+%26+Universities;WebRTC+%7C+Django+%7C+OpenCV+%7C+Face+Recognition" alt="Typing SVG" />

<p align="center">
  <img src="https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/WebRTC-333333?style=for-the-badge&logo=webrtc&logoColor=white" />
  <img src="https://img.shields.io/badge/Face_Recognition-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

<p align="center">
  <img src="https://img.shields.io/github/license/GAuravgiy87/Edumi2?style=flat-square&color=6366f1" />
  <img src="https://img.shields.io/badge/version-2.0.0-blue?style=flat-square" />
  <img src="https://img.shields.io/badge/status-active-success?style=flat-square" />
</p>

### ✨ *Where Learning Meets Innovation* ✨

<img src="https://user-images.githubusercontent.com/74038190/212284100-561aa473-3905-4a80-b561-0d28506553ee.gif" width="700">

---

> 🎥 **Camera/Mic Not Working on IP Address?**  
> WebRTC requires HTTPS on non-localhost. Use **ngrok** (Option 1) or **run_https.bat** (Option 2) for local network testing.

---

[Features](#-features) • [Quick Start](#-quick-start) • [Installation](#-installation) • [Architecture](#-architecture) • [Troubleshooting](#-troubleshooting)

</div>

---

## 🌟 Features

<table>
<tr>
<td width="50%">

### 👥 AI Attendance & Monitoring
```
✓ Face Recognition powered attendance
✓ Real-time focus tracking
✓ Presence detection (Cumulative verification)
✓ Secure face encryption
✓ Headcount monitoring service
```

</td>
<td width="50%">

### 🎥 Real-Time Video Meetings
```
✓ HD video conferencing via WebRTC
✓ Screen sharing (4K @ 60fps support)
✓ Dynamic Google Meet style layout
✓ In-meeting chat & emoji support
✓ Optimized for zero latency
```

</td>
</tr>
<tr>
<td width="50%">

### 📹 Camera Management
```
✓ RTSP & IP Camera integration
✓ Dedicated camera microservice
✓ Multi-camera live-feed monitoring
✓ OpenCV optimized processing
✓ Mobile camera support (DroidCam/IP Webcam)
```

</td>
<td width="50%">

### 🔐 Advanced User Control
```
✓ Role-based access (Teacher/Student/Admin)
✓ Secure Django auth with Staff/Superuser
✓ Meeting permissions & codes
✓ Detailed user profiles with bio/avatars
✓ Interactive admin dashboard
```

</td>
</tr>
</table>

<div align="center">
<img src="https://user-images.githubusercontent.com/74038190/212284115-f47cd8ff-2ffb-4b04-b5bf-4d1c14c0247f.gif" width="1000">
</div>

---

## 🚀 Quick Start (Windows)

The simplest way to run **Edumi2** on Windows using the pre-configured scripts:

1.  **Start Core Services**: Double-click `start_network.bat`.
    *   This starts the **Main App** (Port 8000) and **Camera Service** (Port 8001).
2.  **Enable HTTPS (for Camera/Mic)**:
    *   **Option A**: Run `start_ngrok.bat` (Requires ngrok.exe in root).
    *   **Option B**: Double-click `run_https.bat`.
3.  **Access**:
    *   URL: `http://localhost:8000`
    *   Default Admin: **EdumiAdmin** / **Gaurav@0000**

---

## 📦 Installation

To set up **Edumi2** manually from scratch:

### 1. Clone the Repository
```bash
git clone https://github.com/GAuravgiy87/Edumi2.git
cd Edumi2
```

### 2. Environment Setup
Create a virtual environment to keep dependencies isolated:
```bash
# Create environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
pip install -r camera_service/requirements.txt
```

### 4. Database Setup
```bash
# Run migrations
python manage.py migrate

# Initialize Admin User & Default Data
python setup_admin.py
```
*Note: Default credentials will be created (EdumiAdmin / Gaurav@0000).*

---

## 🏗️ Architecture

<div align="center">

```mermaid
graph TB
    A[🧑‍💻 User Browser] -->|HTTP/WebSocket| B[🌐 Main App :8000]
    A -->|Camera Feeds| C[📹 Camera Service :8001]
    B -->|ASGI/Channels| D[🔌 WebSocket Server]
    B -->|Shared DB| E[(💾 SQLite)]
    C -->|Shared DB| E
    C -->|RTSP/OpenCV| F[📷 IP & Mobile Cameras]
    D -->|WebRTC| G[🎥 Video Meetings]
    
    style A fill:#6366f1,stroke:#4f46e5,color:#fff
    style B fill:#10b981,stroke:#059669,color:#fff
    style C fill:#f59e0b,stroke:#d97706,color:#fff
    style D fill:#8b5cf6,stroke:#7c3aed,color:#fff
    style E fill:#ec4899,stroke:#db2777,color:#fff
    style F fill:#06b6d4,stroke:#0891b2,color:#fff
    style G fill:#ef4444,stroke:#dc2626,color:#fff
```

</div>

### Component Overview
- **Main App (Port 8000)**: Handles Django logic, Authentication, Meetings, and Core Management.
- **Camera Service (Port 8001)**: A dedicated microservice for high-performance RTSP streaming and processing.
- **Daphne/Channels**: Powers the real-time WebSocket communication and WebRTC signaling.
- **OpenCV/Face Recognition**: Handles the AI monitoring and attendance logic.

---

## 🔧 Debugging & Troubleshooting

### ❌ Camera/Mic Permission Issues
- **Problem**: "NotAllowedError" or camera doesn't start.
- **Cause**: WebRTC requires **HTTPS** on all connections except `localhost`.
- **Debug Steps**:
    1.  Ensure you are using `https://` if accessing via IP (e.g., `10.17.2.47`).
    2.  Run `run_https.bat` to bypass security warnings locally.
    3.  Check browser site settings to ensure microphone/camera permissions are set to "Allow".

### ❌ Database Locked (SQLite)
- **Problem**: `django.db.utils.OperationalError: database is locked`.
- **Cause**: Multi-threaded access to SQLite during high-concurrency tasks (like face recognition updates).
- **Debug Steps**:
    1.  The project includes `DatabaseErrorMiddleware` to handle these automatically.
    2.  If persistent, clear active sessions: `del db.sqlite3` and rerun `python manage.py migrate`.

### ❌ Port Conflict
- **Problem**: `Error: [WinError 10048] Only one usage of each socket address...`.
- **Cause**: Port 8000 or 8001 is already being used.
- **Debug Steps (Windows)**:
    ```bash
    netstat -ano | findstr :8000
    taskkill /F /PID <PID_Found>
    ```

### ❌ WebSocket/Redis Issues
- **Problem**: Connection rejected or chat/video not initializing.
- **Cause**: Redis server not running or `channels_redis` not connected.
- **Debug Steps**:
    1.  Ensure Redis is started (if using Linux or Docker).
    2.  In Windows, verify the `CHANNEL_LAYERS` in `settings.py` points to a running instance or use the fallback.

---

## 🧹 Maintenance & Hygiene
This project has recently undergone significant refactoring to improve performance:
- **Removed Redundant Scripts**: Cleaned up the root directory by removing 15+ unused/isolated scripts and temporary logs.
- **Consolidated Docs**: All setup guides and technical specs are now found in the `/docs` folder.
- **Clean State**: Auto-cleanup of `__pycache__` and `.pyc` files is performed periodically to keep the repository light.

---

## 📝 License
This project is licensed under the MIT License.

## 🙏 Acknowledgments
- **Gaurav Chauhan** - Core Developer
- **Django Project** for the robust framework.
- **OpenCV & Face_Recognition** for the AI capabilities.

<div align="center">

**[⬆ Back to Top](#edumi2)**

<p>
<img src="https://img.shields.io/badge/Made%20with-Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/Powered%20by-Django-092E20?style=for-the-badge&logo=django&logoColor=white" />
<img src="https://img.shields.io/badge/AI--Powered-Face--Recognition-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" />
</p>

<sub>⭐ Star this repo if you find it helpful!</sub>

</div>
