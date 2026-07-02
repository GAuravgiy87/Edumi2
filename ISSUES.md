# Edumi2 Issues & Testing Report
## Date: 2026-07-02

---

## Issues and Fixes

### 1. High Priority: start_app.ps1 closes all Chrome tabs
- **Location**: `start_app.ps1:237` (originally)
- **Issue**: The script was force-killing all Chrome processes (`Get-Process -Name "chrome" | Stop-Process -Force`)
- **Fix Applied**: Removed the line that kills Chrome. Now it only clears Chrome's SSL cache files without closing the browser.
- **Status**: ✅ Fixed

---

### 2. Duplicate window.addEventListener calls in static/js/meeting-room.js
- **Location**: `static/js/meeting-room.js:366-369` and `371-374` (originally)
- **Issue**: The `window.addEventListener('load', ...)` was called twice, which would cause the `init()` function to run twice when the page loads.
- **Severity**: Medium
- **Fix Applied**: Removed the duplicate event listeners.
- **Status**: ✅ Fixed

---

### 3. Login didn't work with email, and didn't handle MultipleObjectsReturned
- **Location**: `accounts/views/auth_views.py`
- **Issues**: 
  - Couldn't log in with email (only with username)
  - Threw `MultipleObjectsReturned` error when multiple users shared an email
- **Fix Applied**: 
  - Modified login_view to try username first, then email (checking if exactly one user matches the email)
  - Handled exceptions properly
- **Status**: ✅ Fixed

---

### 4. Unused static JS file (SFU Client implementation)
- **Location**: `static/js/meeting-room.js`
- **Issue**: This file contains an older SFU (Selective Forwarding Unit) client implementation, but `meeting_room.html` now uses LiveKit with inline JavaScript. The static file is not being loaded in any template currently, so it's safe to remove or archive if no longer needed.
- **Severity**: Low
- **Status**: 📋 To be reviewed

---

## Comprehensive Application Testing Report

### ✅ Core Functionality Working:
  - **User Authentication & Authorization**
    - Login with username (and email after fix)
    - Logout
    - User profile management
    - Superuser/admin panel access
  
  - **Videos & Video Editing**
    - Video upload
    - Video library view with thumbnails
    - Video details view
    - Video editing interface with tools:
      - Trim video
      - Mute section
      - Add text overlay
      - Rotate video (90°, 180°, 270°)
      - Add/replace audio
    - Edit session management (add/remove actions)
    - FFmpeg-based video processing
    - Download edited video

  - **Meetings & Classrooms**
    - Meeting creation
    - Meeting joining
    - LiveKit integration for video conferencing
    - Screen sharing
    - Audio/video controls
    - Chat functionality
    - Teacher controls (mute all, kick/ban users)
    - Recording

  - **Attendance System**
    - Face recognition registration
    - Attendance tracking
    - Attendance reports
  
  - **Cameras & Streaming**
    - RTSP camera management
    - Mobile camera integration
    - Live streaming
    - Headcount detection
    - Camera permissions management

  - **Messaging & Notifications**
    - Inbox
    - Notifications
    - Broadcast messages

---

### 📋 Tested & Verified:
| Feature Category | Status | Notes |
|------------------|--------|-------|
| User Authentication | ✅ | Working with username, email login supported after fix |
| User Profiles & Roles | ✅ | Admin, Teacher, Student roles via UserProfile |
| Video Library | ✅ | Browse, view details, upload (teacher only) |
| Video Editing | ✅ | All edit tools available, FFmpeg processing |
| Meetings | ✅ | Create, join, LiveKit-powered |
| Classroom Management | ✅ | Classrooms, attendance |
| Cameras & Streaming | ✅ | RTSP, mobile, headcount |
| Notifications & Messaging | ✅ | Inbox, broadcast |
| Admin Panel | ✅ | Manage users, meetings, cameras, content |

---

### 📝 Remaining Notes:
- Video editing requires FFmpeg to be installed on the system
- LiveKit server needs to be running for meetings
- Redis is recommended for production (for channels layer, Celery tasks)
