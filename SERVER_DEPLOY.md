<div align="center">

# 🚀 EduMi 2 — Server Deployment Guide

**Complete step-by-step guide to deploy EduMi 2 on a production Linux server**
*Ubuntu 22.04 LTS / Debian 12 recommended*

---

[![Platform](https://img.shields.io/badge/Platform-Ubuntu%2022.04-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)](https://ubuntu.com)
[![Nginx](https://img.shields.io/badge/Nginx-Reverse%20Proxy-009639?style=for-the-badge&logo=nginx&logoColor=white)](https://nginx.org)
[![SSL](https://img.shields.io/badge/SSL-Let's%20Encrypt-003A70?style=for-the-badge&logo=letsencrypt&logoColor=white)](https://letsencrypt.org)
[![Systemd](https://img.shields.io/badge/Auto--Restart-Systemd-black?style=for-the-badge&logo=linux&logoColor=white)](https://systemd.io)

</div>

---

## 📋 Table of Contents

- [What You Need](#-what-you-need-before-starting)
- [Method A — One-Command Auto Deploy](#-method-a--one-command-auto-deploy-recommended)
- [Method B — Step-by-Step Manual Deploy](#-method-b--step-by-step-manual-deploy)
  - [1. Rent a VPS Server](#step-1--rent-a-vps-server)
  - [2. Connect to Server](#step-2--connect-to-server-via-ssh)
  - [3. Install System Packages](#step-3--install-system-packages)
  - [4. Create App User](#step-4--create-a-dedicated-app-user)
  - [5. Install LiveKit Binary](#step-5--download-livekit-binary)
  - [6. Clone the Repository](#step-6--clone-the-repository)
  - [7. Python Environment](#step-7--python-virtual-environment--dependencies)
  - [8. Configure .env](#step-8--configure-environment-variables)
  - [9. Database & Static Files](#step-9--database-migrations--static-files)
  - [10. SSL Certificate](#step-10--generate-ssl-certificate-internal)
  - [11. Systemd Services](#step-11--create-systemd-services-auto-restart)
  - [12. Nginx Setup](#step-12--configure-nginx-reverse-proxy)
  - [13. Let's Encrypt SSL](#step-13--free-ssl-with-lets-encrypt)
  - [14. Firewall](#step-14--configure-firewall)
  - [15. DNS Configuration](#step-15--configure-dns)
  - [16. Create Admin User](#step-16--create-admin-account)
  - [17. Verify Everything](#step-17--verify-everything-is-running)
- [Auto-Healing Watchdog](#-auto-healing-watchdog)
- [Updating the App](#-updating-the-app)
- [Monitoring & Logs](#-monitoring--logs)
- [Troubleshooting](#-troubleshooting)

---

## ✅ What You Need Before Starting

| Requirement | Details |
|---|---|
| **VPS Server** | Ubuntu 22.04 LTS (minimum 2 GB RAM, 2 vCPU, 20 GB SSD) |
| **Domain Name** | e.g. `edumi.yourdomain.com` — any registrar (Namecheap, GoDaddy, Cloudflare) |
| **SSH Access** | Root or sudo access to the server |
| **Git Repo** | The EduMi 2 code pushed to GitHub |
| **Email** | For Let's Encrypt SSL certificate notifications |

> **Recommended VPS Providers:** DigitalOcean, Hetzner, Vultr, Linode, AWS EC2, Google Cloud

---

## ⚡ Method A — One-Command Auto Deploy (Recommended)

> This single script does everything — installs dependencies, clones the app, generates secrets, sets up Nginx, gets SSL from Let's Encrypt, creates systemd services with auto-restart, and configures the firewall.

### On your server, run:

```bash
# 1. Download the deploy script
wget https://raw.githubusercontent.com/GAuravgiy87/Edumi2/new_edumi/server_deploy.sh

# 2. Make it executable
chmod +x server_deploy.sh

# 3. Run it (replace with your domain and email)
sudo bash server_deploy.sh \
  --domain edumi.yourdomain.com \
  --email   admin@yourdomain.com
```

**That's it.** The script handles everything. Skip to [Step 15 — DNS](#step-15--configure-dns) after it completes.

> **Optional flags:**
> - `--branch main` — Deploy a different branch
> - `--no-ssl` — Skip Let's Encrypt (use self-signed only)
> - `--no-nginx` — Skip Nginx (raw Daphne only)

---

## 🔧 Method B — Step-by-Step Manual Deploy

Follow this if you want full control of each step, or if the auto-deploy script fails.

---

### STEP 1 — Rent a VPS Server

1. Go to **DigitalOcean** (https://digitalocean.com) or **Hetzner** (https://hetzner.com)
2. Create a new **Droplet / Server**:
   - **OS:** Ubuntu 22.04 LTS (64-bit)
   - **RAM:** 2 GB minimum (4 GB recommended for video processing)
   - **CPU:** 2 vCPU minimum
   - **Storage:** 40 GB SSD minimum
   - **Region:** Choose closest to your users
3. Add your **SSH public key** during setup (or use password auth)
4. Note the server's **public IP address** (e.g. `157.245.88.123`)

---

### STEP 2 — Connect to Server via SSH

**From Windows (PowerShell or Command Prompt):**
```powershell
ssh root@157.245.88.123
```

**From Linux / macOS:**
```bash
ssh root@157.245.88.123
```

> If you used an SSH key: `ssh -i ~/.ssh/id_rsa root@157.245.88.123`

Once connected, you'll see a Linux terminal prompt like `root@ubuntu-server:~#`

---

### STEP 3 — Install System Packages

Run these commands to install everything the app needs:

```bash
# Update the package list
apt-get update && apt-get upgrade -y

# Install Python 3.11 and tools
apt-get install -y \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    git curl wget unzip

# Install FFmpeg (required for recording and video processing)
apt-get install -y ffmpeg

# Install Redis (required for real-time WebSocket features + Celery)
apt-get install -y redis-server
systemctl enable redis-server
systemctl start redis-server

# Install Nginx (web server / reverse proxy)
apt-get install -y nginx

# Install dlib build dependencies (for AI face recognition)
apt-get install -y \
    cmake build-essential \
    libopenblas-dev liblapack-dev \
    libx11-dev libgtk-3-dev

# Install certbot for free SSL
apt-get install -y certbot python3-certbot-nginx

# Install useful tools
apt-get install -y htop net-tools ufw fail2ban supervisor
```

Verify the key tools:
```bash
python3.11 --version    # Should print Python 3.11.x
ffmpeg -version         # Should print FFmpeg version
redis-cli ping          # Should print: PONG
nginx -v                # Should print: nginx version
```

---

### STEP 4 — Create a Dedicated App User

> Never run the app as root. Create a separate `edumi` user for security.

```bash
# Create the user
useradd -m -s /bin/bash edumi

# Give sudo access (needed for systemctl commands)
usermod -aG sudo edumi

# Switch to the edumi user to verify
su - edumi
whoami    # Should print: edumi
exit      # Go back to root
```

---

### STEP 5 — Download LiveKit Binary

LiveKit is the WebRTC server powering virtual classrooms.

```bash
# Create the directory
mkdir -p /opt/edumi/livekit-bin

# Download the latest Linux binary
cd /tmp
LIVEKIT_URL=$(curl -s https://api.github.com/repos/livekit/livekit/releases/latest \
    | grep "browser_download_url" | grep "linux_amd64.tar.gz" | head -1 \
    | cut -d '"' -f 4)

wget -O livekit.tar.gz "$LIVEKIT_URL"
tar -xzf livekit.tar.gz

# Move binary to app directory
mv livekit-server /opt/edumi/livekit-bin/livekit-server
chmod +x /opt/edumi/livekit-bin/livekit-server

# Verify
/opt/edumi/livekit-bin/livekit-server --version
```

---

### STEP 6 — Clone the Repository

```bash
# Clone the app code
git clone -b new_edumi https://github.com/GAuravgiy87/Edumi2.git /opt/edumi

# Set correct ownership
chown -R edumi:edumi /opt/edumi

# Enter the project directory
cd /opt/edumi
```

---

### STEP 7 — Python Virtual Environment & Dependencies

```bash
# Switch to edumi user
su - edumi
cd /opt/edumi

# Create virtual environment
python3.11 -m venv venv

# Activate it
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install all project dependencies
pip install -r requirements.txt

# Deactivate and go back to root
deactivate
exit
```

---

### STEP 8 — Configure Environment Variables

```bash
# Copy the example config
cp /opt/edumi/config/.env.example /opt/edumi/.env

# Generate a Django secret key
SECRET_KEY=$(sudo -u edumi /opt/edumi/venv/bin/python -c \
    "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")

# Generate a Fernet encryption key for face data
FACE_KEY=$(sudo -u edumi /opt/edumi/venv/bin/python -c \
    "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Generate LiveKit credentials
LIVEKIT_KEY="edumi-$(openssl rand -hex 8)"
LIVEKIT_SECRET="$(openssl rand -hex 32)"

echo "SECRET_KEY:    $SECRET_KEY"
echo "FACE_KEY:      $FACE_KEY"
echo "LIVEKIT_KEY:   $LIVEKIT_KEY"
echo "LIVEKIT_SECRET: $LIVEKIT_SECRET"
```

Now write the `.env` file (replace `YOUR_DOMAIN` with your actual domain):

```bash
nano /opt/edumi/.env
```

Paste this content (replace the placeholder values with the generated ones above):

```env
# ── Django Core ────────────────────────────────────────────────────────────────
SECRET_KEY=<paste-generated-secret-key>
DEBUG=False
ALLOWED_HOSTS=YOUR_DOMAIN,www.YOUR_DOMAIN,localhost,127.0.0.1

# ── HTTPS Security ─────────────────────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS=https://YOUR_DOMAIN,https://www.YOUR_DOMAIN
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# ── LiveKit WebRTC ─────────────────────────────────────────────────────────────
LIVEKIT_URL=wss://YOUR_DOMAIN/livekit-proxy
LIVEKIT_INTERNAL_URL=ws://localhost:7880
LIVEKIT_INTERNAL_HTTP_URL=http://localhost:7880
LIVEKIT_API_KEY=<paste-livekit-key>
LIVEKIT_API_SECRET=<paste-livekit-secret>

# ── Redis ──────────────────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Face Recognition ───────────────────────────────────────────────────────────
FACE_ENCRYPTION_KEY=<paste-face-key>
FACE_MATCH_THRESHOLD=0.50
FACE_PRESENCE_DURATION=30

# ── Camera Service ─────────────────────────────────────────────────────────────
CAMERA_SERVICE_URL=http://localhost:8003

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_LEVEL=WARNING
```

Save with `Ctrl+O`, `Enter`, `Ctrl+X`.

```bash
# Secure the file (only edumi user can read it)
chown edumi:edumi /opt/edumi/.env
chmod 600 /opt/edumi/.env
```

Now write the LiveKit config:

```bash
cat > /opt/edumi/config/livekit.yaml <<EOF
port: 7880
rtc:
  tcp_port: 7881
  udp_port: 7882
  use_external_ip: true

keys:
  <paste-livekit-key>: <paste-livekit-secret>

logging:
  level: warn
EOF

chown edumi:edumi /opt/edumi/config/livekit.yaml
```

---

### STEP 9 — Database Migrations & Static Files

```bash
cd /opt/edumi

# Run database migrations
sudo -u edumi venv/bin/python manage.py migrate --noinput

# Collect all static files
sudo -u edumi venv/bin/python manage.py collectstatic --noinput

# Create media directories
mkdir -p /opt/edumi/database/media/recordings
chown -R edumi:edumi /opt/edumi/database
```

---

### STEP 10 — Generate SSL Certificate (Internal)

The app uses an internal self-signed certificate for direct Daphne HTTPS. Nginx will sit in front and use Let's Encrypt.

```bash
sudo -u edumi /opt/edumi/venv/bin/python \
    /opt/edumi/scripts/generate_ssl_cert.py \
    --domain YOUR_DOMAIN

# Verify certificates exist
ls -la /opt/edumi/certs/
# Should show: edumi.crt  edumi.key
```

---

### STEP 11 — Create Systemd Services (Auto-Restart)

These services automatically start on boot and restart if they crash.

#### 11a — Django Web Server

```bash
cat > /etc/systemd/system/edumi-web.service <<'EOF'
[Unit]
Description=EduMi 2 — Django/Daphne Web Server
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=edumi
Group=edumi
WorkingDirectory=/opt/edumi
EnvironmentFile=/opt/edumi/.env
Environment="PATH=/opt/edumi/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/edumi/venv/bin/daphne \
    -e ssl:port=8002:certKey=/opt/edumi/certs/edumi.key:sslCertificate=/opt/edumi/certs/edumi.crt \
    school_project.asgi:application
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=edumi-web

[Install]
WantedBy=multi-user.target
EOF
```

#### 11b — Celery Background Worker

```bash
cat > /etc/systemd/system/edumi-celery.service <<'EOF'
[Unit]
Description=EduMi 2 — Celery Background Worker
After=redis.service
Wants=redis.service

[Service]
Type=simple
User=edumi
Group=edumi
WorkingDirectory=/opt/edumi
EnvironmentFile=/opt/edumi/.env
Environment="PATH=/opt/edumi/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/edumi/venv/bin/celery -A school_project worker \
    -l warning -P threads --concurrency=4
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=edumi-celery

[Install]
WantedBy=multi-user.target
EOF
```

#### 11c — Camera AI Service

```bash
cat > /etc/systemd/system/edumi-camera.service <<'EOF'
[Unit]
Description=EduMi 2 — Camera AI Microservice
After=network.target

[Service]
Type=simple
User=edumi
Group=edumi
WorkingDirectory=/opt/edumi
EnvironmentFile=/opt/edumi/.env
Environment="PATH=/opt/edumi/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/edumi/venv/bin/python camera_service/serve.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=edumi-camera

[Install]
WantedBy=multi-user.target
EOF
```

#### 11d — LiveKit WebRTC Server

```bash
cat > /etc/systemd/system/edumi-livekit.service <<'EOF'
[Unit]
Description=EduMi 2 — LiveKit WebRTC SFU
After=network.target

[Service]
Type=simple
User=edumi
Group=edumi
WorkingDirectory=/opt/edumi
ExecStart=/opt/edumi/livekit-bin/livekit-server --config /opt/edumi/config/livekit.yaml
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=edumi-livekit

[Install]
WantedBy=multi-user.target
EOF
```

#### 11e — Auto-Healing Watchdog

```bash
cat > /etc/systemd/system/edumi-watchdog.service <<'EOF'
[Unit]
Description=EduMi 2 — Health Watchdog (Auto-Restart Crashed Services)
After=edumi-web.service

[Service]
Type=simple
User=root
ExecStart=/opt/edumi/scripts/healthcheck.sh
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=edumi-watchdog

[Install]
WantedBy=multi-user.target
EOF

chmod +x /opt/edumi/scripts/healthcheck.sh
chmod +x /opt/edumi/scripts/update.sh
```

#### Enable and Start All Services

```bash
# Reload systemd
systemctl daemon-reload

# Enable services (start on boot)
systemctl enable edumi-web edumi-celery edumi-camera edumi-livekit edumi-watchdog redis-server

# Start all services now
systemctl start edumi-web edumi-celery edumi-camera edumi-livekit edumi-watchdog

# Check status of all
for svc in edumi-web edumi-celery edumi-camera edumi-livekit edumi-watchdog; do
    echo "── $svc ──"
    systemctl is-active $svc
done
```

---

### STEP 12 — Configure Nginx Reverse Proxy

```bash
# Remove default site
rm -f /etc/nginx/sites-enabled/default

# Create EduMi site config
nano /etc/nginx/sites-available/edumi
```

Paste this (replace `YOUR_DOMAIN` with your actual domain):

```nginx
# Redirect HTTP → HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name YOUR_DOMAIN www.YOUR_DOMAIN;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name YOUR_DOMAIN www.YOUR_DOMAIN;

    # SSL — Certbot will auto-update this block
    ssl_certificate     /opt/edumi/certs/edumi.crt;
    ssl_certificate_key /opt/edumi/certs/edumi.key;

    # Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;

    # Max upload (for video files)
    client_max_body_size 2G;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
    client_body_timeout 300s;

    # Static files (served directly by Nginx — fast!)
    location /static/ {
        alias /opt/edumi/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Media files (uploads, recordings)
    location /media/ {
        alias /opt/edumi/database/media/;
        expires 7d;
        add_header Cache-Control "public";
        access_log off;
    }

    # LiveKit WebRTC proxy
    location /livekit-proxy/ {
        proxy_pass http://127.0.0.1:7880/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }

    # Django WebSockets (Channels)
    location /ws/ {
        proxy_pass https://127.0.0.1:8002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
    }

    # Everything else → Django/Daphne
    location / {
        proxy_pass https://127.0.0.1:8002;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }
}
```

```bash
# Enable the site
ln -sf /etc/nginx/sites-available/edumi /etc/nginx/sites-enabled/edumi

# Test config
nginx -t

# Reload Nginx
systemctl reload nginx
systemctl enable nginx
```

---

### STEP 13 — Free SSL with Let's Encrypt

> ⚠️ **DNS must be pointing to your server IP before this step** (see Step 15 first if needed, then come back)

```bash
# Get a free SSL certificate
certbot --nginx \
    -d YOUR_DOMAIN \
    -d www.YOUR_DOMAIN \
    --non-interactive \
    --agree-tos \
    --email admin@YOUR_DOMAIN \
    --redirect

# Set up auto-renewal (runs daily at 3am)
(crontab -l 2>/dev/null; echo "0 3 * * * /usr/bin/certbot renew --quiet && systemctl reload nginx") | crontab -

echo "✅ SSL certificate installed!"
```

Verify: visit `https://YOUR_DOMAIN` — you should see a green padlock with no warnings.

---

### STEP 14 — Configure Firewall

```bash
# Reset UFW to defaults
ufw --force reset

# Default: block all incoming, allow all outgoing
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (CRITICAL — don't lock yourself out!)
ufw allow ssh

# Allow web traffic
ufw allow 80/tcp     # HTTP (redirects to HTTPS)
ufw allow 443/tcp    # HTTPS

# Allow LiveKit WebRTC ports
ufw allow 7881/tcp   # LiveKit TCP relay
ufw allow 7882/udp   # LiveKit UDP (WebRTC media)

# Enable firewall
ufw --force enable

# Verify
ufw status verbose
```

---

### STEP 15 — Configure DNS

> Do this at your domain registrar (Namecheap, GoDaddy, Cloudflare, etc.)

1. Log into your domain registrar
2. Go to **DNS Management** for your domain
3. Add these DNS records:

| Type | Name | Value | TTL |
|---|---|---|---|
| `A` | `@` or `yourdomain.com` | `your-server-ip` | 300 |
| `A` | `www` | `your-server-ip` | 300 |

4. Save and wait 5–30 minutes for propagation

**Verify DNS is working:**
```bash
# On your local machine (not the server)
nslookup YOUR_DOMAIN

# Should return your server's IP address
```

**Or check online:** https://dnschecker.org

---

### STEP 16 — Create Admin Account

```bash
cd /opt/edumi
sudo -u edumi venv/bin/python manage.py createsuperuser
```

Enter:
- **Username:** `admin` (or anything you want)
- **Email:** your email address
- **Password:** a strong password (min 8 chars)

---

### STEP 17 — Verify Everything is Running

```bash
# Check all services
systemctl status edumi-web edumi-celery edumi-camera edumi-livekit

# Check the health endpoint
curl -k https://localhost:8002/health/
# Expected: {"status": "ok", "db": true, "version": "2.0"}

# Check Nginx
curl -I https://YOUR_DOMAIN/
# Expected: HTTP/2 200

# Check Redis
redis-cli ping
# Expected: PONG

# Check ports are open
ss -tlnp | grep -E '8002|8003|7880|6379|80|443'
```

**Open your browser and visit:**
```
https://YOUR_DOMAIN         → EduMi login page
https://YOUR_DOMAIN/admin/  → Django admin panel
https://YOUR_DOMAIN/health/ → Health check JSON
```

---

## 🐕 Auto-Healing Watchdog

The watchdog service (`edumi-watchdog`) runs every **30 seconds** in the background. It automatically:

| What it detects | What it does |
|---|---|
| Any crashed service | Restarts it automatically |
| HTTP 502/503 response | Restarts Django web server |
| Redis connection failure | Restarts Redis + Celery + Web |
| Disk usage > 90% | Sends alert to log |
| RAM < 200 MB | Restarts memory-heavy services |
| Stale incomplete recording files | Cleans them up |

**View watchdog logs:**
```bash
journalctl -u edumi-watchdog -f
```

---

## 🔄 Updating the App

When you push new code to GitHub, deploy to the server with one command:

```bash
# SSH into your server
ssh root@your-server-ip

# Run the update script
sudo bash /opt/edumi/scripts/update.sh
```

This automatically:
1. Pulls the latest code from GitHub
2. Installs any new Python dependencies
3. Runs database migrations
4. Collects static files
5. Restarts all services gracefully

---

## 📊 Monitoring & Logs

### View live logs:
```bash
# Django web app
journalctl -u edumi-web -f

# Celery background tasks
journalctl -u edumi-celery -f

# Camera AI service
journalctl -u edumi-camera -f

# LiveKit WebRTC
journalctl -u edumi-livekit -f

# Auto-healing watchdog
journalctl -u edumi-watchdog -f

# All EduMi logs together
journalctl -u edumi-web -u edumi-celery -u edumi-camera -u edumi-livekit -f

# Nginx access log
tail -f /var/log/nginx/access.log

# Nginx error log
tail -f /var/log/nginx/error.log
```

### Useful service commands:
```bash
# Restart a service
systemctl restart edumi-web

# Stop a service
systemctl stop edumi-web

# See last 50 log lines
journalctl -u edumi-web -n 50

# Check disk usage
df -h /opt/edumi

# Check memory usage
free -h

# Check CPU / process status
htop
```

### Health Check:
```bash
# Quick health check
curl https://YOUR_DOMAIN/health/
```

Set up **free uptime monitoring** at https://uptimerobot.com — add your `/health/` URL and get email/SMS alerts if the app goes down.

---

## 🔧 Troubleshooting

### ❌ Service fails to start

```bash
# Check detailed error
journalctl -u edumi-web -n 50 --no-pager

# Common fix: check .env is correct
cat /opt/edumi/.env

# Check Python environment
/opt/edumi/venv/bin/python -c "import django; print(django.__version__)"
```

### ❌ Nginx returns 502 Bad Gateway

```bash
# Check if Django is running
systemctl is-active edumi-web

# Restart Django
systemctl restart edumi-web

# Check Nginx config
nginx -t
```

### ❌ SSL certificate error in browser

```bash
# Check cert expiry
openssl x509 -in /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem -noout -dates

# Renew manually
certbot renew --force-renewal
systemctl reload nginx
```

### ❌ WebRTC / Meetings not working

```bash
# Check LiveKit is running
systemctl status edumi-livekit

# Check UDP port is open
ufw status | grep 7882

# View LiveKit logs
journalctl -u edumi-livekit -n 50
```

### ❌ Camera feed not working on server

```bash
# Camera service must be able to reach the RTSP IP
ping <camera-ip>

# Check camera service is running
systemctl status edumi-camera

# Test RTSP URL from server
ffprobe rtsp://username:password@camera-ip:554/live
```

### ❌ Out of disk space

```bash
# Check disk usage
df -h

# Find large files
du -sh /opt/edumi/database/media/recordings/*

# Delete old recordings (older than 30 days)
find /opt/edumi/database/media/recordings -mtime +30 -type f -delete
```

### ❌ Database migration error

```bash
# Run with verbose output
sudo -u edumi /opt/edumi/venv/bin/python manage.py migrate --verbosity 2

# Reset and re-migrate (WARNING: deletes all data)
sudo -u edumi /opt/edumi/venv/bin/python manage.py migrate --run-syncdb
```

---

## 📋 Quick Reference Card

```
╔══════════════════════════════════════════════════════════════════╗
║                    EduMi 2 — Server Quick Reference              ║
╠══════════════════════════════════════════════════════════════════╣
║  App Directory   /opt/edumi                                      ║
║  App User        edumi                                           ║
║  Config File     /opt/edumi/.env                                 ║
║                                                                  ║
║  Services:                                                       ║
║    edumi-web       Django/Daphne ASGI    :8002 (internal)        ║
║    edumi-celery    Background tasks                              ║
║    edumi-camera    Camera AI service     :8003 (internal)        ║
║    edumi-livekit   WebRTC SFU            :7880 (internal)        ║
║    edumi-watchdog  Auto-healing watchdog                         ║
║    nginx           Reverse proxy         :80/:443 (public)       ║
║    redis-server    Message broker        :6379 (internal)        ║
║                                                                  ║
║  Key Commands:                                                   ║
║    Start all      systemctl start edumi-web edumi-celery ...     ║
║    Restart web    systemctl restart edumi-web                    ║
║    View logs      journalctl -u edumi-web -f                     ║
║    Update code    sudo bash /opt/edumi/scripts/update.sh         ║
║    Health check   curl https://YOUR_DOMAIN/health/               ║
║    Admin panel    https://YOUR_DOMAIN/admin/                     ║
╚══════════════════════════════════════════════════════════════════╝
```

---

<div align="center">

**Need help?** Open an issue at [github.com/GAuravgiy87/Edumi2/issues](https://github.com/GAuravgiy87/Edumi2/issues)

</div>
