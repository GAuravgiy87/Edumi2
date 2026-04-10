#!/usr/bin/env bash
# =============================================================================
#  EduMi â€” Docker Startup Script
#
#  - Checks if Docker + Docker Compose are installed; installs if missing
#  - Builds the image (multi-stage, optimised)
#  - Runs each service in its own dedicated container
#  - AMD GPU passthrough via /dev/dri (ROCm)
#  - Prints live status and logs
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# =============================================================================
step "1 / 5  Docker installation check"
# =============================================================================

install_docker() {
    info "Docker not found â€” installing Docker Engine..."

    # Detect distro
    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        DISTRO="${ID:-unknown}"
    else
        DISTRO="unknown"
    fi

    case "$DISTRO" in
        ubuntu|debian|linuxmint|pop)
            info "Detected Debian/Ubuntu â€” using apt installer"
            sudo apt-get update -qq
            sudo apt-get install -y --no-install-recommends \
                ca-certificates curl gnupg lsb-release

            # Add Docker's official GPG key
            sudo install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
                | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            sudo chmod a+r /etc/apt/keyrings/docker.gpg

            # Add repo
            echo \
              "deb [arch=$(dpkg --print-architecture) \
              signed-by=/etc/apt/keyrings/docker.gpg] \
              https://download.docker.com/linux/ubuntu \
              $(lsb_release -cs) stable" \
              | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

            sudo apt-get update -qq
            sudo apt-get install -y docker-ce docker-ce-cli \
                containerd.io docker-buildx-plugin docker-compose-plugin
            ;;

        fedora|rhel|centos|rocky|almalinux)
            info "Detected RHEL/Fedora â€” using dnf installer"
            sudo dnf -y install dnf-plugins-core
            sudo dnf config-manager \
                --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
            sudo dnf install -y docker-ce docker-ce-cli \
                containerd.io docker-buildx-plugin docker-compose-plugin
            ;;

        arch|manjaro)
            info "Detected Arch â€” using pacman"
            sudo pacman -Sy --noconfirm docker docker-compose
            ;;

        *)
            warn "Unknown distro '$DISTRO' â€” trying generic install script"
            curl -fsSL https://get.docker.com | sudo sh
            ;;
    esac

    # Start + enable Docker daemon
    sudo systemctl enable --now docker
    # Add current user to docker group (no sudo needed after re-login)
    sudo usermod -aG docker "$USER"
    success "Docker installed"
    warn "You may need to log out and back in for group changes to take effect."
    warn "For this session, commands will run with sudo if needed."
}

# Check Docker
if ! command -v docker &>/dev/null; then
    install_docker
else
    DOCKER_VER=$(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1)
    success "Docker $DOCKER_VER already installed"
fi

# Ensure Docker daemon is running
if ! docker info &>/dev/null; then
    info "Starting Docker daemon..."
    sudo systemctl start docker || error "Could not start Docker daemon"
    sleep 2
fi

# Check Docker Compose (plugin or standalone)
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    success "Docker Compose plugin: $(docker compose version --short)"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
    success "docker-compose standalone: $(docker-compose --version)"
else
    info "Installing Docker Compose plugin..."
    sudo apt-get install -y docker-compose-plugin 2>/dev/null \
        || sudo curl -SL \
            "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
            -o /usr/local/bin/docker-compose \
        && sudo chmod +x /usr/local/bin/docker-compose
    COMPOSE_CMD="docker-compose"
    success "Docker Compose installed"
fi

# =============================================================================
step "2 / 5  AMD GPU passthrough check"
# =============================================================================

GPU_FLAGS=""

if [ -d /dev/dri ]; then
    success "AMD GPU /dev/dri found â€” GPU passthrough enabled"
    # Ensure video group exists in compose
    GPU_FLAGS="--device /dev/dri"
else
    warn "/dev/dri not found â€” running without GPU passthrough"
    warn "For AMD GPU support install ROCm: https://rocm.docs.amd.com/en/latest/deploy/linux/quick_start.html"
    # Patch compose to remove device mapping that would fail
    sed -i '/\/dev\/dri/d; /group_add:/d; /- video/d' docker-compose.yml 2>/dev/null || true
fi

# =============================================================================
step "3 / 5  Environment file"
# =============================================================================

if [ ! -f .env ]; then
    warn ".env not found â€” creating from defaults"
    cat > .env <<'EOF'
SECRET_KEY=django-insecure-change-me-in-production-please
DEBUG=False
ALLOWED_HOSTS=*
REDIS_URL=redis://redis:6379/0
FACE_ENCRYPTION_KEY=
FACE_MATCH_THRESHOLD=0.50
FACE_PRESENCE_DURATION=30
EOF
    warn "Edit .env and set SECRET_KEY + FACE_ENCRYPTION_KEY before going to production!"
else
    success ".env found"
fi

# =============================================================================
step "4 / 5  Build Docker images"
# =============================================================================

info "Building EduMi image (multi-stage â€” first build takes ~10 min for dlib)..."
info "Subsequent builds use layer cache and are fast."

# BuildKit for parallel layer building
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

$COMPOSE_CMD build \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    --parallel \
    2>&1 | grep -E "^(Step|#|=>|ERROR|Successfully)" || true

success "Images built"

# =============================================================================
step "5 / 5  Start all containers"
# =============================================================================

# Pull any images we don't build (redis, nginx)
info "Pulling base images..."
$COMPOSE_CMD pull redis nginx --quiet 2>/dev/null || true

# Stop any old containers cleanly
info "Stopping any existing containers..."
$COMPOSE_CMD down --remove-orphans 2>/dev/null || true

# Run migrations inside a one-off web container before starting
info "Running database migrations..."
$COMPOSE_CMD run --rm \
    -e DJANGO_SETTINGS_MODULE=school_project.settings \
    web \
    python manage.py migrate --run-syncdb 2>&1 | tail -8

# Create admin user
info "Ensuring admin user exists..."
$COMPOSE_CMD run --rm web python setup_admin.py 2>&1 | tail -5 || true

# Start all services â€” each in its own dedicated container
info "Starting all services..."
$COMPOSE_CMD up -d \
    --force-recreate \
    --remove-orphans

# Wait a moment then show status
sleep 4

# =============================================================================
echo ""
echo -e "${GREEN}${BOLD}â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—${NC}"
echo -e "${GREEN}${BOLD}â•‘           EduMi Docker Stack Running             â•‘${NC}"
echo -e "${GREEN}${BOLD}â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£${NC}"
echo -e "${GREEN}${BOLD}â•‘${NC}  App:      http://localhost:80"
echo -e "${GREEN}${BOLD}â•‘${NC}  Admin:    http://localhost:80/admin/"
echo -e "${GREEN}${BOLD}â•‘${NC}  Direct:   http://localhost:8000  (bypass nginx)"
echo -e "${GREEN}${BOLD}â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£${NC}"
echo -e "${GREEN}${BOLD}â•‘${NC}  Containers:"

$COMPOSE_CMD ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null \
    | tail -n +2 \
    | while IFS= read -r line; do
        echo -e "${GREEN}${BOLD}â•‘${NC}    $line"
    done

echo -e "${GREEN}${BOLD}â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•${NC}"
echo ""

# =============================================================================
# Helpful commands
# =============================================================================
echo -e "${BOLD}Useful commands:${NC}"
echo -e "  ${CYAN}$COMPOSE_CMD logs -f web${NC}          â€” Daphne live logs"
echo -e "  ${CYAN}$COMPOSE_CMD logs -f celery${NC}       â€” Celery worker logs"
echo -e "  ${CYAN}$COMPOSE_CMD logs -f nginx${NC}        â€” Nginx logs"
echo -e "  ${CYAN}$COMPOSE_CMD ps${NC}                   â€” Container status"
echo -e "  ${CYAN}$COMPOSE_CMD down${NC}                 â€” Stop everything"
echo -e "  ${CYAN}$COMPOSE_CMD restart web${NC}          â€” Restart only web"
echo -e "  ${CYAN}$COMPOSE_CMD exec web bash${NC}        â€” Shell into web container"
echo ""
echo -e "  ${YELLOW}To stop:  $COMPOSE_CMD down${NC}"
echo ""

# Tail logs (Ctrl+C to detach â€” containers keep running)
echo -e "${BOLD}Tailing logs (Ctrl+C to detach â€” stack keeps running):${NC}\n"
$COMPOSE_CMD logs -f --tail=30 web celery nginx
