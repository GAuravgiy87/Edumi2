# 🏗️ SYSTEM ARCHITECTURE - EDUMI2

Edumi2 is a professional-grade educational ecosystem that integrates real-time AI monitoring with high-performance video conferencing to ensure academic integrity.

---

## 🗺️ High-Level System Map

This diagram shows how information flows from the **User** to the **AI & Database**.

```text
+-------------------------------------------------------------------------------+
|                      1. THE USER INTERFACE (Frontend)                         |
|   +---------------------------------------+       +-----------------------+   |
|   |             WEB BROWSER               |       |    USER DASHBOARD     |   |
|   |      (Accessing the Platform)         |       |  (Teachers & Students)|   |
|   +-------------------+-------------------+       +-----------+-----------+   |
+-----------------------|---------------------------------------|---------------+
                        |                                       |
                        +-------------------+-------------------+
                                            |
                          (Internet Connection: HTTPS / WSS)
                                            |
                                            v
+-----------------------------------------------------------------------------+
|                      2. THE GATEWAY (Security & Routing)                    |
|             "The digital security guard that checks permissions"            |
|   +-----------------------------------------------------------------------+ |
|   |                          NGINX SECURITY PROXY                         | |
|   |            (Protects the app and ensures fast data delivery)          | |
|   +-------------------------------------+---------------------------------+ |
+-----------------------------------------|-----------------------------------+
                                          |
                                          | (Reverse Proxy: HTTP / WS)
                                          v
+-----------------------------------------------------------------------------+
|                      3. THE BRAIN (Application Services)                    |
|             "Where all the AI, Video, and Logic processing happens"         |
|   +-------------+   +--------------+   +-------------+   +---------------+  |
|   |  MAIN APP   |   | AI MONITORING|   | LIVEKIT SFU |   | CAMERA SERVER |  |
|   | (Django/ASGI)   | (OpenCV / AI)|   | (WebRTC Eng)|   | (RTSP/HTTP)   |  |
|   |             |   |              |   |             |   |               |  |
|   | - Auth & RT |   | - Face Recog |   | - Video RT  |   | - Feed Hub    |  |
|   | - WS Hub    |   | - Att. Track |   | - Simulcast |   | - Post-Proc   |  |
|   +------+------+   +------+-------+   +------+------+   +-------+-------+  |
|          |                   |                    |                    ^          |
|          |                   |                    |            (RTSP)  |          |
|          |                   |                    |            +-------+-------+  |
|          |                   |                    |            |   IP CAMERA   |  |
|          |                   |                    |            | [Live Stream] |  |
|          |                   |                    |            +-------+-------+  |
|          |                   |                    |                    |          |
|          +----------+--------+----------+---------+----------+---------+          |
|                     |                   |                    |                    |
|                     |            (Task Signal)               |                    |
|                     v                   v                    v                    |
|   +-------------------------------------------------------------------------------+ |
|   |                          CELERY WORKER                                        | |
|   |                  (Background Tasks / Analytics)                               | |
|   +--------------------------------+----------------------------------------------+ |
|                                    |                                        |
|                                    | (ORM / Redis Protocol)                  |
|                                    v                                        |
+------------------------------------|----------------------------------------+
                                     |
                                     v
+------------------------------------|----------------------------------------+
|                      4. THE VAULT (Data & Infrastructure)                   |
|   +-------------------------+               +-------------------------------+ |
|   |     DATABASE (SQLite)   |               |       MESSAGE HUB (Redis)     | |
|   |    [Saved Records]      |               |      [Instant Signals]        | |
|   +-------------------------+               +-------------------------------+ |
+-----------------------------------------------------------------------------+
                    
---

## 🚀 How the App Flows (Simple Steps)

To make it even simpler, here is the "Life of a Lecture":

1.  **Login & Check:** The **User Interface** asks the **Main App** if the user is a Teacher or Student.
2.  **Face ID:** The **AI Monitoring** looks at the student's camera (via the Camera Server) to make sure they are who they say they are.
3.  **Start Video:** The **LiveKit SFU** starts a high-quality stream between the teacher and students.
4.  **Watch Attention:** While the lecture is on, the **AI Monitoring** watches if students are paying attention.
5.  **Auto-Report:** When the lecture ends, the **Celery Worker** saves everything into **The Vault** and sends a report to the Admin.

---

## 🧩 Key Parts Explained

*   **Web Browser:** The client-side application (Chrome, Edge, etc.) used by all users to access the platform.
*   **User Dashboard:** The main interface for Teachers and Students to manage meetings, view attendance, and interact in real-time.
*   **[ Main App ] (Django/ASGI):** The central "Manager" that handles **Auth & Routing** and the **WebSockets Hub** for real-time signals.
*   **[ AI Monitoring ] (OpenCV / AI):** The "Observer" that performs **Face Recognition** and **Attention Tracking**. It receives processed video data to verify student identity and focus.
*   **[ LiveKit SFU ] (WebRTC Engine):** The high-performance "Media Engine" responsible for **Video Routing** and **Simulcasting** (adjusting quality for varying internet speeds).
*   **[ Camera Server ] (Processing):** Positioned outside the main application layer, it captures raw feeds from **IP Cameras** and prepares them for the AI Monitoring service.
*   **[ Celery Worker ] (Background Tasks / Analytics):** Positioned at the bottom of Layer 3, this "Assistant" handles heavy background tasks like generating reports and calculating student analytics.
*   **IP Cameras:** Physical hardware (CCTV/RTSP) that feeds live video directly into the Camera Server.
*   **[ Message Hub ] (Redis):** The "Speedway" that makes chat and notifications feel instant.
*   **[ Database ] (SQLite):** The "File Cabinet" where all history is stored safely.