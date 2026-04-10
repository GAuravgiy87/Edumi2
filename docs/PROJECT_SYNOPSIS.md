# PROJECT SYNOPSIS

---

## 1. Title of the Project

**EduMi — AI-Powered Smart Classroom Platform with Real-Time Video Conferencing, Face Recognition Attendance & Intelligent Campus Monitoring**

---

## 2. Introduction

EduMi is a comprehensive, AI-driven educational platform designed specifically for schools and universities. It integrates real-time video conferencing, automated face recognition-based attendance, student engagement analysis, and live campus camera monitoring into a single unified web application.

The rapid growth of digital education has created a demand for intelligent systems that go beyond simple video calls. Traditional e-learning tools lack automated attendance, engagement tracking, and security monitoring. EduMi addresses this gap by combining WebRTC-based video conferencing with computer vision and machine learning to deliver a smart, automated, and secure virtual classroom experience.

With the rise of hybrid and remote learning environments, institutions need platforms that reduce administrative overhead, ensure academic integrity, and provide real-time insights into student participation — all of which EduMi delivers.

---

## 3. Problem Statement

### What problem are we solving?

Educational institutions conducting online or hybrid classes face several critical challenges:

- **Manual Attendance is Inefficient:** Teachers must manually mark attendance during online sessions, which is time-consuming, error-prone, and easily manipulated by students.
- **No Engagement Visibility:** Existing platforms (Zoom, Google Meet) provide no insight into whether students are actually paying attention or are distracted.
- **Lack of Campus Security Integration:** There is no unified system that connects virtual classrooms with physical campus camera monitoring.
- **Identity Verification Gaps:** Students can join meetings without proper identity verification, enabling proxy attendance.
- **Fragmented Tools:** Institutions use separate tools for video calls, attendance registers, and security cameras — leading to data silos and administrative burden.

### Why is it important?

Academic integrity, student engagement, and campus safety are foundational to quality education. Automating these processes saves hundreds of hours of administrative work per semester and provides data-driven insights that improve teaching outcomes.

- **No Dedicated Classroom Ownership:** Generic platforms like Zoom or Google Meet do not give teachers a persistent, owned classroom space. Every session requires a new link, new setup, and students have no fixed "home" classroom to return to. There is no concept of a teacher owning a classroom with a permanent class code, controlled membership, and session history.
- **No Student Approval Workflow:** Anyone with a meeting link can join. There is no mechanism for a teacher to review, approve, or deny individual students before they enter the virtual classroom.
- **No Persistent Classroom Identity:** When a meeting ends, all context is lost. There are no persistent classrooms that carry forward schedules, membership lists, attendance history, and engagement data across multiple sessions.

### Current Issues in Existing Systems

| Existing System | Limitation |
|---|---|
| Zoom / Google Meet | No persistent classrooms, no attendance automation, no engagement tracking |
| Manual Attendance Registers | Prone to proxy, time-consuming, no analytics |
| Standalone CCTV Systems | Not integrated with academic workflows |
| LMS Platforms (Moodle, etc.) | No real-time video or AI-based monitoring |
| Generic Video Platforms | No teacher-owned classroom with join approval, class codes, or session history |

---

## 4. Objectives

- Automate student attendance using real-time face recognition during live video sessions
- Provide HD video conferencing with WebRTC tailored for classroom environments
- Track and report student engagement levels (focused, distracted, tired, confused) per session
- Integrate RTSP and mobile IP cameras for live campus head-count monitoring
- Implement role-based access control for teachers, students, and administrators
- Secure all biometric data using AES-256 encryption with no raw image storage
- Enable teachers to manage virtual classrooms with join-request approval workflows
- Provide real-time notifications, in-meeting chat, and direct messaging
- Generate automated post-meeting attendance and engagement reports
- Support two-factor authentication (2FA) for enhanced account security
- Reduce teacher administrative workload through full automation of attendance workflows
- Deliver a scalable, containerized deployment using Docker

---

## 5. Scope of the Project

### Where the project can be used

- Schools and universities conducting online or hybrid classes
- Corporate training environments requiring attendance tracking
- Examination centers needing identity verification
- Campus security teams monitoring physical spaces via IP cameras
- Educational administrators requiring engagement analytics and reports

### Limitations (What it will NOT do)

- Will not replace a full Learning Management System (LMS) with course content delivery
- Will not perform real-time emotion analysis on audio/voice
- Will not support mobile native apps (iOS/Android) — web browser only
- Will not function without a stable internet connection (WebRTC requires connectivity)
- Will not store raw face images for recognition — only encrypted numerical embeddings
- Will not support more than one face per student registration frame
- Face recognition accuracy may degrade in very low-light environments without enhancement
- Will not integrate with third-party SIS (Student Information Systems) out of the box

---

## 6. Methodology / Working

### System Process Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EduMi SYSTEM FLOW                            │
└─────────────────────────────────────────────────────────────────────┘

  [USER REGISTRATION]
       │
       ▼
  Student/Teacher registers → Role assigned (Student / Teacher / Admin)
       │
       ▼
  Student registers face → Webcam capture → 128-d embedding extracted
       │                                          │
       │                              AES-256 encrypted → stored in DB
       │                              (No raw image stored)
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                    CLASSROOM WORKFLOW                           │
  │                                                                 │
  │  Teacher creates Classroom (class code + password)             │
  │       │                                                         │
  │       ▼                                                         │
  │  Student requests to join → Teacher approves/denies            │
  │       │                                                         │
  │       ▼                                                         │
  │  Teacher starts Meeting → Meeting goes LIVE                    │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                  LIVE MEETING (WebRTC + WebSocket)              │
  │                                                                 │
  │  Participants connect via WebRTC (P2P video/audio)             │
  │       │                                                         │
  │       ▼                                                         │
  │  WebSocket: ws/meeting/<code>/  ← signaling, chat, controls    │
  │  WebSocket: ws/attendance/<code>/ ← face recognition frames    │
  │  WebSocket: ws/face-tracking/<code>/ ← engagement snapshots   │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │              FACE RECOGNITION ATTENDANCE PIPELINE               │
  │                                                                 │
  │  Every N seconds → Student webcam frame sent via WebSocket     │
  │       │                                                         │
  │       ▼                                                         │
  │  Liveness Check → pixel variance > 6.0 (anti-spoofing)        │
  │       │                                                         │
  │       ▼                                                         │
  │  Face Detection (HOG model) → Quality Score check             │
  │       │                                                         │
  │       ▼                                                         │
  │  128-d Embedding extracted (large model, 68 landmarks)         │
  │       │                                                         │
  │       ▼                                                         │
  │  Decrypt stored embedding → Cosine similarity comparison       │
  │       │                                                         │
  │       ▼                                                         │
  │  Rolling Vote Buffer (2 consecutive matches required)          │
  │       │                                                         │
  │       ├── MATCH → Cumulative presence timer increments         │
  │       │           (default: 30s threshold → marked Present)    │
  │       │                                                         │
  │       └── NO MATCH → Frame logged, timer paused               │
  │                                                                 │
  │  Late detection: if marked after threshold → status = Late     │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │              ENGAGEMENT TRACKING PIPELINE                       │
  │                                                                 │
  │  Per-frame emotion detection → snapshot stored                 │
  │  Emotions: focused / happy / tired / confused / distracted     │
  │       │                                                         │
  │       ▼                                                         │
  │  Meeting ends → EngagementReport auto-generated                │
  │  Per-student engagement score + class-wide average             │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │              CAMERA MONITORING (Parallel System)                │
  │                                                                 │
  │  RTSP / Mobile IP Cameras → OpenCV frame capture               │
  │       │                                                         │
  │       ▼                                                         │
  │  HOG + Haar Cascade detection → Head count per frame           │
  │       │                                                         │
  │       ▼                                                         │
  │  Stabilized count (15-frame history) → HeadCountLog saved      │
  │  Snapshot image stored → Dashboard display                     │
  └─────────────────────────────────────────────────────────────────┘
```

### System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         EduMi ARCHITECTURE                               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────┐    HTTPS/WSS     ┌──────────────────────────────────┐ │
│   │   Browser   │ ◄─────────────► │         Nginx Reverse Proxy       │ │
│   │  (WebRTC)   │                  │           (Port 80/443)           │ │
│   └─────────────┘                  └──────────────┬───────────────────┘ │
│                                                   │                      │
│                              ┌────────────────────▼──────────────────┐  │
│                              │     Daphne ASGI Server (Port 8000)    │  │
│                              │         Django Channels 4.0           │  │
│                              │                                        │  │
│                              │  ┌──────────┐  ┌──────────────────┐  │  │
│                              │  │  HTTP    │  │   WebSocket      │  │  │
│                              │  │ Views    │  │   Consumers      │  │  │
│                              │  └────┬─────┘  └────────┬─────────┘  │  │
│                              └───────┼──────────────────┼────────────┘  │
│                                      │                  │               │
│         ┌────────────────────────────▼──────────────────▼────────────┐  │
│         │                    Django Apps                              │  │
│         │  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌───────────┐  │  │
│         │  │ accounts │ │ meetings │ │ attendance │ │  cameras  │  │  │
│         │  └──────────┘ └──────────┘ └────────────┘ └───────────┘  │  │
│         └────────────────────────┬──────────────────────────────────┘  │
│                                  │                                       │
│              ┌───────────────────┼───────────────────┐                  │
│              │                   │                   │                  │
│    ┌─────────▼──────┐  ┌─────────▼──────┐  ┌────────▼───────┐         │
│    │  SQLite / DB   │  │  Redis Cache   │  │ Celery Workers │         │
│    │  (ORM Models)  │  │  (Channels +   │  │ (Async Tasks)  │         │
│    └────────────────┘  │   Cache Layer) │  └────────────────┘         │
│                         └────────────────┘                              │
│                                                                          │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │          Camera Microservice (Port 8001)                         │  │
│   │   OpenCV ← RTSP Cameras / Mobile IP Cameras (IP Webcam)         │  │
│   └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Technologies Used

### Programming Languages
| Language | Usage |
|---|---|
| Python 3.x | Backend, AI/ML pipeline, camera processing |
| JavaScript (ES6+) | Frontend, WebRTC signaling, WebSocket client |
| HTML5 / CSS3 | UI templates |
| SQL | Database queries via Django ORM |

### Frameworks & Libraries
| Technology | Version | Purpose |
|---|---|---|
| Django | 4.2.9 | Web framework, ORM, admin |
| Django Channels | 4.0.0 | WebSocket / ASGI support |
| Daphne | 4.0.0 | ASGI server |
| Celery | 5.3.6 | Asynchronous task queue |
| OpenCV | 4.8.1.78 | Camera feed processing, head detection |
| face_recognition | 1.3.0 | 128-d face embedding extraction |
| NumPy | ≥1.26.0 | Numerical computation for embeddings |
| Pillow | 10.2.0 | Image processing |
| cryptography (Fernet) | ≥42.0.0 | AES-256 face embedding encryption |
| openpyxl | ≥3.1.2 | Excel report generation |
| django-otp | 1.2.4 | Two-factor authentication |
| django-two-factor-auth | 1.15.5 | 2FA UI and flow |
| django-cors-headers | 4.3.1 | CORS policy management |
| channels-redis | 4.1.0 | Redis channel layer |
| requests | 2.31.0 | HTTP client for microservice calls |

### Infrastructure & DevOps
| Technology | Purpose |
|---|---|
| Redis | Message broker (Channels), caching |
| Docker & Docker Compose | Containerized deployment |
| Nginx | Reverse proxy, SSL termination |
| ngrok | HTTPS tunneling for WebRTC (dev/demo) |
| SQLite | Development database (PostgreSQL-ready) |

### AI / Machine Learning
| Component | Technology |
|---|---|
| Face Detection | HOG (Histogram of Oriented Gradients) |
| Face Encoding | 128-d deep metric learning (dlib large model, 68 landmarks) |
| Liveness Detection | Pixel variance + motion diff (anti-spoofing) |
| Head Detection | HOG People Detector + Haar Cascades (frontal, profile, upper body) |
| Engagement Analysis | Emotion classification from facial expressions |
| Low-light Enhancement | Custom NumPy-based image enhancement |

### Communication Protocols
| Protocol | Usage |
|---|---|
| WebRTC | Peer-to-peer video/audio conferencing |
| WebSocket (WSS) | Real-time signaling, attendance, chat |
| RTSP | IP camera video stream ingestion |
| HTTP/HTTPS | REST API and page serving |


### Hardware–Software Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  HARDWARE ↔ SOFTWARE INTERACTION                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐   USB / UVC    ┌─────────────────────────────────┐   │
│  │  HD Webcam   │ ─────────────► │  Browser (WebRTC getUserMedia)  │   │
│  │ (Student /   │                │  → Face frames via WebSocket    │   │
│  │  Teacher)    │                │  → Video stream via WebRTC P2P  │   │
│  └──────────────┘                └──────────────┬──────────────────┘   │
│                                                 │ HTTPS / WSS           │
│  ┌──────────────┐   RTSP/TCP     ┌──────────────▼──────────────────┐   │
│  │  IP Camera   │ ─────────────► │   Camera Microservice (8001)    │   │
│  │  (Campus)    │                │   OpenCV → Head Detection       │   │
│  └──────────────┘                │   HOG + Haar Cascade            │   │
│                                  └──────────────┬──────────────────┘   │
│  ┌──────────────┐  HTTP/MJPEG                   │                       │
│  │  Smartphone  │ ─────────────►  (same above)  │                       │
│  │ (IP Webcam)  │                               │                       │
│  └──────────────┘                               │                       │
│                                  ┌──────────────▼──────────────────┐   │
│                                  │   Django Backend (Port 8000)    │   │
│                                  │   Daphne ASGI + Channels        │   │
│                                  │   Face Recognition Pipeline     │   │
│                                  │   Attendance & Engagement DB    │   │
│                                  └──────────────┬──────────────────┘   │
│                                                 │                       │
│                                  ┌──────────────▼──────────────────┐   │
│                                  │  Redis (Cache + Channel Layer)  │   │
│                                  │  SQLite / PostgreSQL (Database) │   │
│                                  │  Celery (Async Task Workers)    │   │
│                                  └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Literature Review

### Related Work & Existing Research

**1. Automated Attendance Using Face Recognition (2018–2023)**
Multiple research papers (IEEE, Springer) have demonstrated face recognition-based attendance systems using OpenCV and dlib. Most implementations are offline desktop applications. EduMi extends this concept to a real-time, web-based, encrypted, and anti-spoofing-aware system integrated directly into a video conferencing platform.

**2. WebRTC-Based E-Learning Platforms**
Studies on WebRTC for education (e.g., "WebRTC for Real-Time Communication in E-Learning," IJCA 2020) confirm low-latency peer-to-peer video is viable for classrooms. Existing platforms like Jitsi Meet and BigBlueButton provide video but lack AI-based attendance or engagement tracking.

**3. Student Engagement Detection**
Research published in journals like Computers & Education has explored using facial action units and emotion recognition to measure student engagement. EduMi implements a practical version of this using per-frame emotion snapshots aggregated into engagement reports.

**4. Campus Surveillance & Head Counting**
HOG-based pedestrian detection (Dalal & Triggs, CVPR 2005) remains a widely used baseline for head counting in surveillance. EduMi uses this combined with Haar cascades for robust multi-angle detection in campus camera feeds.

**5. Biometric Data Security**
GDPR and FERPA compliance research emphasizes that biometric data must be encrypted at rest. EduMi implements Fernet (AES-256) encryption for all face embeddings, storing only encrypted binary data — no raw images — aligning with best practices in biometric data protection.

---

## 9. Expected Outcome

Upon successful completion and deployment, EduMi is expected to:

- Reduce attendance marking time from ~5 minutes per class to zero (fully automated)
- Achieve face recognition accuracy of 90%+ under normal lighting conditions with the 0.55 cosine similarity threshold
- Provide teachers with per-student and class-wide engagement reports after every session
- Enable real-time head count monitoring across multiple campus cameras simultaneously
- Support concurrent virtual classrooms with multiple teachers and student groups
- Eliminate proxy attendance through liveness detection and rolling vote verification
- Generate downloadable Excel attendance and engagement reports for administrative use
- Provide a secure, role-based platform where student biometric data is never exposed in raw form
- Reduce overall administrative workload for attendance management by an estimated 80%

---

## 10. Hardware & Software Requirements

### Hardware Requirements

| Component | Minimum Specification | Recommended |
|---|---|---|
| Server / Host Machine | Intel Core i5, 8GB RAM | Intel Core i7/i9, 16GB+ RAM |
| Webcam (Student/Teacher) | 720p HD webcam | 1080p webcam |
| IP / RTSP Camera | Any RTSP-compatible IP camera | 1080p RTSP camera (H.264) |
| Mobile Camera | Android phone with IP Webcam app | Any modern Android/iOS device |
| Network | 10 Mbps broadband | 50+ Mbps for multi-user |
| Storage | 20 GB free disk space | 100 GB SSD |
| GPU (Optional) | — | NVIDIA GPU for faster face recognition |

### Software Requirements

| Category | Requirement |
|---|---|
| Operating System | Windows 10/11, Ubuntu 20.04+, macOS 12+ |
| Python | Python 3.10 or higher |
| Database | SQLite (dev), PostgreSQL 14+ (production) |
| Cache / Broker | Redis 6.0+ |
| Container Runtime | Docker 24+, Docker Compose v2 |
| Web Browser | Chrome 90+, Firefox 88+, Edge 90+ (WebRTC support required) |
| Build Tools | CMake, C++ compiler (for face_recognition / dlib on Windows) |
| HTTPS | SSL certificate or ngrok for WebRTC on non-localhost |

---

## 11. Timeline / Project Plan

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROJECT TIMELINE — JAN to APR                            │
├──────────────┬──────────────────────────────────────────────────────────────┤
│    MONTH     │                        TASKS                                 │
├──────────────┼──────────────────────────────────────────────────────────────┤
│              │  • Project requirement gathering & analysis                  │
│   JANUARY    │  • System architecture design                                │
│  (Planning & │  • Database schema design (models for all apps)              │
│   Design)    │  • UI/UX wireframes for classroom, attendance, camera views  │
│              │  • Technology stack finalization                             │
│              │  • Development environment setup (Django, Redis, Docker)     │
├──────────────┼──────────────────────────────────────────────────────────────┤
│              │  • User authentication system (login, register, roles)       │
│  FEBRUARY    │  • Classroom & meeting management module                     │
│ (Core Dev —  │  • WebRTC video conferencing integration                     │
│  Backend)    │  • WebSocket consumers (meeting signaling, chat)             │
│              │  • Face registration pipeline (capture → encrypt → store)   │
│              │  • Face recognition attendance consumer (WebSocket)          │
├──────────────┼──────────────────────────────────────────────────────────────┤
│              │  • RTSP & mobile camera integration (OpenCV)                 │
│    MARCH     │  • Head counting service (HOG + Haar cascade)                │
│  (Advanced   │  • Engagement tracking & emotion detection                   │
│  Features)   │  • Engagement report auto-generation (post-meeting)          │
│              │  • Notifications, messaging, admin dashboard                 │
│              │  • 2FA implementation (django-otp)                           │
├──────────────┼──────────────────────────────────────────────────────────────┤
│              │  • End-to-end system testing (all modules)                   │
│    APRIL     │  • Bug fixing, performance optimization                      │
│  (Testing &  │  • Docker containerization & deployment                      │
│  Deployment) │  • Excel report generation & export                         │
│              │  • Documentation finalization                                │
│              │  • Final demo & project submission                           │
└──────────────┴──────────────────────────────────────────────────────────────┘
```

### Detailed Monthly Task Table

| Phase | Month | Task | Duration |
|---|---|---|---|
| Planning | January Week 1 | Requirements gathering, scope definition | 1 week |
| Planning | January Week 2 | System architecture & DB schema design | 1 week |
| Planning | January Week 3–4 | UI wireframes, tech stack setup, environment config | 2 weeks |
| Development | February Week 1 | User auth, profiles, role-based access | 1 week |
| Development | February Week 2 | Classroom creation, membership, meeting management | 1 week |
| Development | February Week 3 | WebRTC conferencing + WebSocket signaling | 1 week |
| Development | February Week 4 | Face registration + AES-256 encryption pipeline | 1 week |
| Development | March Week 1 | Real-time face recognition attendance (WebSocket) | 1 week |
| Development | March Week 2 | RTSP/mobile camera integration + head counting | 1 week |
| Development | March Week 3 | Engagement tracking + emotion detection | 1 week |
| Development | March Week 4 | Notifications, messaging, admin panel, 2FA | 1 week |
| Testing | April Week 1 | Unit testing, integration testing | 1 week |
| Testing | April Week 2 | Bug fixing, security audit, performance tuning | 1 week |
| Deployment | April Week 3 | Docker deployment, Nginx config, HTTPS setup | 1 week |
| Submission | April Week 4 | Final documentation, demo, project submission | 1 week |

---

## 12. Conclusion

EduMi represents a significant step forward in intelligent educational technology. By combining real-time WebRTC video conferencing with AI-powered face recognition attendance, student engagement analysis, and live campus camera monitoring, the platform addresses the most pressing challenges faced by modern educational institutions.

The system eliminates manual attendance processes, prevents proxy attendance through liveness detection, and gives teachers actionable insights into student engagement — all within a single, secure, and scalable web platform. The use of AES-256 encryption for biometric data ensures student privacy is protected at all times.

EduMi is not just a video conferencing tool — it is a complete smart classroom ecosystem that bridges the gap between physical and virtual learning environments, making education more efficient, transparent, and data-driven.

---

## 13. References

### Research Papers
1. Dalal, N., & Triggs, B. (2005). *Histograms of Oriented Gradients for Human Detection*. IEEE CVPR 2005. https://ieeexplore.ieee.org/document/1467360
2. Amos, B., Ludwiczuk, B., & Satyanarayanan, M. (2016). *OpenFace: A general-purpose face recognition library with mobile applications*. CMU Technical Report. https://cmusatyalab.github.io/openface/
3. King, D. E. (2009). *Dlib-ml: A Machine Learning Toolkit*. Journal of Machine Learning Research, 10, 1755–1758. https://jmlr.org/papers/v10/king09a.html
4. Viola, P., & Jones, M. (2001). *Rapid Object Detection using a Boosted Cascade of Simple Features*. IEEE CVPR 2001. https://ieeexplore.ieee.org/document/990517
5. Mehta, S., & Jadhav, A. (2020). *Automated Attendance System Using Face Recognition*. International Journal of Computer Applications, 175(12). https://www.ijcaonline.org/

### Official Documentation
6. Django Project. (2024). *Django 4.2 Documentation*. https://docs.djangoproject.com/en/4.2/
7. Django Channels. (2024). *Channels Documentation*. https://channels.readthedocs.io/en/stable/
8. WebRTC.org. (2024). *WebRTC API Documentation*. https://webrtc.org/getting-started/overview
9. OpenCV. (2024). *OpenCV Python Documentation*. https://docs.opencv.org/4.x/
10. Redis. (2024). *Redis Documentation*. https://redis.io/docs/

### Books
11. Géron, A. (2022). *Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow* (3rd ed.). O'Reilly Media.
12. Rosebrock, A. (2019). *Deep Learning for Computer Vision with Python*. PyImageSearch.
13. Greenfeld, D., & Roy, A. (2022). *Two Scoops of Django 3.x*. Two Scoops Press.

### Standards & Security
14. NIST. (2023). *Digital Identity Guidelines (SP 800-63)*. https://pages.nist.gov/800-63-3/
15. GDPR Article 9. *Processing of Special Categories of Personal Data (Biometrics)*. https://gdpr-info.eu/art-9-gdpr/

---

*Document prepared for: EduMi Project Synopsis*
*Version: 1.0 | Date: April 2026*
