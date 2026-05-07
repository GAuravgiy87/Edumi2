# 🎓 Edumi2: AI-Powered Virtual Classroom & Attendance Ecosystem

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django 4.2](https://img.shields.io/badge/Django-4.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Redis](https://img.shields.io/badge/Redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![LiveKit](https://img.shields.io/badge/LiveKit-0052FF?style=for-the-badge&logo=livekit&logoColor=white)](https://livekit.io/)
[![WebRTC](https://img.shields.io/badge/WebRTC-333333?style=for-the-badge&logo=webrtc&logoColor=white)](https://webrtc.org/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-007808?style=for-the-badge&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![Nginx](https://img.shields.io/badge/Nginx-009639?style=for-the-badge&logo=nginx&logoColor=white)](https://nginx.org/)

**Edumi2** is a professional-grade educational platform that bridges the gap between high-performance video conferencing and academic integrity. By integrating **Real-Time AI Monitoring** (Face Recognition & Attention Tracking) with a scalable **WebRTC SFU**, Edumi2 provides a seamless, secure, and modern academic command center.

---

## ✨ Key Features

*   **🎥 HD Video Meetings**: Powered by **LiveKit SFU** for low-latency, high-quality WebRTC streaming.
*   **🧠 AI Attendance**: Mandatory biometric (Face-ID) verification for automated, fraud-proof attendance logging.
*   **📊 Engagement Analytics**: Real-time tracking of student focus based on head pose, eye aspect ratio (EAR), and presence.
*   **🛡️ Host Governance**: Comprehensive teacher console to mute, kick, or ban participants in real-time.
*   **📡 Global Signaling**: WebSocket-driven "No-Reload" experience for chat, notifications, and dashboard updates.
*   **📹 Camera Microservice**: Independent HLS proxy for RTSP/Mobile cameras to prevent main-thread blocking.

---

## 🚀 Getting Started

### 1. Prerequisites
*   Python 3.9+
*   Redis (installed and running)
*   LiveKit Server (Docker or Binary)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/GAuravgiy87/Edumi2.git
cd Edumi2

# Setup environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r camera_service/requirements.txt

# Initialize Database
python manage.py migrate
python setup_admin.py
```

### 3. Running the System
The easiest way to launch the entire ecosystem (Django, Daphne, Camera Service, and Ngrok) is using the master script:

**Windows (PowerShell):**
```powershell
./start_all.ps1
```

---

## 🔒 Security & Privacy
*   **No Photo Storage**: Edumi2 never stores raw images of students. It only saves mathematical **128-d face embeddings**.
*   **Encrypted Biometrics**: All embeddings are encrypted using **AES-256** at the database level.
*   **Secure Tunnels**: Mandatory **HTTPS/WSS** enforcement via Nginx/Ngrok for camera and microphone access.

---

## 🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request or open an Issue for feature requests and bug reports.

---

*Developed by GAuravgiy87 — Engineering the Future of Academic Interaction.*
