<div align="center">

# 🚀 EduMi - Running Guide

### *Get Your Educational Platform Up and Running in Minutes*

<img src="https://img.shields.io/badge/Platform-EduMi-6366f1?style=for-the-badge" />
<img src="https://img.shields.io/badge/Status-Ready-success?style=for-the-badge" />

---

</div>

## 🎯 Overview

EduMi consists of two microservices that run simultaneously:

| Service | Port | Purpose |
|---------|------|---------|
| 🌐 **Main App** | 8000 | Authentication, meetings, dashboards, camera management |
| 📹 **Camera Service** | 8001 | RTSP & mobile camera streaming, live feeds |

---

## ⚡ Quick Start

### 🪟 Windows

Simply run the batch script:
```bash
./start_services.bat
```

### 🐧 Linux/Mac

Run the shell script:
```bash
chmod +x start_services.sh
./start_services.sh
```

> 💡 **Tip**: This automatically starts both services in separate terminal windows!

---

## 🎮 Manual Start

If you prefer to start services manually or need more control:

### Step 1: Start Camera Service

Open a terminal and run:
```bash
cd camera_service
python manage.py runserver 8001
```

### Step 2: Start Main App

Open another terminal and run:
```bash
python manage.py runserver 8000
```

---

## 🌐 Access the Application

Once both services are running:

| Service | URL | Description |
|---------|-----|-------------|
| 🏠 **Main Application** | http://localhost:8000 | Login, meetings, dashboards |
| 📹 **Camera Service API** | http://localhost:8001 | Camera streaming endpoints |

### 🔒 HTTPS for WebRTC (Camera/Mic Access)

**Important**: Meeting room features (camera, microphone, screen sharing) require HTTPS when accessing via IP address.

| Access Method | Works with HTTP? | Notes |
|---------------|------------------|-------|
| `localhost` or `127.0.0.1` | ✅ Yes | No HTTPS needed |
| IP address (e.g., `10.7.32.74`) | ❌ No | Requires HTTPS |

**To enable HTTPS for IP access:**

```bash
# Quick start with HTTPS
run_https.bat

# Or manually
python manage.py runserver_plus --cert-file cert 0.0.0.0:8000
```

Then access via:
- This computer: `https://localhost:8000`
- Other devices: `https://YOUR_IP:8000`

⚠️ You'll see a security warning (self-signed certificate) - click "Advanced" → "Proceed anyway"

📖 **See [MEETING_SETUP.md](MEETING_SETUP.md) for detailed HTTPS setup instructions**

---

## 🎬 First Time Setup

If this is your first time running EduMi:

### 1️⃣ Install Dependencies

```bash
# Main application dependencies
pip install -r requirements.txt

# Camera service dependencies
pip install -r camera_service/requirements.txt
```

### 2️⃣ Run Database Migrations

```bash
python manage.py migrate
```

### 3️⃣ Create Admin User (Optional)

```bash
python setup_admin.py
```

**Default credentials**:
- Username: `admin`
- Password: `admin123`

### 4️⃣ Create Test Users (Optional)

```bash
python setup_test_users.py
```

This creates sample teachers and students for testing.

---

## 🛑 Stopping the Services

### Using Scripts
- **Windows**: Close the command windows that opened
- **Linux/Mac**: Press `Ctrl+C` in the terminal running the script

### Manual Stop
Press `Ctrl+C` in each terminal window

---

## 🔧 General Troubleshooting

### ❌ Port Already in Use

**Error**: `Error: That port is already in use.`

**Solution**:

**Windows**:
```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

**Linux/Mac**:
```bash
# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or for port 8001
lsof -ti:8001 | xargs kill -9
```

---

### ❌ Camera Service Not Working

**Symptoms**:
- Camera feeds not loading
- 404 errors on camera endpoints

**Checklist**:
- ✅ Ensure both services are running
- ✅ Check camera service terminal for errors
- ✅ Verify CORS settings in `camera_service/camera_service/settings.py`
- ✅ Confirm database is accessible

---

### ❌ Database Issues

**Error**: `no such table` or migration errors

**Solution**:
```bash
# Run migrations
python manage.py migrate

# If issues persist, reset database (WARNING: deletes all data)
rm db.sqlite3
python manage.py migrate
python setup_admin.py
```

---

### ❌ WebSocket Connection Failed

**Symptoms**:
- Can't join meetings
- Real-time features not working

**Checklist**:
- ✅ Main app is running on port 8000
- ✅ Check browser console for errors
- ✅ Verify `ASGI_APPLICATION` in settings
- ✅ Ensure Channels is installed

---

### ❌ Module Not Found Errors

**Error**: `ModuleNotFoundError: No module named 'X'`

**Solution**:
```bash
# Reinstall dependencies
pip install -r requirements.txt
pip install -r camera_service/requirements.txt

# Or install specific package
pip install <package-name>
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    EduMi Platform                    │
├─────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────────────┐      ┌──────────────────┐    │
│  │  Main App :8000  │◄────►│ Camera Svc :8001 │    │
│  │                  │ CORS │                  │    │
│  │  • Auth          │      │  • RTSP Stream   │    │
│  │  • Meetings      │      │  • Live Feeds    │    │
│  │  • WebRTC        │      │  • OpenCV        │    │
│  │  • WebSocket     │      │                  │    │
│  └────────┬─────────┘      └────────┬─────────┘    │
│           │                         │               │
│           └──────────┬──────────────┘               │
│                      │                               │
│              ┌───────▼────────┐                     │
│              │  SQLite DB     │                     │
│              │  (Shared)      │                     │
│              └────────────────┘                     │
└─────────────────────────────────────────────────────┘
```

**Why Two Services?**

1. **Main App (ASGI)**: Needs WebSocket support for real-time meetings
2. **Camera Service (WSGI)**: Handles resource-intensive RTSP streaming
3. **Separation**: Prevents conflicts and improves performance

For more details, see [ARCHITECTURE.md](ARCHITECTURE.md)

---

## 📚 Additional Resources

| Document | Description |
|----------|-------------|
| [README.md](README.md) | Main project documentation |
| [UPDATE.md](UPDATE.md) | Complete changelog & fixes |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture |
| [SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md) | Detailed setup guide |

---

## 🎓 Common Use Cases

### Starting Development
```bash
./start_services.bat  # or .sh on Linux/Mac
```

### Running Tests
```bash
python manage.py test
```

### Creating New Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Accessing Admin Panel
1. Create superuser: `python manage.py createsuperuser`
2. Visit: http://localhost:8000/admin/

---

## 💡 Pro Tips

- 🔥 Use separate terminals to see logs from each service
- 📝 Check terminal output for errors and warnings
- 🔄 Restart services after code changes
- 🎯 Use browser DevTools to debug WebSocket connections
- 📊 Monitor database with SQLite browser tools

---

<div align="center">

### ✨ Happy Coding with EduMi!

**Need Help?** Check [UPDATE.md](UPDATE.md) for common issues and solutions

[⬆ Back to Top](#-edumi---running-guide)

</div>
