#!/usr/bin/env bash
# ==============================================================================
#  EduMi2 — Native Ubuntu System & Prerequisites Inspector (Without Docker)
#  Tested on: Ubuntu 20.04/22.04/24.04 LTS, Debian 11/12
# ==============================================================================
#  USAGE:
#    chmod +x scripts/check_ubuntu_env.sh
#    ./scripts/check_ubuntu_env.sh
# ==============================================================================

set -uo pipefail

# ANSI Color Utilities
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

pass() { echo -e "  ${GREEN}[✓ PASS]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[! WARN]${NC} $1"; ((WARNINGS++)); }
fail() { echo -e "  ${RED}[✗ FAIL]${NC} $1"; ((ERRORS++)); }
info() { echo -e "  ${BLUE}[i INFO]${NC} $1"; }
header() {
    echo ""
    echo -e "${BOLD}${CYAN}--------------------------------------------------${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}--------------------------------------------------${NC}"
}

echo ""
echo -e "${BOLD}${GREEN}"
echo "   ███████╗██████╗ ██╗   ██╗███╗   ███╗██╗    ██████╗ "
echo "   ██╔════╝██╔══██╗██║   ██║████╗ ████║██║    ╚════██╗"
echo "   █████╗  ██║  ██║██║   ██║██╔████╔██║██║     █████╔╝"
echo "   ██╔══╝  ██║  ██║██║   ██║██║╚██╔╝██║██║    ██╔═══╝ "
echo "   ███████╗██████╔╝╚██████╔╝██║ ╚═╝ ██║██║    ███████╗"
echo "   ╚══════╝╚═════╝  ╚═════╝ ╚═╝     ╚═╝╚═╝    ╚══════╝"
echo -e "${NC}"
echo -e "  ${BOLD}EduMi2 Native Ubuntu Infrastructure Inspector${NC}"
echo -e "  Date: $(date)"
echo ""

# ------------------------------------------------------------------------------
header "1. Operating System & Linux Distribution"
# ------------------------------------------------------------------------------

if [ -f /etc/os-release ]; then
    . /etc/os-release
    info "OS Distribution: $NAME $VERSION"
    if [[ "$ID" == "ubuntu" || "$ID_LIKE" == *"ubuntu"* || "$ID" == "debian" ]]; then
        pass "Supported Linux Distribution ($NAME)"
    else
        warn "Untested distribution ($NAME). Ubuntu 22.04/24.04 LTS is recommended."
    fi
else
    warn "Could not read /etc/os-release"
fi

if command -v systemctl &>/dev/null && [ -d /run/systemd/system ]; then
    pass "Systemd init manager is active and running"
else
    fail "Systemd is not running as init system (Required for native service management)"
fi


# ------------------------------------------------------------------------------
header "2. System Hardware & Memory Resources"
# ------------------------------------------------------------------------------

TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 0)
TOTAL_RAM_GB=$(awk "BEGIN {print $TOTAL_RAM_KB / 1024 / 1024}")
TOTAL_RAM_GB_INT=${TOTAL_RAM_GB%.*}

if [ "$TOTAL_RAM_GB_INT" -ge 4 ]; then
    pass "RAM Capacity: ${TOTAL_RAM_GB:0:4} GB (Sufficient)"
elif [ "$TOTAL_RAM_GB_INT" -ge 2 ]; then
    warn "RAM Capacity: ${TOTAL_RAM_GB:0:4} GB (Minimum requirement is 4GB for video processing)"
else
    fail "RAM Capacity: ${TOTAL_RAM_GB:0:4} GB (Insufficient RAM. At least 4GB RAM is required)"
fi

CPU_CORES=$(nproc 2>/dev/null || echo 1)
if [ "$CPU_CORES" -ge 2 ]; then
    pass "CPU Cores: $CPU_CORES cores"
else
    warn "CPU Cores: $CPU_CORES core (Multi-core system recommended for Daphne & Celery)"
fi

FREE_DISK_GB=$(df -BG . 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G' || echo 0)
if [ "$FREE_DISK_GB" -ge 10 ]; then
    pass "Available Storage: ${FREE_DISK_GB} GB free"
elif [ "$FREE_DISK_GB" -ge 5 ]; then
    warn "Available Storage: ${FREE_DISK_GB} GB free (Recommended >= 10GB for video media storage)"
else
    fail "Available Storage: ${FREE_DISK_GB} GB free (Insufficient disk space)"
fi


# ------------------------------------------------------------------------------
header "3. Python & Build Toolchain"
# ------------------------------------------------------------------------------

PYTHON_BIN=""
if command -v python3.11 &>/dev/null; then
    PYTHON_BIN="python3.11"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
fi

if [ -n "$PYTHON_BIN" ]; then
    PY_VER=$($PYTHON_BIN --version 2>&1)
    pass "Python runtime found: $PY_VER ($PYTHON_BIN)"
    
    # Check venv support
    if $PYTHON_BIN -m venv --help &>/dev/null; then
        pass "Python venv module available"
    else
        fail "Python venv module missing (Install: sudo apt install ${PYTHON_BIN}-venv)"
    fi
else
    fail "Python 3 is not installed (Required: Python 3.10 or 3.11)"
fi

# Build Essentials & C++ Compiler
for pkg in gcc g++ make cmake; do
    if command -v $pkg &>/dev/null; then
        pass "Build tool '$pkg' found: $(command -v $pkg)"
    else
        fail "Build tool '$pkg' is missing (Install: sudo apt install build-essential cmake)"
    fi
done


# ------------------------------------------------------------------------------
header "4. Multimedia & OpenCV System Dependencies"
# ------------------------------------------------------------------------------

if command -v ffmpeg &>/dev/null; then
    FFMPEG_VER=$(ffmpeg -version 2>&1 | head -n 1)
    pass "FFmpeg binary found: $FFMPEG_VER"
else
    fail "FFmpeg binary is missing (Install: sudo apt install ffmpeg)"
fi

if command -v ffprobe &>/dev/null; then
    pass "FFprobe binary found"
else
    fail "FFprobe binary is missing (Install: sudo apt install ffmpeg)"
fi

# Shared libraries required for OpenCV & Pillow
MISSING_LIBS=()
for lib in libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libpq-dev libffi-dev; do
    if dpkg -l | grep -q "$lib" 2>/dev/null || ldconfig -p 2>/dev/null | grep -q "$lib"; then
        pass "System library '$lib' found"
    else
        MISSING_LIBS+=("$lib")
    fi
done

if [ ${#MISSING_LIBS[@]} -gt 0 ]; then
    warn "Some shared libraries may be missing: ${MISSING_LIBS[*]}"
fi


# ------------------------------------------------------------------------------
header "5. System Database & Server Daemons"
# ------------------------------------------------------------------------------

# PostgreSQL
if command -v psql &>/dev/null; then
    PSQL_VER=$(psql --version 2>&1)
    pass "PostgreSQL client found: $PSQL_VER"
    if systemctl is-active --quiet postgresql 2>/dev/null; then
        pass "PostgreSQL service is running"
    else
        warn "PostgreSQL service installed but not active (Start: sudo systemctl start postgresql)"
    fi
else
    fail "PostgreSQL is not installed (Install: sudo apt install postgresql postgresql-contrib libpq-dev)"
fi

# Redis
if command -v redis-cli &>/dev/null; then
    pass "Redis CLI found"
    if redis-cli ping 2>/dev/null | grep -q "PONG"; then
        pass "Redis service is active and responding to PING"
    elif systemctl is-active --quiet redis-server 2>/dev/null || systemctl is-active --quiet redis 2>/dev/null; then
        pass "Redis service is active"
    else
        warn "Redis service installed but not active (Start: sudo systemctl start redis-server)"
    fi
else
    fail "Redis is not installed (Install: sudo apt install redis-server)"
fi

# Nginx
if command -v nginx &>/dev/null; then
    NGINX_VER=$(nginx -v 2>&1)
    pass "Nginx Web Server found: $NGINX_VER"
else
    fail "Nginx Web Server is not installed (Install: sudo apt install nginx)"
fi


# ------------------------------------------------------------------------------
header "6. Network Port Availability Check"
# ------------------------------------------------------------------------------

REQUIRED_PORTS=(80 443 8002 8003 8004 8005 8006 8007 8008 6379 5432 7880 7881)

check_port() {
    local port=$1
    if command -v ss &>/dev/null; then
        ss -tuln | grep -q ":${port} " && return 1 || return 0
    elif command -v netstat &>/dev/null; then
        netstat -tuln | grep -q ":${port} " && return 1 || return 0
    else
        (exec 6<>/dev/tcp/127.0.0.1/$port) 2>/dev/null && exec 6>&- && return 1 || return 0
    fi
}

for port in "${REQUIRED_PORTS[@]}"; do
    if check_port "$port"; then
        pass "Port $port is available"
    else
        info "Port $port is currently in use (Will be bound by native service)"
    fi
done


# ------------------------------------------------------------------------------
header "7. Summary & Next Steps"
# ------------------------------------------------------------------------------

echo ""
if [ "$ERRORS" -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✓ System environment check passed! ($WARNINGS warnings)${NC}"
    echo -e "  Your Ubuntu server is ready for native EduMi2 deployment."
    echo -e "  Run ${CYAN}sudo bash deploy_ubuntu_native.sh${NC} to start deployment."
    exit 0
else
    echo -e "${RED}${BOLD}✗ Infrastructure check failed with $ERRORS error(s) and $WARNINGS warning(s).${NC}"
    echo ""
    echo -e "${BOLD}Automated Package Installation Command:${NC}"
    echo -e "  Run the command below on your Ubuntu server to install all missing dependencies:"
    echo ""
    echo -e "  ${CYAN}sudo apt-get update && sudo apt-get install -y \\${NC}"
    echo -e "    ${CYAN}python3.11 python3.11-venv python3.11-dev python3-pip \\${NC}"
    echo -e "    ${CYAN}build-essential cmake g++ libpq-dev libffi-dev \\${NC}"
    echo -e "    ${CYAN}ffmpeg postgresql postgresql-contrib redis-server nginx \\${NC}"
    echo -e "    ${CYAN}libopenblas-dev liblapack-dev libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev curl wget git${NC}"
    echo ""
    exit 1
fi
