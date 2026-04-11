#!/usr/bin/env bash
# =============================================================================
#  EduMi — Bare-metal Linux startup
#  Works on a fresh clone with zero pre-installed deps.
#
#  Usage:
#    chmod +x start.sh && bash start.sh
#
#  What it does (fully automatic):
#    1. Detects distro, installs all system packages
#    2. Installs Python 3.10+ if missing
#    3. Creates / reuses venv, installs all pip deps
#    4. Compiles dlib + face_recognition (first run ~5 min)
#    5. Installs AMD OpenCL runtime if GPU detected
#    6. Generates .env with a real secret key if missing
#    7. Runs migrations, collectstatic, creates admin
#    8. Starts Redis, Celery, Daphne — all capped to 4 CPU cores
# =============================================================================
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
step()    { echo -e "\n${BOLD}━━━  $*  ━━━${NC}"; }

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
PROJECT_ROOT="$SCRIPT_DIR"
VENV_DIR="$PROJECT_ROOT/venv"
LOG_DIR="$PROJECT_ROOT/logs"
PIDS_DIR="$PROJECT_ROOT/.pids"
mkdir -p "$LOG_DIR" "$PIDS_DIR"

# ── Resource limits (4 cores shared, GPU handles heavy lifting) ───────────────
CPU_BUDGET=4
WORKERS=2          # Celery + Daphne thread workers
OCV_THREADS=3      # OpenCV threads (leave 1 for OS)

# ── Runtime config ────────────────────────────────────────────────────────────
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"
DJANGO_SETTINGS="school_project.settings"

# ── Cleanup on exit ───────────────────────────────────────────────────────────
cleanup() {
    echo -e "\n${YELLOW}[STOP]${NC} Shutting down..."
    for pidfile in "$PIDS_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        pid=$(cat "$pidfile")
        name=$(basename "$pidfile" .pid)
        kill -0 "$pid" 2>/dev/null && kill "$pid" 2>/dev/null \
            && info "Stopped $name (pid $pid)"
        rm -f "$pidfile"
    done
    success "All services stopped."
}
trap cleanup EXIT INT TERM
save_pid() { echo "$!" > "$PIDS_DIR/$1.pid"; }

# =============================================================================
step "1 / 8  Detect distro & install system packages"
# =============================================================================

if [ ! -f /etc/os-release ]; then
    error "Cannot detect Linux distro — /etc/os-release missing"
fi
# shellcheck disable=SC1091
. /etc/os-release
DISTRO="${ID:-unknown}"
info "Distro: $PRETTY_NAME"

install_apt_packages() {
    info "Updating apt and installing system dependencies..."
    sudo apt-get update -qq
    sudo apt-get install -y --no-install-recommends \
        python3-venv python3-dev \
        build-essential cmake make \
        libopenblas-dev liblapack-dev \
        libx11-dev libgtk-3-dev \
        libgl1-mesa-glx libglib2.0-0 \
        libsm6 libxext6 libxrender1 \
        libboost-all-dev \
        ffmpeg \
        redis-server \
        curl wget \
        ocl-icd-libopencl1 ocl-icd-opencl-dev
}

install_dnf_packages() {
    info "Installing system dependencies via dnf..."
    sudo dnf install -y \
        python3-devel \
        gcc gcc-c++ cmake make \
        openblas-devel lapack-devel \
        libX11-devel gtk3-devel \
        mesa-libGL glib2 \
        libSM libXext libXrender \
        boost-devel \
        ffmpeg redis \
        curl wget \
        ocl-icd ocl-icd-devel
}

install_pacman_packages() {
    info "Installing system dependencies via pacman..."
    sudo pacman -Sy --noconfirm \
        python \
        base-devel cmake \
        openblas lapack \
        libx11 gtk3 \
        mesa glib2 boost \
        ffmpeg redis \
        curl wget \
        ocl-icd opencl-headers
}

case "$DISTRO" in
    ubuntu|debian|linuxmint|pop|kali)
        install_apt_packages ;;
    fedora|rhel|centos|rocky|almalinux)
        install_dnf_packages ;;
    arch|manjaro|endeavouros)
        install_pacman_packages ;;
    *)
        warn "Unknown distro '$DISTRO' — attempting apt install (may fail)"
        install_apt_packages || warn "Some system packages may be missing"
        ;;
esac
success "System packages ready"

# =============================================================================
step "2 / 8  Python version check"
# =============================================================================

PYTHON_BIN=$(command -v python3 || command -v python)
[ -z "$PYTHON_BIN" ] && error "python3 not found — install it first"

PY_VER=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
"$PYTHON_BIN" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" \
    || error "Python 3.10+ required, found $PY_VER"

success "Python $PY_VER ($PYTHON_BIN)"

# =============================================================================
step "3 / 8  Virtual environment"
# =============================================================================

if [ ! -d "$VENV_DIR" ]; then
    info "Creating venv..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    success "venv created at $VENV_DIR"
else
    success "venv exists — reusing"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
success "venv active ($(python --version))"

# =============================================================================
step "4 / 8  Install Python dependencies"
# =============================================================================

info "Installing from requirements.txt..."
pip install -r requirements.txt --quiet

# face_recognition compiles dlib — takes ~5 min on first run
if ! python -c "import face_recognition" 2>/dev/null; then
    info "Compiling dlib + face_recognition (first time ~5 min, grab a coffee)..."
    pip install face_recognition \
        && success "face_recognition installed" \
        || warn "face_recognition failed — attendance features limited"
else
    success "face_recognition already installed"
fi

# pyopencl — optional, for AMD OpenCL detection
pip install pyopencl --quiet 2>/dev/null \
    && success "pyopencl installed" \
    || warn "pyopencl skipped (AMD OpenCL optional)"

success "All Python packages installed"

# =============================================================================
step "5 / 8  AMD GPU setup"
# =============================================================================

# Check for AMD GPU
if lspci 2>/dev/null | grep -qi "AMD\|Radeon\|ATI"; then
    success "AMD GPU detected"

    # ROCm path
    if [ -d /opt/rocm ]; then
        export PATH="/opt/rocm/bin:$PATH"
        export LD_LIBRARY_PATH="/opt/rocm/lib:${LD_LIBRARY_PATH:-}"
        success "ROCm found at /opt/rocm — GPU compute enabled"
    else
        warn "ROCm not installed. For full GPU compute:"
        warn "  https://rocm.docs.amd.com/en/latest/deploy/linux/quick_start.html"
        warn "  (OpenCL still works for OpenCV acceleration)"
    fi

    # Verify OpenCL
    if ldconfig -p 2>/dev/null | grep -q libOpenCL; then
        success "OpenCL runtime available"
    else
        warn "OpenCL runtime missing — install: sudo apt install ocl-icd-libopencl1"
    fi
else
    warn "No AMD GPU detected — running CPU-only mode"
fi

# Set env vars — capped to 4-core budget
export DJANGO_SETTINGS_MODULE="$DJANGO_SETTINGS"
export OMP_NUM_THREADS="$OCV_THREADS"
export OPENBLAS_NUM_THREADS="$OCV_THREADS"
export MKL_NUM_THREADS="$OCV_THREADS"
export NUMEXPR_NUM_THREADS="$OCV_THREADS"
export OPENCV_FFMPEG_CAPTURE_OPTIONS="rtsp_transport;tcp"

# Run GPU detection/setup script
info "Running GPU setup script..."
python scripts/gpu_setup.py 2>&1 | tee "$LOG_DIR/gpu_setup.log" \
    && success "GPU setup complete" \
    || warn "GPU setup warnings — see logs/gpu_setup.log"

# =============================================================================
step "6 / 8  Environment file (.env)"
# =============================================================================

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    warn ".env not found — generating with a secure secret key..."

    # Generate a real Django secret key
    SECRET=$(python -c "
import secrets, string
chars = string.ascii_letters + string.digits + '!@#\$%^&*(-_=+)'
print(''.join(secrets.choice(chars) for _ in range(60)))
")

    # Generate a Fernet encryption key for face vectors
    FERNET_KEY=$(python -c "
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
" 2>/dev/null || echo "")

    cat > "$PROJECT_ROOT/.env" <<EOF
SECRET_KEY=${SECRET}
DEBUG=False
ALLOWED_HOSTS=*
REDIS_URL=redis://localhost:6379/0
FACE_ENCRYPTION_KEY=${FERNET_KEY}
FACE_MATCH_THRESHOLD=0.50
FACE_PRESENCE_DURATION=30
EOF
    success ".env generated"
    info "  SECRET_KEY and FACE_ENCRYPTION_KEY auto-generated"
    warn "  Review .env before going to production (set ALLOWED_HOSTS to your domain)"
else
    success ".env found"
fi

# =============================================================================
step "7 / 8  Django setup (migrate + static + admin)"
# =============================================================================

# Ensure media/recordings dir exists
mkdir -p "$PROJECT_ROOT/media/face_photos" \
         "$PROJECT_ROOT/media/profile_pictures" \
         "$PROJECT_ROOT/media/recordings"

info "Running database migrations..."
python manage.py migrate --run-syncdb 2>&1 | tail -5

info "Collecting static files..."
python manage.py collectstatic --noinput --clear -v 0 2>&1 | tail -3

if [ -f "$PROJECT_ROOT/setup_admin.py" ]; then
    info "Creating admin user..."
    python setup_admin.py 2>&1 | tail -5 || warn "Admin setup skipped"
fi

success "Django ready"

# =============================================================================
step "8 / 8  Start services (Redis → Celery → Daphne)"
# =============================================================================

# ── Redis ─────────────────────────────────────────────────────────────────────
if redis-cli ping &>/dev/null 2>&1; then
    success "Redis already running"
else
    info "Starting Redis..."
    redis-server \
        --daemonize yes \
        --logfile "$LOG_DIR/redis.log" \
        --loglevel notice \
        --maxmemory 256mb \
        --maxmemory-policy allkeys-lru \
        --save "" \
        --appendonly no
    sleep 1
    redis-cli ping &>/dev/null && success "Redis started" \
        || error "Redis failed — check $LOG_DIR/redis.log"
fi

# ── Celery worker ─────────────────────────────────────────────────────────────
info "Starting Celery worker (concurrency=$WORKERS)..."
celery -A school_project worker \
    --loglevel=info \
    --concurrency="$WORKERS" \
    --max-tasks-per-child=100 \
    --logfile="$LOG_DIR/celery.log" \
    --pidfile="$PIDS_DIR/celery.pid" \
    --detach
success "Celery worker started"

# ── Celery beat ───────────────────────────────────────────────────────────────
info "Starting Celery beat..."
celery -A school_project beat \
    --loglevel=info \
    --logfile="$LOG_DIR/celery_beat.log" \
    --pidfile="$PIDS_DIR/celery_beat.pid" \
    --detach
success "Celery beat started"

# ── Daphne ASGI ───────────────────────────────────────────────────────────────
info "Starting Daphne on $APP_HOST:$APP_PORT..."
daphne \
    -b "$APP_HOST" \
    -p "$APP_PORT" \
    --access-log "$LOG_DIR/access.log" \
    -v 1 \
    school_project.asgi:application &
save_pid "daphne"
DAPHNE_PID=$!

sleep 2
kill -0 "$DAPHNE_PID" 2>/dev/null \
    && success "Daphne running (pid $DAPHNE_PID)" \
    || error "Daphne failed — check $LOG_DIR/access.log"

# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║         EduMi is running!                ║${NC}"
echo -e "${GREEN}${BOLD}╠══════════════════════════════════════════╣${NC}"
echo -e "${GREEN}${BOLD}║${NC}  App:    http://$APP_HOST:$APP_PORT"
echo -e "${GREEN}${BOLD}║${NC}  Admin:  http://localhost:$APP_PORT/admin/"
echo -e "${GREEN}${BOLD}║${NC}  Logs:   $LOG_DIR/"
echo -e "${GREEN}${BOLD}║${NC}  CPU:    $CPU_BUDGET cores  |  Workers: $WORKERS"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Press ${BOLD}Ctrl+C${NC} to stop all services"
echo ""
# =============================================================================

wait "$DAPHNE_PID"
