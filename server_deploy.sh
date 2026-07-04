#!/bin/bash
# ==============================================================================
#  EduMi 2 — Full Server Deploy Script
#  Tested on: Ubuntu 22.04 LTS / Debian 12
#
#  USAGE:
#    chmod +x server_deploy.sh
#    sudo bash server_deploy.sh --domain yourdomain.com --email admin@yourdomain.com
#
#  OPTIONS:
#    --domain    Your domain name (required)
#    --email     Let's Encrypt notification email (required)
#    --branch    Git branch to deploy (default: new_edumi)
#    --repo      Git repo URL (default: official EduMi repo)
#    --no-ssl    Skip Let's Encrypt (use self-signed cert instead)
#    --no-nginx  Skip Nginx setup (raw Daphne only)
# ==============================================================================

set -euo pipefail

# ─── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step() { echo -e "\n${BOLD}${CYAN}══════════════════════════════════════════${NC}"; echo -e "${BOLD}${CYAN}  $1${NC}"; echo -e "${BOLD}${CYAN}══════════════════════════════════════════${NC}"; }

# ─── Defaults ─────────────────────────────────────────────────────────────────
DOMAIN=""
EMAIL=""
BRANCH="new_edumi"
REPO="https://github.com/GAuravgiy87/Edumi2.git"
USE_SSL=true
USE_NGINX=true
APP_USER="edumi"
APP_DIR="/opt/edumi"
PYTHON_VERSION="python3.11"

# ─── Parse Arguments ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)   DOMAIN="$2";   shift 2 ;;
        --email)    EMAIL="$2";    shift 2 ;;
        --branch)   BRANCH="$2";   shift 2 ;;
        --repo)     REPO="$2";     shift 2 ;;
        --no-ssl)   USE_SSL=false; shift   ;;
        --no-nginx) USE_NGINX=false; shift ;;
        *) warn "Unknown option: $1"; shift ;;
    esac
done

[[ -z "$DOMAIN" ]] && err "Missing --domain. Usage: sudo bash server_deploy.sh --domain yourdomain.com --email you@example.com"
[[ "$USE_SSL" == true && -z "$EMAIL" ]] && err "Missing --email (required for Let's Encrypt). Use --no-ssl to skip."

echo ""
echo -e "${BOLD}${GREEN}"
echo "  ███████╗██████╗ ██╗   ██╗███╗   ███╗██╗    ██████╗ "
echo "  ██╔════╝██╔══██╗██║   ██║████╗ ████║██║    ╚════██╗"
echo "  █████╗  ██║  ██║██║   ██║██╔████╔██║██║     █████╔╝"
echo "  ██╔══╝  ██║  ██║██║   ██║██║╚██╔╝██║██║    ██╔═══╝ "
echo "  ███████╗██████╔╝╚██████╔╝██║ ╚═╝ ██║██║    ███████╗"
echo "  ╚══════╝╚═════╝  ╚═════╝ ╚═╝     ╚═╝╚═╝    ╚══════╝"
echo -e "${NC}"
echo -e "  ${BOLD}Server Production Deployment${NC}"
echo -e "  Domain  : ${CYAN}${DOMAIN}${NC}"
echo -e "  SSL     : ${CYAN}${USE_SSL}${NC}"
echo -e "  Branch  : ${CYAN}${BRANCH}${NC}"
echo -e "  App Dir : ${CYAN}${APP_DIR}${NC}"
echo ""

# ─── Root check ───────────────────────────────────────────────────────────────
[[ "$EUID" -ne 0 ]] && err "Run this script as root: sudo bash server_deploy.sh ..."

# ==============================================================================
step "STEP 1 / 10 — System Packages"
# ==============================================================================

apt-get update -qq
apt-get install -y -qq \
    git curl wget unzip \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    ffmpeg \
    redis-server \
    nginx \
    cmake build-essential \
    libopenblas-dev liblapack-dev libx11-dev libgtk-3-dev \
    supervisor \
    ufw fail2ban \
    htop net-tools

if [[ "$USE_SSL" == true ]]; then
    apt-get install -y -qq certbot python3-certbot-nginx
fi

log "System packages installed"

# ==============================================================================
step "STEP 2 / 10 — Create App User"
# ==============================================================================

if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$APP_USER"
    log "Created user: $APP_USER"
else
    log "User $APP_USER already exists"
fi

# ==============================================================================
step "STEP 3 / 10 — Clone / Update Repository"
# ==============================================================================

if [[ -d "$APP_DIR/.git" ]]; then
    info "Repository already exists — pulling latest changes..."
    cd "$APP_DIR"
    sudo -u "$APP_USER" git fetch origin
    sudo -u "$APP_USER" git checkout "$BRANCH"
    sudo -u "$APP_USER" git pull origin "$BRANCH"
else
    info "Cloning repository..."
    git clone -b "$BRANCH" "$REPO" "$APP_DIR"
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
fi

log "Repository ready at $APP_DIR"

# ==============================================================================
step "STEP 4 / 10 — Python Virtual Environment & Dependencies"
# ==============================================================================

cd "$APP_DIR"
sudo -u "$APP_USER" $PYTHON_VERSION -m venv venv
sudo -u "$APP_USER" venv/bin/pip install --upgrade pip setuptools wheel -q
sudo -u "$APP_USER" venv/bin/pip install -r requirements.txt -q

log "Python dependencies installed"

# ==============================================================================
step "STEP 5 / 10 — Download LiveKit Server Binary"
# ==============================================================================

LIVEKIT_DIR="$APP_DIR/livekit-bin"
mkdir -p "$LIVEKIT_DIR"

if [[ ! -f "$LIVEKIT_DIR/livekit-server" ]]; then
    info "Downloading LiveKit server binary..."
    LIVEKIT_URL=$(curl -s https://api.github.com/repos/livekit/livekit/releases/latest \
        | grep "browser_download_url" | grep "linux_amd64.tar.gz" | head -1 \
        | cut -d '"' -f 4)
    wget -q -O /tmp/livekit.tar.gz "$LIVEKIT_URL"
    tar -xzf /tmp/livekit.tar.gz -C "$LIVEKIT_DIR" livekit-server
    rm /tmp/livekit.tar.gz
    chmod +x "$LIVEKIT_DIR/livekit-server"
    log "LiveKit binary downloaded"
else
    log "LiveKit binary already exists"
fi

chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# ==============================================================================
step "STEP 6 / 10 — Environment Configuration"
# ==============================================================================

ENV_FILE="$APP_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    info "Creating .env from template..."
    cp "$APP_DIR/config/.env.example" "$ENV_FILE"

    # Generate Django secret key
    SECRET_KEY=$(sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" -c \
        "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")

    # Generate Fernet face encryption key
    FACE_KEY=$(sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" -c \
        "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

    # Generate LiveKit credentials
    LIVEKIT_KEY="edumi-$(openssl rand -hex 8)"
    LIVEKIT_SECRET="$(openssl rand -hex 32)"

    cat > "$ENV_FILE" <<ENVEOF
# Auto-generated by server_deploy.sh on $(date)
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN},localhost,127.0.0.1

CSRF_TRUSTED_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}

# LiveKit WebRTC
LIVEKIT_URL=wss://${DOMAIN}/livekit-proxy
LIVEKIT_INTERNAL_URL=ws://localhost:7880
LIVEKIT_INTERNAL_HTTP_URL=http://localhost:7880
LIVEKIT_API_KEY=${LIVEKIT_KEY}
LIVEKIT_API_SECRET=${LIVEKIT_SECRET}

# Redis
REDIS_URL=redis://localhost:6379/0

# Face Recognition
FACE_ENCRYPTION_KEY=${FACE_KEY}
FACE_MATCH_THRESHOLD=0.50
FACE_PRESENCE_DURATION=30

# Camera Service
CAMERA_SERVICE_URL=http://localhost:8003

# Logging
LOG_LEVEL=WARNING
ENVEOF

    chown "$APP_USER:$APP_USER" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    log ".env created with auto-generated secrets"

    # Write LiveKit config
    LIVEKIT_CONFIG="$APP_DIR/config/livekit.yaml"
    cat > "$LIVEKIT_CONFIG" <<LKEOF
port: 7880
rtc:
  tcp_port: 7881
  udp_port: 7882
  use_external_ip: true

keys:
  ${LIVEKIT_KEY}: ${LIVEKIT_SECRET}

logging:
  level: warn
LKEOF
    chown "$APP_USER:$APP_USER" "$LIVEKIT_CONFIG"
    log "LiveKit config written"
else
    warn ".env already exists — skipping auto-generation (edit manually if needed)"
fi

# ==============================================================================
step "STEP 7 / 10 — Database & Static Files"
# ==============================================================================

cd "$APP_DIR"
sudo -u "$APP_USER" venv/bin/python manage.py migrate --noinput
sudo -u "$APP_USER" venv/bin/python manage.py collectstatic --noinput -v 0
log "Database migrated and static files collected"

# Create media directories
mkdir -p "$APP_DIR/database/media/recordings"
chown -R "$APP_USER:$APP_USER" "$APP_DIR/database"
log "Media directories created"

# ==============================================================================
step "STEP 8 / 10 — Systemd Services (Auto-Restart)"
# ==============================================================================

# ── Redis ──────────────────────────────────────────────────────────────────────
systemctl enable redis-server
systemctl start redis-server

# ── Django / Daphne ───────────────────────────────────────────────────────────
cat > /etc/systemd/system/edumi-web.service <<EOF
[Unit]
Description=EduMi 2 — Django/Daphne ASGI Server
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
Environment="PATH=${APP_DIR}/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=${APP_DIR}/venv/bin/daphne \
    -e ssl:port=8002:certKey=${APP_DIR}/certs/edumi.key:sslCertificate=${APP_DIR}/certs/edumi.crt \
    school_project.asgi:application
Restart=always
RestartSec=5
StartLimitInterval=60
StartLimitBurst=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=edumi-web

# Auto-heal: restart if memory exceeds 1GB
MemoryMax=1G
MemorySwapMax=0

[Install]
WantedBy=multi-user.target
EOF

# ── Celery Worker ──────────────────────────────────────────────────────────────
cat > /etc/systemd/system/edumi-celery.service <<EOF
[Unit]
Description=EduMi 2 — Celery Background Worker
After=redis.service
Wants=redis.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
Environment="PATH=${APP_DIR}/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=${APP_DIR}/venv/bin/celery -A school_project worker \
    -l warning -P threads --concurrency=4
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=edumi-celery

[Install]
WantedBy=multi-user.target
EOF

# ── Camera AI Service ──────────────────────────────────────────────────────────
cat > /etc/systemd/system/edumi-camera.service <<EOF
[Unit]
Description=EduMi 2 — Camera AI Microservice
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
Environment="PATH=${APP_DIR}/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=${APP_DIR}/venv/bin/python camera_service/serve.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=edumi-camera

[Install]
WantedBy=multi-user.target
EOF

# ── LiveKit WebRTC SFU ─────────────────────────────────────────────────────────
cat > /etc/systemd/system/edumi-livekit.service <<EOF
[Unit]
Description=EduMi 2 — LiveKit WebRTC SFU
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/livekit-bin/livekit-server --config ${APP_DIR}/config/livekit.yaml
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=edumi-livekit

[Install]
WantedBy=multi-user.target
EOF

# ── Health Watchdog ────────────────────────────────────────────────────────────
cat > /etc/systemd/system/edumi-watchdog.service <<EOF
[Unit]
Description=EduMi 2 — Health Watchdog
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

# ── Enable all services ────────────────────────────────────────────────────────
systemctl daemon-reload
for svc in edumi-web edumi-celery edumi-camera edumi-livekit edumi-watchdog; do
    systemctl enable "$svc"
    log "Enabled: $svc"
done

log "All systemd services configured"

# ==============================================================================
step "STEP 9 / 10 — SSL Certificate & Nginx"
# ==============================================================================

# Generate self-signed cert first (used internally by Daphne)
sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" "$APP_DIR/scripts/generate_ssl_cert.py" \
    --domain "$DOMAIN" || true

if [[ "$USE_NGINX" == true ]]; then

    # Write Nginx config
    cat > /etc/nginx/sites-available/edumi <<NGINXEOF
# EduMi 2 — Nginx Production Config
# Auto-generated by server_deploy.sh

# Rate limiting zones
limit_req_zone \$binary_remote_addr zone=api:10m rate=30r/m;
limit_req_zone \$binary_remote_addr zone=login:10m rate=10r/m;

# Redirect HTTP → HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} www.${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN} www.${DOMAIN};

    # SSL — replaced by certbot after Let's Encrypt
    ssl_certificate     ${APP_DIR}/certs/edumi.crt;
    ssl_certificate_key ${APP_DIR}/certs/edumi.key;

    # SSL hardening
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Max upload size (for video uploads)
    client_max_body_size 2G;
    client_body_timeout 300s;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;

    # Static files — served directly by Nginx (fast)
    location /static/ {
        alias ${APP_DIR}/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
        gzip_static on;
    }

    # Media files
    location /media/ {
        alias ${APP_DIR}/database/media/;
        expires 7d;
        add_header Cache-Control "public";
        access_log off;
    }

    # LiveKit WebRTC proxy (WebSocket upgrade)
    location /livekit-proxy/ {
        proxy_pass http://127.0.0.1:7880/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_read_timeout 3600s;
    }

    # Django WebSocket (Channels)
    location /ws/ {
        proxy_pass https://127.0.0.1:8002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 3600s;
    }

    # Rate-limit login endpoint
    location /login/ {
        limit_req zone=login burst=5 nodelay;
        proxy_pass https://127.0.0.1:8002;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # All other requests → Django/Daphne
    location / {
        proxy_pass https://127.0.0.1:8002;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_buffering off;
    }
}
NGINXEOF

    # Enable site
    ln -sf /etc/nginx/sites-available/edumi /etc/nginx/sites-enabled/edumi
    rm -f /etc/nginx/sites-enabled/default

    nginx -t && systemctl reload nginx
    log "Nginx configured"

    # Get Let's Encrypt cert
    if [[ "$USE_SSL" == true ]]; then
        info "Obtaining Let's Encrypt certificate..."
        certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" \
            --non-interactive --agree-tos --email "$EMAIL" \
            --redirect || warn "Let's Encrypt failed — using self-signed cert (check DNS propagation)"

        # Auto-renew cron
        (crontab -l 2>/dev/null; echo "0 3 * * * /usr/bin/certbot renew --quiet && systemctl reload nginx") | crontab -
        log "SSL auto-renewal scheduled (daily at 3am)"
    fi
fi

# ==============================================================================
step "STEP 10 / 10 — Firewall & Start Services"
# ==============================================================================

# UFW Firewall
ufw --force reset > /dev/null 2>&1
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 7881/tcp   # LiveKit TCP
ufw allow 7882/udp   # LiveKit UDP (WebRTC)
echo "y" | ufw enable
log "Firewall configured"

# Start all EduMi services
for svc in edumi-web edumi-celery edumi-camera edumi-livekit edumi-watchdog; do
    systemctl start "$svc" || warn "Service $svc failed to start (check: journalctl -u $svc)"
done

# Verify
sleep 3
echo ""
echo -e "${BOLD}Service Status:${NC}"
for svc in edumi-web edumi-celery edumi-camera edumi-livekit; do
    STATUS=$(systemctl is-active "$svc" 2>/dev/null || echo "inactive")
    if [[ "$STATUS" == "active" ]]; then
        echo -e "  ${GREEN}●${NC} $svc — active"
    else
        echo -e "  ${RED}●${NC} $svc — $STATUS  (run: journalctl -u $svc -n 50)"
    fi
done

# ==============================================================================
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║        🎉  DEPLOYMENT COMPLETE!                     ║${NC}"
echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}${GREEN}║${NC}  App URL : ${CYAN}https://${DOMAIN}${NC}"
echo -e "${BOLD}${GREEN}║${NC}  Admin   : ${CYAN}https://${DOMAIN}/admin/${NC}"
echo -e "${BOLD}${GREEN}║${NC}  Logs    : ${CYAN}journalctl -u edumi-web -f${NC}"
echo -e "${BOLD}${GREEN}║${NC}  Restart : ${CYAN}systemctl restart edumi-web${NC}"
echo -e "${BOLD}${GREEN}║${NC}  Update  : ${CYAN}bash ${APP_DIR}/scripts/update.sh${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Point your DNS A record: ${DOMAIN} → $(curl -s ifconfig.me 2>/dev/null || echo 'your-server-ip')"
echo "  2. Create admin account: sudo -u ${APP_USER} ${APP_DIR}/venv/bin/python ${APP_DIR}/manage.py createsuperuser"
echo "  3. Watch logs: journalctl -u edumi-web -f"
echo ""
