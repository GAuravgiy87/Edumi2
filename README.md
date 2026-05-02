<div align="center">

<img src="static/logo.svg" alt="EduMi Logo" width="400" />

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=28&duration=2800&pause=2000&color=6366F1&center=true&vCenter=true&width=940&lines=Edumi2+-+Real-Time+AI+Monitoring+%26+Meetings;The+Future+of+Academic+Interaction;One+Complete+Source+of+Truth" alt="Typing SVG" />

---

### 📘 **The Master Guide**
All technical specifications, architectural diagrams, installation steps, and app flows have been consolidated into a single comprehensive manual.

## [👉 View Full Project Documentation (PROJECT_COMPLETE_GUIDE.md)](PROJECT_COMPLETE_GUIDE.md)

---

### 🚀 Quick Start
If you just want to run the system immediately:
1. Right-click `start_all.ps1` and select **Run with PowerShell**.
2. Copy the **ngrok URL** provided in the console.
3. Open the URL in your browser.
4. Default Admin: `EdumiAdmin` / `Gaurav@0000`

---

### 🛠️ Core Technology Stack
| Backend | Real-Time | Media | AI Engine |
|:---:|:---:|:---:|:---:|
| Django | Channels | LiveKit | OpenCV |

</div>

### 🏗️ System Architecture & Data Flow

```text
+-----------------------------------------------------------------------------+
|                     LAYER 1: PRESENTATION & CLIENTS                         |
|  [ Student & Teacher Web Browsers ]        [ External IP Cameras in Rooms ] |
+-----------------------------------------------------------------------------+
              |                                        |
     (HTTPS / WSS / WebRTC)                  (RTSP / HTTP Media Streams)
              |                                        |
              v                                        v
+-----------------------------------------------------------------------------+
|                     LAYER 2: GATEWAY & ROUTING                              |
|  [ Ngrok Tunnel ] ---> Secure Entry Point for External WebRTC / WebSockets  |
|  [ Nginx Proxy  ] ---> Routes HTTP to Django / WebSockets to Daphne         |
+-----------------------------------------------------------------------------+
              |                                        |
       (Routing)                                 (Signaling)
              v                                        v
+-----------------------------------------------------------------------------+
|                     LAYER 3: APPLICATION & AI CORE                          |
|  +--------------------+    +--------------------+    +--------------------+ |
|  |     Main App       |    |   Camera Service   |    |    LiveKit SFU     | |
|  |   (Django/ASGI)    |<-->|   (OpenCV / AI)    |    |  (WebRTC Engine)   | |
|  | - Auth & Routing   |    | - Face Recognition |    | - Video Routing    | |
|  | - WebSockets Hub   |    | - Attention Track  |    | - Simulcasting     | |
|  +---------|----------+    +---------|----------+    +---------|----------+ |
|            |                         |                         |            |
|            +-----------+-------------+-------------------------+            |
|                        v                                                    |
|            +-----------------------+                                        |
|            |     Celery Worker     | ---> Background Tasks / Analytics      |
|            +-----------------------+                                        |
+-----------------------------------------------------------------------------+
              |                                        |
       (Queries)                                (Pub/Sub)
              v                                        v
+-----------------------------------------------------------------------------+
|                     LAYER 4: DATA & PERSISTENCE                             |
|  [ SQLite DB ] ----> Stores Users, Meetings, Logs, Profiles                 |
|  [ Redis     ] ----> Real-time Message Broker (Channels) & Celery Queue     |
+-----------------------------------------------------------------------------+
```

---

<sub>For developer notes and a complete module deep-dive, please refer to the [Master Guide](PROJECT_COMPLETE_GUIDE.md).</sub>
