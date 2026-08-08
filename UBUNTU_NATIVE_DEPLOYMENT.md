# EduMi2 — Native Ubuntu Deployment Guide (Without Docker)

This guide provides full instructions for building, installing, and deploying **EduMi2** directly on **Ubuntu Server (20.04 / 22.04 / 24.04 LTS)** natively using **Systemd**, **PostgreSQL**, **Redis**, **Nginx**, **Daphne**, and **Celery** — completely **without Docker**.

---

## 📋 Architecture & Requirements

- **Operating System**: Ubuntu 20.04 / 22.04 / 24.04 LTS or Debian 11/12.
- **Hardware Requirements**:
  - **RAM**: Minimum 4GB (8GB recommended for video stream rendering & face recognition).
  - **CPU**: Dual-core CPU or higher.
  - **Disk Space**: Minimum 10GB free space.
- **System Stack**:
  - **Database**: PostgreSQL 15 (`edumi_db`, `edumi_user`).
  - **In-Memory Cache / Broker**: Redis (`redis-server`).
  - **Web Framework**: Django 4.2.9 + Daphne (ASGI WebSockets).
  - **Media SFU Server**: LiveKit Server (`port 7880`, `7881`).
  - **Process Manager**: Systemd (`edumi-auth`, `edumi-admin`, `edumi-meeting`, `edumi-msg`, `edumi-profile`, `edumi-video`, `edumi-camera`, `edumi-celery`, `edumi-livekit`).
  - **Reverse Proxy**: Nginx Web Server with SSL/TLS termination.

---

## ⚡ Quick Deployment (Automated)

### 1. Check Server Prerequisites
Run the infrastructure inspector to check your Ubuntu OS version, Python 3.11, PostgreSQL, Redis, Nginx, Systemd, C/C++ build tools, graphics libraries, disk space, and open network ports:

```bash
chmod +x scripts/check_ubuntu_env.sh
./scripts/check_ubuntu_env.sh
```

### 2. Run Automated Deployment Script
To automatically install all missing Ubuntu packages, provision PostgreSQL, configure Redis, download LiveKit server, setup Python `venv`, install dependencies, run migrations and `collectstatic`, generate SSL certificates, create Systemd microservice files, and configure Nginx:

```bash
chmod +x deploy_ubuntu_native.sh
sudo bash deploy_ubuntu_native.sh
```

*(Optional: For domain setup with Let's Encrypt SSL, pass `--domain yourdomain.com --email you@example.com`)*
```bash
sudo bash deploy_ubuntu_native.sh --domain edumi.ac.in --email admin@edumi.ac.in
```

---

## 🛠 Manual Step-by-Step Installation Guide

### Step 1: Update Packages & Install System Dependencies
```bash
sudo apt-get update
sudo apt-get install -y \
  python3.11 python3.11-venv python3.11-dev python3-pip \
  build-essential cmake g++ libpq-dev libffi-dev \
  ffmpeg postgresql postgresql-contrib redis-server nginx supervisor \
  libopenblas-dev liblapack-dev libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
  curl wget git openssl net-tools
```

### Step 2: Configure PostgreSQL Database
```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql

sudo -u postgres psql -c "CREATE USER edumi_user WITH PASSWORD 'edumi_secure_pass_123';"
sudo -u postgres psql -c "CREATE DATABASE edumi_db OWNER edumi_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE edumi_db TO edumi_user;"
```

### Step 3: Setup Python Environment & Dependencies
```bash
cd /opt/edumi   # Or your project directory
python3.11 -m venv venv
./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r requirements.txt
```

### Step 4: Run Migrations & Collect Static Files
```bash
./venv/bin/python manage.py migrate
./venv/bin/python manage.py collectstatic --noinput
./venv/bin/python manage.py createsuperuser
```

### Step 5: Start & Enable Systemd Microservices
View status of all EduMi2 background services:
```bash
sudo systemctl status edumi-auth edumi-admin edumi-meeting edumi-msg edumi-profile edumi-video edumi-camera edumi-celery edumi-livekit
```

To restart services:
```bash
sudo systemctl restart edumi-auth edumi-camera edumi-celery nginx
```

---

## 🌐 Network Ports Reference

| Service | Executable / Command | Port | Access |
| :--- | :--- | :--- | :--- |
| **Nginx HTTP / HTTPS** | `nginx` | 80 / 443 | Public |
| **EduMi Auth** | `daphne (school_project.asgi:application)` | 8002 | Internal |
| **EduMi Admin** | `daphne (school_project.asgi:application)` | 8003 | Internal |
| **EduMi Meeting** | `daphne (school_project.asgi:application)` | 8004 | Internal |
| **EduMi Messaging** | `daphne (school_project.asgi:application)` | 8005 | Internal |
| **EduMi Profile** | `daphne (school_project.asgi:application)` | 8006 | Internal |
| **EduMi Video** | `daphne (school_project.asgi:application)` | 8007 | Internal |
| **Camera Microservice** | `python camera_service/serve.py` | 8008 | Internal |
| **LiveKit SFU Server** | `./livekit-bin/livekit-server` | 7880 / 7881 | Internal / WSS |
| **Redis** | `redis-server` | 6379 | Internal |
| **PostgreSQL** | `postgresql` | 5432 | Internal |
