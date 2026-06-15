# EduMi2 Production Deployment Guide

This guide covers deploying EduMi2 to production using Docker.

---

## Prerequisites
1. A server running Linux (Ubuntu 22.04 or similar recommended)
2. Docker and Docker Compose installed
3. A domain name (optional, but recommended for SSL)
4. Server IP address

---

## 1. Prepare Environment Variables

Copy `config/.env.example` to `.env` in project root:
```bash
cp config/.env.example .env
```

Then edit `.env` with your actual values:

```bash
# Generate a strong SECRET_KEY
# python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY=your-very-strong-secret-key-here

# Set DEBUG to False for production
DEBUG=False

ALLOWED_HOSTS=*
SERVER_IP=your-server-public-ip

# PostgreSQL
POSTGRES_DB=edumi2
POSTGRES_USER=edumi2
POSTGRES_PASSWORD=your-strong-postgres-password

# Redis
REDIS_URL=redis://redis:6379/0

# LiveKit
LIVEKIT_URL=ws://your-server-ip:8080/livekit-proxy
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=your-very-strong-livekit-secret-at-least-32-chars

# Face Encryption
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FACE_ENCRYPTION_KEY=your-fernet-encryption-key
FACE_MATCH_THRESHOLD=0.50
FACE_PRESENCE_DURATION=30

# CSRF
CSRF_TRUSTED_ORIGINS=http://your-server-ip,http://your-server-ip:8080,https://your-domain.com
```

---

## 2. Deploy Using Docker Compose

### 2.1 Start All Services
From project root directory:
```bash
docker-compose up -d
```

### 2.2 Check Service Status
```bash
docker-compose ps
```

All services should show status "Up" or "Healthy".

### 2.3 View Logs
```bash
# All services
docker-compose logs -f

# Specific service (web, db, redis, livekit, worker, camera_service, nginx)
docker-compose logs -f web
```

---

## 3. Production Security Checklist

### 3.1 SSL Certificate (Strongly Recommended!)
To use HTTPS, we recommend adding Let's Encrypt using Nginx:

1. Update `nginx/nginx.conf` to include your domain
2. Use `certbot` to get SSL certificates
3. Update `docker-compose.yml` to mount certificates and use 443 port

### 3.2 Update Security Settings in `school_project/settings.py`
If you have SSL configured, update these in settings.py:
```python
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = 'SAMEORIGIN'
```

### 3.3 Firewall
Allow necessary ports on your server's firewall:
- 80 (HTTP)
- 443 (HTTPS, if using SSL)
- 50000-50200 (LiveKit UDP for video/audio)

---

## 4. Maintenance

### 4.1 Backup Database
```bash
docker-compose exec db pg_dump -U edumi2 edumi2 > backup.sql
```

### 4.2 Restore Database
```bash
docker-compose exec -T db psql -U edumi2 -d edumi2 < backup.sql
```

### 4.3 Update Application
```bash
docker-compose down
git pull  # Or copy updated files
docker-compose build --no-cache
docker-compose up -d
```

### 4.4 Collect Static Files (If not using Docker)
```bash
python manage.py collectstatic --noinput
```

---

## 5. Service URLs

| Service | URL | Notes |
|---------|-----|-------|
| EduMi2 Web Interface | http://your-server-ip:8080 | Main app |
| LiveKit | http://your-server-ip:7880 | Internal use only |
| Django Admin | http://your-server-ip:8080/admin | Create a superuser first |

---

## 6. Create a Superuser (Admin Account)
```bash
docker-compose exec web python manage.py createsuperuser
```
