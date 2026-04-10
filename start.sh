#!/usr/bin/env bash
# =============================================================================
#  EduMi â€” Linux Startup Script
#  Full performance: venv + deps + GPU setup + Redis + Celery + Daphne
# =============================================================================
set -euo pipefail

# â”€â”€ Colours â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
step()    { echo -e "\n${BOLD}â”â”â”  $*  â”â”â”${NC}"; }

# â”€â”€ Resolve project root (directory this script lives in) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
PROJECT_ROOT="$SCRIPT_DIR"

# â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
VENV_DIR="$PROJECT_ROOT/venv"
PYTHON_MIN="3.10"
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
DJANGO_SETTINGS="school_project.settings"
LOG_DIR="$PROJECT_ROOT/logs"
PIDS_DIR="$PROJECT_ROOT/.pids"

# Physical core count for workers (leave 2 logical cores for OS)
CORES=$(nproc --all 2>/dev/null || echo 4)
WORKERS=$(( CORES > 2 ? CORES - 2 : 2 ))

mkdir -p "$LOG_DIR" "$PIDS_DIR"

# â”€â”€ Trap: clean shutdown on Ctrl+C / exit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
cleanup() {
    echo -e "\n${YELLOW}[STOP]${NC} Shutting down all services..."

    for pidfile in "$PIDS_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        pid=$(cat "$pidfile")
        name=$(basename "$pidfile" .pid)
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && info "Stopped $name (pid $pid)"
        fi
        rm -f "$pidfile"
    done

    success "All services stopped."
}
trap cleanup EXIT INT TERM

save_pid() { echo "$!" > "$PIDS_DIR/$1.pid"; }

# =============================================================================
step "1 / 7  System dependencies"
# =============================================================================

check_cmd() {
    command -v "$1" &>/dev/null || error "'$1' not found. Install it first:\n  $2"
}

check_cmd python3   "sudo apt install python3 python3-venv python3-dev"
check_cmd pip3      "sudo apt install python3-pip"
check_cmd redis-cli "sudo apt install redis-server"
check_cmd ffmpeg    "sudo apt install ffmpeg"

# Python version check
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python $PY_VER detected"
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" \
    || error "Python >= $PYTHON_MIN required (found $PY_VER)"

# OpenCL / AMD GPU runtime (optional â€” warn, don't fail)
if ! ldconfig -p 2>/dev/null | grep -q libOpenCL; then
    warn "OpenCL runtime not found. For AMD GPU acceleration install:"
    warn "  sudo apt install ocl-icd-opencl-dev rocm-opencl-runtime"
    warn "  (continuing without GPU acceleration)"
fi

# =============================================================================
step "2 / 7  Virtual environment"
# =============================================================================

if [ ! -d "$VENV_DIR" ]; then
    info "Creating venv at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
    success "venv created"
else
    info "venv already exists â€” reusing"
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
success "venv activated ($(python --version))"

# Upgrade pip silently
pip install --upgrade pip --quiet

# =============================================================================
step "3 / 7  Install requirements"
# =============================================================================

# Build deps needed for dlib / face_recognition on Linux
if ! python -c "import dlib" 2>/dev/null; then
    info "Installing build dependencies for dlib..."
    sudo apt-get install -y --no-install-recommends \
        cmake build-essential libopenblas-dev liblapack-dev \
        libx11-dev libgtk-3-dev 2>/dev/null \
        || warn "Could not install build deps (may need sudo). dlib may fail."
fi

info "Installing Python packages from requirements.txt ..."
pip install -r requirements.txt --quiet

# face_recognition (needs dlib â€” may take a few minutes first time)
if ! python -c "import face_recognition" 2>/dev/null; then
    info "Installing face_recognition (compiling dlib â€” this takes ~5 min first time)..."
    pip install face_recognition --quiet \
        && success "face_recognition installed" \
        || warn "face_recognition install failed â€” attendance features will be limited"
fi

# GPU extras
info "Installing GPU/performance extras..."
pip install psutil --quiet

# pyopencl for AMD OpenCL detection (optional)
pip install pyopencl --quiet 2>/dev/null \
    && success "pyopencl installed (AMD OpenCL support)" \
    || warn "pyopencl not installed â€” OpenCL detection will use fallback"

# python-dotenv (needed by settings.py)
pip install python-dotenv --quiet

success "All packages installed"

# =============================================================================
step "4 / 7  GPU & CPU optimisation"
# =============================================================================

export DJANGO_SETTINGS_MODULE="$DJANGO_SETTINGS"

# Set OpenCV to use all cores
export OMP_NUM_THREADS="$CORES"
export OPENBLAS_NUM_THREADS="$CORES"
export MKL_NUM_THREADS="$CORES"
export NUMEXPR_NUM_THREADS="$CORES"

# Force RTSP over TCP (prevents packet loss on cameras)
export OPENCV_FFMPEG_CAPTURE_OPTIONS="rtsp_transport;tcp"

# AMD ROCm / HIP (if installed)
if [ -d /opt/rocm ]; then
    export PATH="/opt/rocm/bin:$PATH"
    export LD_LIBRARY_PATH="/opt/rocm/lib:${LD_LIBRARY_PATH:-}"
    info "ROCm found at /opt/rocm â€” AMD GPU compute enabled"
fi

# Run GPU setup script (non-fatal)
info "Running GPU setup..."
python scripts/gpu_setup.py 2>&1 | tee "$LOG_DIR/gpu_setup.log" \
    && success "GPU setup complete" \
    || warn "GPU setup had warnings (check logs/gpu_setup.log)"

# =============================================================================
step "5 / 7  Redis"
# =============================================================================

if redis-cli ping &>/dev/null; then
    success "Redis already running"
else
    info "Starting Redis server..."
    redis-server --daemonize yes \
                 --logfile "$LOG_DIR/redis.log" \
                 --loglevel notice \
                 --maxmemory 256mb \
                 --maxmemory-policy allkeys-lru
    sleep 1
    redis-cli ping &>/dev/null && success "Redis started" || error "Redis failed to start"
fi

# =============================================================================
step "6 / 7  Django: migrate + static files"
# =============================================================================

info "Running migrations..."
python manage.py migrate --run-syncdb 2>&1 | tail -5

info "Collecting static files..."
python manage.py collectstatic --noinput --clear -v 0 2>&1 | tail -3

# Create admin user if it doesn't exist
if [ -f "setup_admin.py" ]; then
    info "Ensuring admin user exists..."
    python setup_admin.py 2>&1 | tail -5 || warn "Admin setup skipped"
fi

success "Django ready"

# =============================================================================
step "7 / 7  Starting services"
# =============================================================================

# â”€â”€ Celery worker â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "Starting Celery worker ($WORKERS concurrency)..."
celery -A school_project worker \
    --loglevel=info \
    --concurrency="$WORKERS" \
    --max-tasks-per-child=100 \
    --logfile="$LOG_DIR/celery.log" \
    --pidfile="$PIDS_DIR/celery.pid" \
    --detach
success "Celery worker started (log: logs/celery.log)"

# â”€â”€ Celery beat (scheduled tasks) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "Starting Celery beat..."
celery -A school_project beat \
    --loglevel=info \
    --logfile="$LOG_DIR/celery_beat.log" \
    --pidfile="$PIDS_DIR/celery_beat.pid" \
    --detach
success "Celery beat started (log: logs/celery_beat.log)"

# â”€â”€ Daphne ASGI server â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
info "Starting Daphne on $APP_HOST:$APP_PORT ..."
info "  Workers: $WORKERS threads | Cores: $CORES"

daphne \
    -b "$APP_HOST" \
    -p "$APP_PORT" \
    --access-log "$LOG_DIR/access.log" \
    -v 1 \
    school_project.asgi:application \
    &
save_pid "daphne"
DAPHNE_PID=$!

sleep 2
if kill -0 "$DAPHNE_PID" 2>/dev/null; then
    success "Daphne running (pid $DAPHNE_PID)"
else
    error "Daphne failed to start â€” check logs/access.log"
fi

# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—${NC}"
echo -e "${GREEN}${BOLD}â•‘        EduMi is running!                 â•‘${NC}"
echo -e "${GREEN}${BOLD}â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£${NC}"
echo -e "${GREEN}${BOLD}â•‘${NC}  App:    http://$APP_HOST:$APP_PORT"
echo -e "${GREEN}${BOLD}â•‘${NC}  Admin:  http://localhost:$APP_PORT/admin/"
echo -e "${GREEN}${BOLD}â•‘${NC}  Logs:   $LOG_DIR/"
echo -e "${GREEN}${BOLD}â•‘${NC}  Cores:  $CORES  |  Workers: $WORKERS"
echo -e "${GREEN}${BOLD}â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•${NC}"
echo ""
echo -e "  Press ${BOLD}Ctrl+C${NC} to stop all services"
echo ""
# =============================================================================

# Keep script alive â€” tail Daphne logs to terminal
wait "$DAPHNE_PID"
