# 🛠️ EduMi Developer Workflow & Setup Guide

This document provides a step-by-step technical guide for developers to set up, extend, and maintain the EduMi platform.

---

## 1. Initial Environment Setup

### Step 1: Python Virtual Environment
It is recommended to use Python 3.12 for optimal performance and compatibility.
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

### Step 2: Dependency Orchestration
Install dependencies for both services.
```bash
# Main Service
pip install -r requirements.txt

# Camera Microservice
pip install -r camera_service/requirements.txt
```

### Step 3: Redis Installation
Redis is mandatory for the signaling server and task queue.
- **Windows**: Use Memurai or WSL2 to install Redis.
- **Linux**: `sudo apt install redis-server`

---

## 2. Database Initialization & Migration

### Step 1: Schema Application
Apply the models to the SQLite database.
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 2: Administrative Setup
Use the provided setup script to create the initial environment.
```bash
python setup_admin.py
```
*Default Credentials: Username: `EdumiAdmin` | Password: `Gaurav@0000`*

---

## 3. Local Development Execution

### Execution Mode A: Multi-Terminal (Logs Visible)
**Terminal 1 (Redis):**
```bash
redis-server
```

**Terminal 2 (Camera Service):**
```bash
cd camera_service
python manage.py runserver 8001
```

**Terminal 3 (Main App):**
```bash
python manage.py runserver 8000
```

### Execution Mode B: Integrated (Quick Start)
```bash
./start_services.bat
```

---

## 4. Feature Development Lifecycle

### Step 1: Modifying Real-time Logic
When modifying `meetings/consumers.py`:
1. Update the `MeetingConsumer` class.
2. Ensure any database operations use `@database_sync_to_async`.
3. Restart the Django server to clear the Channel Layer cache.

### Step 2: Extending the Data Model
When adding fields to `Account` or `Meeting` models:
1. Update `models.py`.
2. Run `python manage.py makemigrations <app_name>`.
3. Apply changes with `python manage.py migrate`.

### Step 3: Frontend Styling
The design system uses Vanilla CSS for maximum performance:
- Navigation/Layout: `static/css/sidebar.css`
- Meeting Space: `static/css/meeting-room.css`
- Component Logic: `static/js/meeting_room.js`

---

## 5. Testing & Quality Assurance

### Step 1: Internal Unit Tests
```bash
python manage.py test meetings
python manage.py test accounts
```

### Step 2: Network & HTTPS Simulation
Because WebRTC requires HTTPS for non-localhost access, use Ngrok for mobile camera testing:
```bash
ngrok http 8000
```
Then update your `CSRF_TRUSTED_ORIGINS` in `settings.py` if the domain changes.

---

## 6. Troubleshooting Common Issues

| Issue | Reason | Solution |
| :--- | :--- | :--- |
| **WebSocket Disconnect** | Redis not running | Ensure `redis-server` is active on port 6379. |
| **Camera Feed Black** | CORS mismatch | Check `ALLOWED_HOSTS` in `camera_service/settings.py`. |
| **Parse Errors** | Null byte corruption | Run the cleanup script or check for hidden characters in `.py` files. |
| **2FA Lockout** | Secret key lost | Use `python manage.py shell` to disable 2FA for the user. |

---
*EduMi Technical Operations Guide - 2026*
