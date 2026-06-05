# 🎓 Edumi2: Complete Technical & Operational Manual

> **The Ultimate Guide for Developers, Administrators, and Stakeholders.**

---

## 📖 Table of Contents
1. [Project Overview](#-project-overview)
2. [Core Features](#-core-features)
3. [System Architecture (4-Layer Model)](#-system-architecture)
4. [Technology Stack](#-technology-stack)
5. [Module Deep Dive](#-module-deep-dive)
6. [Real-Time Signaling Hub](#-real-time-signaling-hub)
7. [App Flows (Step-by-Step)](#-app-flows)
8. [Developer Installation Guide](#-developer-installation-guide)
9. [Database & Security](#-database--security)
10. [Troubleshooting & Maintenance](#-troubleshooting)

---

## 🌟 Project Overview
**Edumi2** is a professional-grade educational ecosystem that bridges the gap between high-performance video conferencing and academic integrity. Unlike generic meeting tools, Edumi2 integrates **Real-Time AI Monitoring** (Face Recognition & Attention Tracking) and **Host Governance** into a seamless, modern academic command center.

---

## ✨ Core Features

### 🎥 Professional Video Meetings (LiveKit SFU)
- **High-Performance WebRTC**: Low-latency HD video/audio distribution.
- **Teacher Console**: Centralized dashboard to kick/ban students and mute all participants.
- **Granular Permissions**: Real-time server-side control over student hardware (Mic/Camera/Screen).
- **Interactive Tools**: Screen sharing, emoji reactions, and real-time chat with file attachments.

### 🧠 AI Attendance & Monitoring
- **Face ID Verification**: Mandatory biometric registration before joining any session.
- **Attention Tracking**: AI-driven focus scoring based on head pose and presence.
- **Automated Attendance**: Passive monitoring that logs student participation duration into the database.
- **Encryption**: All biometric data is encrypted and securely stored.

### ⚡ Real-Time Auto-Update System
- **Global Signal Bridge**: Uses WebSockets to push updates (messages, meeting starts, kicks) instantly.
- **No-Reload Experience**: Chat windows and dashboard stats update dynamically via AJAX/WebSocket.
- **Toast Notifications**: Non-intrusive alerts for system-wide events.

---

## 🏗️ System Architecture

Edumi2 follows a **4-Layer Decoupled Architecture** to ensure that heavy AI processing does not affect the video meeting quality.

```text
+-----------------------------------------------------------------------+
| LAYER 1: PRESENTATION (Clients & Edge Devices)                        |
|   [ Web Browser ] <----(WSS/WebRTC)----> [ Teacher/Student ]          |
|   [ IP Cameras  ] -----(RTSP/HTTP)-----> [ Classroom Hardware ]       |
+-----------------------------------------------------------------------+
              |                                 |
              v                                 v
+-----------------------------------------------------------------------+
| LAYER 2: GATEWAY & SECURITY (Traffic Management)                      |
|   [ Ngrok Tunnel ]  -> Secure HTTPS/WSS entry point                   |
|   [ Nginx Proxy  ]  -> Static asset delivery & Media serving          |
+-----------------------------------------------------------------------+
              |                                 |
              v                                 v
+-----------------------------------------------------------------------+
| LAYER 3: APPLICATION (Services & AI Logic)                            |
|   +------------------+   +------------------+   +------------------+  |
|   |   Main App       |   |  Camera Service  |   |  LiveKit SFU     |  |
|   | (Django/ASGI)    |   | (OpenCV / AI)    |   | (Media Engine)   |  |
|   +---------|--------+   +---------|--------+   +---------|--------+  |
|             |                      |                      |           |
|             +----------+-----------+----------------------+           |
|                        v                                              |
|             +-------------------+                                     |
|             |   Celery Worker   | -> Analytics & Background Tasks     |
|             +-------------------+                                     |
+-----------------------------------------------------------------------+
              |                                 |
              v                                 v
+-----------------------------------------------------------------------+
| LAYER 4: DATA & PERSISTENCE (Infrastructure)                            |
|   [ SQLite DB ]      -> Stores Users, Rooms, Attendance Records       |
|   [ Redis ]          -> Real-time Message Broker (Channels/Celery)    |
+-----------------------------------------------------------------------+
```

---

## 🛠️ Technology Stack

| Category | Technology | Usage |
|:---|:---|:---|
| **Backend** | Django 4.x / Python | Core logic, Auth, and RBAC. |
| **Real-Time** | Django Channels / Daphne | WebSocket management & Signaling. |
| **Media** | LiveKit / WebRTC | SFU-based video/audio streaming. |
| **AI/ML** | OpenCV / Face_Recognition | Identity & Engagement tracking. |
| **Database** | SQLite / Redis | Data persistence & Real-time cache. |
| **Frontend** | Vanilla JS / CSS3 / HTML5 | Modern, responsive Academic UI. |

---

## 🧩 Module Deep Dive

### 1. Accounts & Identity (`accounts`)
- **Profiles**: Extended User models with Face-ID registration.
- **Dashboards**: Separate "Command Centers" for Teachers and Students.
- **Notification Hub**: A WebSocket consumer that routes messages and alerts to specific users.

### 2. Meetings & Governance (`meetings`)
- **LiveKit Proxy**: An internal service that generates secure tokens for WebRTC sessions.
- **Host Controls**: Logic for kicking participants and enforcing 1-hour bans via `KickedParticipant`.
- **Signaling**: Custom WebSocket handlers (`kick_user`, `permission_update`) for real-time room management.

### 3. AI Monitoring & Attendance (`attendance`)
- **Face Recognition**: Matches live frames against student biometric encodings.
- **Attendance Service**: Background task that aggregates "Presence Minutes" into final logs.

### 4. Camera Microservice (`camera_service`)
- A standalone Django sub-project that handles RTSP/HTTP camera streams to prevent main-thread blocking.

---

## 📡 Real-Time Signaling Hub

The platform uses a **Global Signaling Bridge** to eliminate manual reloads:
1. **Mutation**: User performs an action (e.g., sends a message) via **AJAX**.
2. **Persistence**: Server saves the data to the database.
3. **Propagation**: Server broadcasts a WebSocket event to all relevant clients.
4. **Reception**: Clients receive the event via the `NotificationWS` and update their DOM instantly.

---

## 🔄 App Flows

### 🚀 Joining a Meeting
1. **Entry Check**: System checks if the user is in the `KickedParticipant` list (active ban).
2. **Identity Check**: Verifies if the user has a registered Face-ID profile.
3. **Token Generation**: Django requests a secure JWT from LiveKit.
4. **Handshake**: Browser establishes a WebRTC connection to the SFU via the token.

### 🚫 The "Kick & Ban" Flow
1. **Host Action**: Teacher clicks "Kick" in the participant list.
2. **Signal**: WebSocket event `kick_user` is sent to the server.
3. **Database**: A record is created in `KickedParticipant` with a 1-hour expiration.
4. **Execution**: The target student's socket is disconnected, and they are redirected to the dashboard.

---

## ⚙️ Developer Installation Guide

### 1. Prerequisites
- Python 3.9+
- Redis (installed and running)
- LiveKit Server (available via binary or Docker)

### 2. Setup Commands
```bash
# Clone and Environment
git clone https://github.com/GAuravgiy87/Edumi2.git
python -m venv .venv
.venv\Scripts\activate

# Install Dependencies
pip install -r requirements.txt
pip install -r camera_service/requirements.txt

# Database Init
python manage.py migrate
python setup_admin.py  # Default Admin: EdumiAdmin / Gaurav@0000
```

### 3. Running the System
The easiest way is to use the master script:
- **Windows**: Right-click `start_all.ps1` -> Run with PowerShell.

---

## 🔐 Database & Security
- **Models**:
    - `Meeting`: Stores room state and global overrides.
    - `MeetingParticipant`: Tracks individual permissions (A/V/S).
    - `KickedParticipant`: Enforces time-based bans.
- **Security**: 
    - HTTPS/WSS mandatory for WebRTC.
    - Face-ID authentication for attendance integrity.

---

## 🔧 Troubleshooting

| Issue | Solution |
|:---|:---|
| **Camera/Mic not working** | Use `start_all.ps1` to launch **Ngrok**. HTTPS is required. |
| **Database Locked** | Common in SQLite during heavy AI load. The built-in middleware handles retries. |
| **WebSocket Failure** | Ensure **Redis** is running. Check `settings.py` for `CHANNEL_LAYERS`. |

---

> **Developer Note**: To extend the system, focus on adding new WebSocket event types in `accounts/consumers.py` and updating the corresponding listeners in `base_sidebar.html`.

**Edumi2: Engineering the Future of Academic Interaction.**
