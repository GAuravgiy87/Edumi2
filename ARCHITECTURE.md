# 🏗️ Edumi2: High-Level System Architecture

This document provides a comprehensive technical breakdown of the Edumi2 architecture. The system is built on a **4-Layer Decoupled Model**, designed to handle real-time video conferencing, intensive AI processing, and secure biometric authentication at scale.

---

## 📐 Architectural Overview

Edumi2 follows a layered approach where presentation, security, application logic, and data persistence are isolated. This ensures that heavy tasks—like facial recognition and video remuxing—do not interfere with the responsiveness of the user interface or the quality of live meetings.

![System Architecture Diagram](architecture_digram/v4%20(1).png)

---

## 📡 Layer 1: Presentation & Clients
The edge of the system where users and hardware devices interact.

| Component | Description | Why we use it? |
| :--- | :--- | :--- |
| **Web Browser** | The primary interface for Students and Teachers. | Uses WebSockets for real-time attendance and WebRTC for low-latency video meetings. |
| **Mobile Devices** | Acts as portable IP cameras (via DroidCam/IP Webcam). | Allows students or teachers to provide additional camera angles or use their phone as a classroom monitor. |
| **IP / Physical Cameras** | RTSP-capable cameras installed in physical classrooms. | Enables automated head counting and physical surveillance without human intervention. |

---

## 🛡️ Layer 2: Gateway & Security
The entry point that manages traffic, provides security, and ensures high availability.

| Component | Description | Why we use it? |
| :--- | :--- | :--- |
| **Public Ingress (Ngrok)** | Secure tunnel for local development or cloud gateway. | Provides an instant HTTPS/WSS endpoint, which is mandatory for WebRTC and camera access. |
| **Nginx Reverse Proxy** | Handles SSL termination and static file delivery. | Configured with `ip_hash` (Sticky Sessions) to ensure WebSocket clients stay connected to the same server instance. |
| **Load Balancer** | Distributes traffic across multiple app instances. | Uses "Least Connections" for HTTP and `ip_hash` for WebSockets to maintain session stability. |

---

## 🧠 Layer 3: Application & Processing Core
The "Brain" of the system, divided into synchronous handlers and asynchronous specialist workers.

### A. Request Handlers (Synchronous)
*   **Daphne (ASGI Server):** The interface between the internet and Django. It handles WebSockets and long-polling requests that standard WSGI servers cannot.
*   **Main Application (Django):** Manages the core business logic, including authentication, database models, and permissions.
*   **LiveKit Proxy Consumer:** A specialized middleware that forwards binary Protobuf packets between clients and the LiveKit SFU. This allows the system to run in environments where direct SFU access is restricted, ensuring a secure, proxied connection.

### B. Specialist Workers (Async/Sync)
*   **HLS Viewing Service:** A microservice that consumes RTSP/HTTP streams and converts them to HLS using FFmpeg (without re-encoding for speed). It features an **Idle Shutdown** to save resources when no one is watching.
*   **Analytical AI Service:** Handles head counting and biometric matching. It extracts 128-d face embeddings and performs motion-based anti-spoofing to prevent photo-based attendance fraud.
*   **Celery Worker:** Handles "Fire-and-Forget" background tasks like generating large attendance reports, cleaning up old logs, and sending batch notifications.

### 🔄 The "Active Bridge" (Redis Integration)
While Redis is physically located in Layer 4, it serves as the **active nervous system** for Layer 3.
*   **Signaling:** Application handlers (Daphne/Django) use Redis to "broadcast" events.
*   **Task Hand-off:** The Main App drops tasks into Redis for Celery Workers to pick up asynchronously.


---

## 💾 Layer 4: Data Persistence & Messaging
The foundation where all system state and data are stored.

### The Dual Role of Redis 🔄
In the 4-layer model, Redis is categorized in **Layer 4** because it is a **Stateful Service**. While Layer 3 (Logic) can be restarted at any time, Layer 4 (Redis) maintains the "Short-term Memory" of the system.

1.  **As a Channel Layer (Broker):** It acts as the backbone for WebSockets. When a teacher kicks a student, the "Kick" signal travels through Redis to the specific Daphne worker holding that student's connection.
2.  **As a Cache & Task Queue:** It stores session tokens for speed and acts as the "Waiting Room" for Celery tasks, ensuring that the main application never waits for slow AI processes to finish.


### Database Layer
*   **PostgreSQL:** The production database for high-concurrency storage of user profiles, encrypted face embeddings, and meeting logs.
*   **SQLite:** Used during development for rapid prototyping and local testing.

---

## 🔄 System Data Flows

### 1. The Attendance Feedback Loop
1.  **Capture:** The browser or IP camera sends a video frame to the **Analytical Service**.
2.  **Process:** The service extracts the face vector and compares it against the **PostgreSQL** biometric store.
3.  **Broadcast:** The result (Present/Absent) is sent to **Redis (Channel Layer)**.
4.  **Update:** **Daphne** picks up the message and pushes a WebSocket update to the Teacher's dashboard instantly.

### 2. Video Streaming (HLS)
1.  **Request:** A user opens a camera feed.
2.  **Trigger:** The **Camera Service** starts an FFmpeg process to remux the RTSP stream.
3.  **Delivery:** The stream is served as HLS segments through **Nginx** to the user's browser.
4.  **Optimized Exit:** If the user closes the tab, the **Idle Shutdown** logic kills the FFmpeg process after 30 seconds to save CPU.

---

## 🔒 Security Architecture
*   **Biometric Privacy:** Raw images are never saved. Only 128-d mathematical vectors are stored, encrypted with **AES-256**.
*   **Token-Based Access:** All video meetings require a JWT (JSON Web Token) generated by the Django core and validated by the LiveKit SFU.
*   **Protocol Enforcement:** All communication between Layer 1 and Layer 2 is encrypted via **HTTPS/WSS**.

---

## 📖 Terminology & Glossary

| Term | Description | Role in Edumi2 |
| :--- | :--- | :--- |
| **SFU** | **Selective Forwarding Unit**. A type of WebRTC server that routes video/audio streams between participants. | Used for high-efficiency multi-user video meetings without overloading student hardware. |
| **LiveKit** | A production-grade open-source SFU and developer toolkit. | The core engine for video conferencing, handling room management and media distribution. |
| **Protobuf** | **Protocol Buffers**. Google's language-neutral, binary serialization format. | Used by LiveKit for highly efficient, low-bandwidth signaling between the client and server. |
| **WebRTC** | **Web Real-Time Communication**. An open-source project that enables peer-to-peer media streaming. | The underlying protocol for browser-based video, audio, and data sharing. |
| **HLS** | **HTTP Live Streaming**. An adaptive bitrate streaming protocol. | Used to serve physical camera feeds to the dashboard in a format compatible with all modern browsers. |
| **RTSP** | **Real Time Streaming Protocol**. A protocol designed for controlling streaming media servers. | The standard protocol used to pull raw video feeds from IP cameras and mobile devices. |
| **ASGI** | **Asynchronous Server Gateway Interface**. A successor to WSGI for Python. | Allows Django to handle asynchronous protocols like WebSockets and HTTP2 simultaneously. |
| **Daphne** | A specialized ASGI server built for Django Channels. | Acts as the "Ear" of the system, listening for both standard web requests and long-running WebSocket connections. |
| **Ngrok** | A cross-platform application that exposes local servers to the public internet over secure tunnels. | Used as a **Cloud Gateway** to provide an instant HTTPS/WSS URL for mobile testing and WebRTC. |
| **Nginx** | A high-performance web server and reverse proxy. | Manages **TLS Termination** and efficiently serves static assets like CSS, JS, and profile photos. |
| **Sticky Sessions** | A method where a load balancer maps a client's session to a specific server. | Implemented via `ip_hash` in Nginx to ensure a user's WebSocket connection stays with the same Django worker. |
| **128-d Vector** | A mathematical representation of a face using 128 specific data points (embeddings). | This is the "Biometric Fingerprint" stored in the database. It is much smaller and safer than storing a real photo. |
| **Motion Liveness** | A technique to detect if a face is "alive" by tracking pixel shifts over time. | Part of the **Anti-spoofing** system that prevents students from showing a photo to the camera to fake attendance. |
| **TLS Termination** | The process of decrypting encrypted traffic before it reaches the main application. | Handled by Nginx/Ngrok so the Django application can focus on logic rather than heavy decryption. |
| **JWT** | **JSON Web Token**. A compact, URL-safe means of representing claims between two parties. | Used to authenticate students and teachers when they join a LiveKit video meeting. |
| **AES-256** | **Advanced Encryption Standard** with a 256-bit key. | The industry-standard encryption used to secure student face embeddings in the database. |
| **FFmpeg** | A complete, cross-platform solution to record, convert, and stream audio and video. | The "Workhorse" in the Camera Service that remuxes RTSP streams into HLS segments. |
| **Redis** | An in-memory data structure store used as a broker and cache. | The "Messaging Hub" that coordinates real-time updates between different application parts. |
| **Celery** | An asynchronous task queue/job queue. | Offloads heavy computations (like report generation) so the user doesn't experience "loading" delays. |

---
*Created by Antigravity AI — Architectural Audit 2026-05-07*

