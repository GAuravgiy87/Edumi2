# Edumi2 System Architecture

## Overview
Edumi2 is a comprehensive educational platform integrating real-time video conferencing, secure camera monitoring, and automated attendance tracking. The system is built on a modular, 4-layer architecture designed for security, scalability, and high-performance media delivery.

---

## 🏗️ 4-Layer Architecture Pipeline

### **LAYER 1: CLIENT ACCESS PIPELINE (Frontend)**
*   **WebRTC Client**: Low-latency bi-directional media for Meetings.
*   **HLS.js Player**: Secure, adaptive bitrate streaming for Cameras/VOD.
*   **Management UI**: Admin/Teacher/Student dashboards.
*   **Interactions**: UI | HTTP Requests | WebSocket Signaling.

---

### **LAYER 2: LOGIC & SECURITY PIPELINE (Django)**
*   **Django Web Server**: Core application logic and routing.
*   **Auth Manager**: User authentication and Role-Based Access Control (RBAC).
*   **Token Service**: Generates `StreamTokens` (Cameras) and SFU Signals (Meetings).
*   **API Gateway**: Unified interface for mobile and web clients.
*   **HeadCount Logic**: Orchestrates automated detection cycles.

---

### **LAYER 3: MEDIA INFRASTRUCTURE PIPELINE (Transport)**
*   **Mediasoup SFU**: Selective Forwarding Unit for multi-party WebRTC meetings.
*   **HLS Proxy (Port 8001)**: Isolated microservice for camera stream conversion.
*   **FFmpeg Engine**: Real-time transcoding (RTSP -> HLS) and recording.
*   **Recording Service**: Chunks and finalizes live session videos.

---

### **LAYER 4: HARDWARE & STORAGE PIPELINE (Persistence)**
*   **IP/Mobile Cameras**: Physical hardware layer (RTSP/HTTP feeds).
*   **PostgreSQL**: Primary database for metadata, logs, and users.
*   **Redis**: Real-time state cache for viewer counts and session tracking.
*   **Media Storage**: Local/Cloud storage for HLS segments and processed VODs.

---

## 🔄 System Data Flow

1.  **Meeting Flow**:
    `User -> Django (Auth) -> SFU Signaler -> Mediasoup SFU <-> WebRTC Clients`

2.  **Secure Camera Flow**:
    `User -> Django (Token Gen) -> HLS Player -> HLS Proxy (Auth Check) -> FFmpeg -> IP Camera Hardware`

3.  **HeadCount Pipeline**:
    `Django Timer -> HeadCount Manager -> Camera Feed -> FFmpeg Frame Grab -> Detection Algorithm -> PostgreSQL Log`

---

## 🛡️ Security Implementation
*   **Hardware Abstraction**: Cameras are never exposed directly to users.
*   **Token-Based Access**: Every HLS segment request is validated against a short-lived, user-specific `StreamToken`.
*   **Microservice Isolation**: The video processing engine runs independently from the core web server to prevent resource exhaustion.
