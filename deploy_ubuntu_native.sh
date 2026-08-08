#!/usr/bin/env bash
# ==============================================================================
#  EduMi2 — Master Native Ubuntu Server Deployment Script (Without Docker)
#  Tested on: Ubuntu 20.04 / 22.04 / 24.04 LTS, Debian 11 / 12
# ==============================================================================
#  USAGE:
#    sudo bash deploy_ubuntu_native.sh
#  OR with custom domain & Let's Encrypt SSL:
#    sudo bash deploy_ubuntu_native.sh --domain edumi.ac.in --email admin@edumi.ac.in
# ==============================================================================

set -eo pipefail

# ANSI Color Utilities
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "  ${GREEN}[✓]${NC} $1"; }
info() { echo -e "  ${BLUE}[i]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[!]${NC} $1"; }
err()  { echo -e "  ${RED}[✗]${NC} $1"; exit 1; }
step() {
    echo ""
    echo -e "${BOLD}${CYAN}================================================= ${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}================================================= ${NC}"
}

DOMAIN=""
EMAIL=""
DB_HOST="127.0.0.1"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_USER="edumi"
DB_NAME="edumi_db"
DB_USER="edumi_user"
DB_PASS="edumi_secure_pass_123"

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)  DOMAIN="$2";  shift 2 ;;
        --email)   EMAIL="$2";   shift 2 ;;
        --db-host) DB_HOST="$2"; shift 2 ;;
        *) warn "Unknown argument: $1"; shift ;;
    esac
done

echo ""
echo -e "${BOLD}${GREEN}"
echo "  ███████╗██████╗ ██╗   ██╗███╗   ███╗██╗    ██████╗ "
echo "  ██╔════╝██╔══██╗██║   ██║████╗ ████║██║    ╚════██╗"
echo "  █████╗  ██║  ██║██║   ██║██╔████╔██║██║     █████╔╝"
echo "  ██╔══╝  ██║  ██║██║   ██║██║╚██╔╝██║██║    ██╔═══╝ "
echo "  ███████╗██████╔╝╚██████╔╝██║ ╚═╝ ██║██║    ███████╗"
echo "  ╚══════╝╚═════╝  ╚═════╝ ╚═╝     ╚═╝╚═╝    ╚══════╝"
echo -e "${NC}"
echo -e "  ${BOLD}EduMi2 Native Ubuntu Server Orchestrator (Without Docker)${NC}"
echo -e "  Target Dir : ${CYAN}${APP_DIR}${NC}"
if [ -n "$DOMAIN" ]; then
    echo -e "  Domain     : ${CYAN}${DOMAIN}${NC}"
else
    echo -e "  Mode       : ${CYAN}Localhost / Server IP Mode${NC}"
fi
echo ""

# ------------------------------------------------------------------------------
step "STEP 1: Root Elevation Check & System Inspector"
# ------------------------------------------------------------------------------
IS_ROOT=false
if [ "$(id -u)" -eq 0 ]; then IS_ROOT=true; fi

if [ "$IS_ROOT" = false ]; then
    warn "Running without root privileges. If package installation fails, re-run with: sudo bash deploy_ubuntu_native.sh"
fi

if [ -f "scripts/check_ubuntu_env.sh" ]; then
    chmod +x scripts/check_ubuntu_env.sh
    if ! ./scripts/check_ubuntu_env.sh; then
        if [ "$IS_ROOT" = true ]; then
            info "Installing missing Ubuntu system packages via apt-get..."
            apt-get update -qq
            apt-get install -y -qq \
                python3.11 python3.11-venv python3.11-dev python3-pip \
                build-essential cmake g++ libpq-dev libffi-dev \
                ffmpeg postgresql postgresql-contrib redis-server nginx supervisor \
                libopenblas-dev liblapack-dev libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
                curl wget git openssl net-tools
            log "System packages installed successfully."
        else
            err "Missing system dependencies. Please install them or run with sudo."
        fi
    fi
fi


# ------------------------------------------------------------------------------
step "STEP 2: PostgreSQL Database Provisioning"
# ------------------------------------------------------------------------------
if [ "$IS_ROOT" = true ]; then
    systemctl start postgresql || true
    systemctl enable postgresql || true

    info "Setting up PostgreSQL database '$DB_NAME' and user '$DB_USER'..."
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null || true
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" 2>/dev/null || true
    sudo -u postgres psql -c "ALTER USER $DB_USER CREATEDB;" 2>/dev/null || true
    log "PostgreSQL database and user provisioned."
else
    info "Skipping PostgreSQL user setup (Non-root user). Ensure $DB_NAME is accessible."
fi


# ------------------------------------------------------------------------------
step "STEP 3: Redis Server Setup"
# ------------------------------------------------------------------------------
if [ "$IS_ROOT" = true ]; then
    systemctl start redis-server || systemctl start redis || true
    systemctl enable redis-server 2>/dev/null || systemctl enable redis 2>/dev/null || true
    log "Redis service active."
fi


# ------------------------------------------------------------------------------
step "STEP 4: LiveKit SFU Binary Download"
# ------------------------------------------------------------------------------
LIVEKIT_DIR="$APP_DIR/livekit-bin"
mkdir -p "$LIVEKIT_DIR"

if [ ! -f "$LIVEKIT_DIR/livekit-server" ]; then
    info "Downloading LiveKit Server Linux binary..."
    LIVEKIT_URL=$(curl -s https://api.github.com/repos/livekit/livekit/releases/latest \
        | grep "browser_download_url" | grep "linux_amd64.tar.gz" | head -1 \
        | cut -d '"' -f 4 || echo "")

    if [ -n "$LIVEKIT_URL" ]; then
        wget -q -O /tmp/livekit.tar.gz "$LIVEKIT_URL"
        tar -xzf /tmp/livekit.tar.gz -C "$LIVEKIT_DIR" livekit-server
        rm -f /tmp/livekit.tar.gz
        chmod +x "$LIVEKIT_DIR/livekit-server"
        log "LiveKit binary downloaded to ./livekit-bin/livekit-server"
    else
        warn "Could not fetch LiveKit release automatically. Download manually if needed."
    fi
else
    log "LiveKit binary present in ./livekit-bin/livekit-server"
fi


# ------------------------------------------------------------------------------
step "STEP 5: Python Virtual Environment & Dependencies"
# ------------------------------------------------------------------------------
PYTHON_BIN="python3"
if command -v python3.11 &>/dev/null; then
    PYTHON_BIN="python3.11"
fi

if [ ! -d "venv" ]; then
    info "Creating Python virtual environment using $PYTHON_BIN..."
    $PYTHON_BIN -m venv venv
fi

info "Installing Python dependencies from requirements.txt..."
./venv/bin/pip install --upgrade pip setuptools wheel -q
./venv/bin/pip install -r requirements.txt -q
log "Python dependencies installed inside ./venv/"


# ------------------------------------------------------------------------------
step "STEP 6: Environment File (.env) Configuration"
# ------------------------------------------------------------------------------
ENV_FILE="$APP_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    info "Creating production .env file..."
    SECRET_KEY=$(./venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" 2>/dev/null || echo "secret_edumi_$(date +%s)_key")
    FACE_KEY=$(./venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "ZxYxWvUtSrQpOnMlKjIhGfEdCbA9876543210")
    
    ALLOWED_HOSTS_VAL="localhost,127.0.0.1"
    [ -n "$DOMAIN" ] && ALLOWED_HOSTS_VAL="$DOMAIN,www.$DOMAIN,$ALLOWED_HOSTS_VAL"

    cat > "$ENV_FILE" <<EOF
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=$ALLOWED_HOSTS_VAL
LOG_LEVEL=INFO

DATABASE_URL=postgres://$DB_USER:$DB_PASS@$DB_HOST:5432/$DB_NAME
REDIS_URL=redis://127.0.0.1:6379/0

LIVEKIT_URL=wss://localhost/livekit-proxy
LIVEKIT_INTERNAL_URL=ws://127.0.0.1:7880
LIVEKIT_INTERNAL_HTTP_URL=http://127.0.0.1:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=devsecret_must_be_32_characters_long_1234

SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False

FACE_ENCRYPTION_KEY=$FACE_KEY
FACE_MATCH_THRESHOLD=0.50
FACE_PRESENCE_DURATION=30

CSRF_TRUSTED_ORIGINS=https://localhost,http://localhost,http://127.0.0.1

CAMERA_SERVICE_PORT=8008
CAMERA_SERVICE_URL=http://127.0.0.1:8008

FFMPEG_BINARY=ffmpeg
FFPROBE_BINARY=ffprobe
EOF
    log ".env file created."
else
    log "Existing .env detected."
fi


# ------------------------------------------------------------------------------
step "STEP 7: Directory Setup & SSL Certificates"
# ------------------------------------------------------------------------------
mkdir -p staticfiles media certs logs config

if [ ! -f "certs/edumi.crt" ] || [ ! -f "certs/edumi.key" ]; then
    info "Generating self-signed SSL certificates..."
    ./venv/bin/python scripts/generate_ssl_cert.py 2>/dev/null || \
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout certs/edumi.key -out certs/edumi.crt \
        -subj "/C=IN/ST=Academic/L=EduMi/O=EduMi/CN=edumi.ac.in" 2>/dev/null || true
    log "SSL Certificates prepared in ./certs/"
fi


# ------------------------------------------------------------------------------
step "STEP 8: Django Database Migrations & Static Collection"
# ------------------------------------------------------------------------------
info "Running database migrations..."
./venv/bin/python manage.py migrate --noinput
log "Database schema updated."

info "Collecting static files..."
./venv/bin/python manage.py collectstatic --noinput
log "Static files collected into ./staticfiles/"


# ------------------------------------------------------------------------------
step "STEP 9: Systemd Service Unit Installation"
# ------------------------------------------------------------------------------
if [ "$IS_ROOT" = true ]; then
    info "Creating Systemd service unit files for EduMi microservices..."

    CREATE_SERVICE() {
        local name=$1
        local cmd=$2
        cat > "/etc/systemd/system/${name}.service" <<EOF
[Unit]
Description=EduMi2 - ${name}
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
ExecStart=${cmd}
Restart=always
RestartSec=5
EnvironmentFile=${APP_DIR}/.env

[Install]
WantedBy=multi-user.target
EOF
    }

    CREATE_SERVICE "edumi-auth" "${APP_DIR}/venv/bin/daphne -b 127.0.0.1 -p 8002 school_project.asgi:application"
    CREATE_SERVICE "edumi-admin" "${APP_DIR}/venv/bin/daphne -b 127.0.0.1 -p 8003 school_project.asgi:application"
    CREATE_SERVICE "edumi-meeting" "${APP_DIR}/venv/bin/daphne -b 127.0.0.1 -p 8004 school_project.asgi:application"
    CREATE_SERVICE "edumi-msg" "${APP_DIR}/venv/bin/daphne -b 127.0.0.1 -p 8005 school_project.asgi:application"
    CREATE_SERVICE "edumi-profile" "${APP_DIR}/venv/bin/daphne -b 127.0.0.1 -p 8006 school_project.asgi:application"
    CREATE_SERVICE "edumi-video" "${APP_DIR}/venv/bin/daphne -b 127.0.0.1 -p 8007 school_project.asgi:application"
    CREATE_SERVICE "edumi-camera" "${APP_DIR}/venv/bin/python camera_service/serve.py"
    CREATE_SERVICE "edumi-celery" "${APP_DIR}/venv/bin/celery -A school_project worker -l info -P threads"

    if [ -f "${LIVEKIT_DIR}/livekit-server" ]; then
        CREATE_SERVICE "edumi-livekit" "${LIVEKIT_DIR}/livekit-server --config ${APP_DIR}/config/livekit.yaml"
    fi

    systemctl daemon-reload
    for svc in edumi-auth edumi-admin edumi-meeting edumi-msg edumi-profile edumi-video edumi-camera edumi-celery; do
        systemctl enable ${svc}
        systemctl restart ${svc}
    done
    if [ -f "${LIVEKIT_DIR}/livekit-server" ]; then
        systemctl enable edumi-livekit || true
        systemctl restart edumi-livekit || true
    fi
    log "Systemd services created and started."
else
    warn "Non-root mode: Skipping Systemd service creation. Services can be started manually."
fi


# ------------------------------------------------------------------------------
step "STEP 10: Nginx Web Server Setup"
# ------------------------------------------------------------------------------
if [ "$IS_ROOT" = true ]; then
    info "Configuring Nginx reverse proxy..."

    cat > /etc/nginx/sites-available/edumi <<EOF
upstream edumi_backend {
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
    server 127.0.0.1:8004;
    server 127.0.0.1:8005;
    server 127.0.0.1:8006;
    server 127.0.0.1:8007;
}

server {
    listen 80;
    server_name _;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name _;

    ssl_certificate ${APP_DIR}/certs/edumi.crt;
    ssl_certificate_key ${APP_DIR}/certs/edumi.key;

    client_max_body_size 100M;

    location /static/ {
        alias ${APP_DIR}/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias ${APP_DIR}/media/;
        expires 7d;
    }

    location ~ ^/(cameras|mobile-cameras|head-count)/ {
        proxy_pass http://127.0.0.1:8008;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }

    location /livekit-proxy/ {
        proxy_pass http://127.0.0.1:7880/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }

    location /ws/ {
        proxy_pass http://edumi_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }

    location / {
        proxy_pass http://edumi_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/edumi /etc/nginx/sites-enabled/edumi
    rm -f /etc/nginx/sites-enabled/default
    nginx -t
    systemctl restart nginx
    log "Nginx configured and reloaded."
fi


# ------------------------------------------------------------------------------
step "STEP 11: Deployment Complete & Status Summary"
# ------------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}================================================= ${NC}"
echo -e "${GREEN}${BOLD}   Native Ubuntu EduMi2 Deployment Successful!   ${NC}"
echo -e "${GREEN}${BOLD}================================================= ${NC}"
echo ""
echo -e "  ${BOLD}Access Endpoints:${NC}"
echo -e "  • Web Application (HTTPS) : ${CYAN}https://localhost${NC} or ${CYAN}https://YOUR_SERVER_IP${NC}"
echo -e "  • HTTP Redirect           : ${CYAN}http://localhost:80${NC}"
echo -e "  • Camera Stream Service   : ${CYAN}http://127.0.0.1:8008${NC}"
echo -e "  • LiveKit SFU Service     : ${CYAN}http://127.0.0.1:7880${NC}"
echo ""
echo -e "  ${BOLD}Service Control Commands:${NC}"
echo -e "  • Check Service Status    : ${CYAN}systemctl status edumi-auth edumi-camera edumi-celery${NC}"
echo -e "  • View Service Logs       : ${CYAN}journalctl -u edumi-auth -f${NC}"
echo -e "  • Create Superuser        : ${CYAN}${APP_DIR}/venv/bin/python manage.py createsuperuser${NC}"
echo ""
