# EduMi2 Production Server Specification & Deployment Guide

---
## 📌 Overview
This document consolidates **hardware requirements**, **software prerequisites**, **network ports**, and a **step‑by‑step Docker deployment guide** for the EduMi2 micro‑service application. It is intended for a production environment capable of handling **up to 10 000 concurrent users**.

---
## 🖥️ Hardware Requirements
| Component | Minimum | Recommended |
|-----------|---------|------------|
| **CPU** | 8 cores (x86_64) | 12 – 16 cores for peak load |
| **RAM** | 32 GB | 64 GB |
| **Storage** | 1 TB SSD (fast I/O) | 2 TB SSD + RAID for redundancy |
| **GPU** (optional) | None | NVIDIA RTX 2060 + with CUDA (for video encoding/decoding) |
| **Network** | 1 Gbps stable broadband | 10 Gbps uplink, low latency |

*All containers share a Docker bridge network; ensure the host firewall permits the ports listed below.*

---
## 🛠️ Software Prerequisites (to install on the **host server**)
1. **Operating System** – Windows 11 (Desktop) with Docker Desktop **or** any modern Linux distribution (Ubuntu 22.04 LTS recommended).
2. **Docker Engine** – version **≥ 20.10**
3. **Docker‑Compose** – v2 (bundled with Docker Desktop or `apt install docker-compose`).
4. **Git** – for cloning the repository.
5. **Python 3.11** and **pip** (only needed if you run locally without Docker).
6. **PostgreSQL client libraries** – `libpq-dev` (required to build `psycopg2-binary`).
7. **Redis server** – optional for local testing (Docker version will be used in production).
8. **FFmpeg ≥ 5.0** – required for video processing (installed inside the Docker image).
9. **Nginx** – optional reverse‑proxy for TLS termination (Docker image will be used).
10. **NVIDIA drivers & CUDA Toolkit** – only if GPU acceleration is required (install on host and expose to containers via `--gpus all`).

---
## 🔌 Ports Used (production values)
| Service | Host Port | Container Port | Protocol | Purpose |
|---------|-----------|----------------|----------|---------|
| **Auth** | 8002 | 8002 | TCP | Daphne/WebSocket for authentication |
| **Admin** | 8003 | 8003 | TCP | Admin UI |
| **Meeting** | 8004 | 8004 | TCP | Meeting coordination |
| **Camera** | 8005 | 8005 | TCP | Camera API |
| **Messaging** | 8006 | 8006 | TCP | Chat service |
| **Profile** | 8007 | 8007 | TCP | User profile service |
| **Video** | 8008 | 8008 | TCP | Video streaming |
| **Video Editing** | 8009 | 8009 | TCP | Editing API |
| **Live Stream** | 8010 | 8010 | TCP | Live‑stream manager |
| **LiveKit** | 7880 | 7880 | TCP | SFU signaling |
| **LiveKit Media (UDP)** | 50000‑50200 | 50000‑50200 | UDP | Media transport |
| **PostgreSQL** | 5432 | 5432 | TCP | Database |
| **Redis** | 6379 | 6379 | TCP | Cache / channel layer |
| **Nginx (HTTPS)** | 443 | 443 | TCP | TLS termination (optional) |

> **Note**: The `docker-compose.yml` file already maps these ports. Adjust the host ports if they clash with existing services on the server.

---
## 📦 Docker Images & Build
All Django‑based services share a **single Dockerfile** located at the repository root. The file includes the following `EXPOSE` directive for reference:

```dockerfile
EXPOSE 8002 8003 8004 8005 8006 8007 8008 8009 8010 7880 7881
```

Each service overrides the default command in `docker‑compose.yml` to start Daphne or a custom script on its dedicated port.

---
## 🚀 Production Deployment Guide
### 1. Prepare the Server
```bash
# Update OS packages (Linux example)
sudo apt update && sudo apt upgrade -y

# Install Docker Engine
sudo apt install -y ca-certificates curl gnupg lsb-release
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Verify installation
docker version
docker compose version
```
*On Windows, download Docker Desktop and follow the installer GUI.*

### 2. Clone the Repository
```bash
mkdir -p /opt/edumi2 && cd /opt/edumi2
git clone <repo‑url> .
```
*(Replace `<repo‑url>` with the actual Git URL.)*

### 3. Configure Environment Variables
Copy the example file and adjust for production values (especially secret keys and database passwords):
```bash
cp .env.example .env
# Edit .env – set strong passwords, JWT secrets, LiveKit keys, etc.
vi .env
```
Key variables to review:
- `DATABASE_URL=postgres://edumi_user:<strong‑pass>@db:5432/edumi_db`
- `REDIS_URL=redis://redis:6379/0`
- `LIVEKIT_URL=wss://livekit:7880/livekit-proxy`
- `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`
- `DJANGO_SECRET_KEY`
- `ALLOWED_HOSTS` (include your domain/IP)

### 4. Build & Launch the Stack
```bash
# Build all images (cached layers for faster subsequent builds)
docker compose build

# Start containers in detached mode
docker compose up -d
```
**Verification**:
```bash
docker compose ps   # all services should show "Up"
# Check DB connection
docker exec -it edumi_db psql -U edumi_user -d edumi_db -c "\dt"
```
### 5. Apply Database Migrations & Collect Static Files
```bash
# Run migrations inside any Django container (e.g., auth)
docker exec -it edumi_auth python manage.py migrate
# Collect static assets (already done in Dockerfile, but re‑run if needed)
docker exec -it edumi_auth python manage.py collectstatic --noinput
```
### 6. Optional – Configure Nginx TLS
1. Place your certificate (`fullchain.pem`) and private key (`privkey.pem`) in the `certs/` folder.
2. Create an Nginx config `nginx/conf.d/edumi.conf`:
```nginx
server {
    listen 443 ssl;
    server_name your.domain.com;
    ssl_certificate /etc/ssl/certs/fullchain.pem;
    ssl_certificate_key /etc/ssl/certs/privkey.pem;

    location / {
        proxy_pass http://auth:8002;   # point to the primary entry point
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
3. Restart Nginx:
```bash
docker compose restart nginx
```
### 7. Scaling (if needed)
You can increase the number of worker containers (e.g., Celery or any Django service) by adding the `deploy.replicas` field in `docker‑compose.yml` and redeploying:
```yaml
  celery:
    deploy:
      replicas: 3
```
Then run:
```bash
docker compose up -d --scale celery=3
```
### 8. Monitoring & Logging
- **Docker logs**: `docker logs -f <container_name>`
- **Prometheus/Grafana**: you can add side‑car exporters if needed.
- **Healthchecks** are already defined for PostgreSQL; you may add similar checks for Redis and LiveKit.

---
## 📋 Checklist before Going Live
- [ ] Strong, unique passwords in `.env` (no default credentials).
- [ ] TLS certificates installed and Nginx configuration verified.
- [ ] Firewall opens only the ports listed above; all others are blocked.
- [ ] Data volume `./postgres_data` backed up regularly (e.g., nightly `pg_dump`).
- [ ] Static files served via WhiteNoise or Nginx (verify `collectstatic` succeeded).
- [ ] CPU & RAM monitoring set up; autoscaling plan defined.
- [ ] Load testing performed (e.g., with Locust) to validate 10 000‑user capacity.

---
## 📂 Files Added / Updated
| File | Purpose |
|------|---------|
| `Dockerfile` | Added `EXPOSE` ports for all services.
| `docker-compose.yml` | Defines each micro‑service container, healthchecks, volumes, and port mappings.
| `specs.md` | Consolidates hardware, software, ports, and installation notes (now refined).
| **`server_deployment_guide.md`** (this file) | Full production‑ready server specification and Docker deployment guide.

You can now copy this guide to your server, follow the steps, and have EduMi2 running in a fully containerized, production‑grade environment.

---
*End of document.*
