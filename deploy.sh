#!/bin/bash
# ============================================================
#  EduMi2 — Smart Deploy Script
#  Checks ports, kills blockers, then starts Docker Compose.
#  Works on Linux and WSL2.
#
#  Usage:  bash deploy.sh
#  Custom port: bash deploy.sh --port 8080
# ============================================================

set -e

ENV_FILE=".env.docker"
COMPOSE_CMD="docker compose --env-file $ENV_FILE"
HTTP_PORT=80   # default, can be overridden with --port

# Parse --port argument
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --port) HTTP_PORT="$2"; shift ;;
    esac
    shift
done

REQUIRED_PORTS=($HTTP_PORT 7880 7881)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}   EduMi2 — Pre-flight Deploy Check${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# ── Step 1: Check .env.docker ────────────────────────────────
echo -e "${YELLOW}[1/5] Checking $ENV_FILE...${NC}"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}ERROR: $ENV_FILE not found.${NC}"
    exit 1
fi
echo -e "${GREEN}  OK${NC}"

# ── Step 2: Stop existing EduMi2 containers ──────────────────
echo ""
echo -e "${YELLOW}[2/5] Stopping existing EduMi2 containers...${NC}"
$COMPOSE_CMD down --remove-orphans 2>/dev/null || true
echo -e "${GREEN}  OK${NC}"

# ── Step 3: Update nginx port if not 80 ──────────────────────
if [ "$HTTP_PORT" != "80" ]; then
    echo ""
    echo -e "${YELLOW}[3/5] Setting nginx to port $HTTP_PORT...${NC}"
    # Update docker-compose.yml nginx port mapping
    sed -i "s|\"[0-9]*:80\"|\"$HTTP_PORT:80\"|g" docker-compose.yml
    echo -e "${GREEN}  OK — nginx will listen on port $HTTP_PORT${NC}"
else
    echo ""
    echo -e "${YELLOW}[3/5] Using default port 80...${NC}"
    echo -e "${GREEN}  OK${NC}"
fi

# ── Step 4: Free required ports ──────────────────────────────
echo ""
echo -e "${YELLOW}[4/5] Checking ports: ${REQUIRED_PORTS[*]}...${NC}"

for PORT in "${REQUIRED_PORTS[@]}"; do
    echo -n "  Port $PORT — "

    # Check with ss (Linux/WSL)
    PIDS=$(ss -tlnp 2>/dev/null | grep ":${PORT} " | grep -oP 'pid=\K[0-9]+' | sort -u || true)

    # Also check with lsof as fallback
    if [ -z "$PIDS" ]; then
        PIDS=$(lsof -ti ":$PORT" 2>/dev/null || true)
    fi

    if [ -z "$PIDS" ]; then
        echo -e "${GREEN}free${NC}"
        continue
    fi

    echo -e "${YELLOW}in use (PID: $PIDS) — killing...${NC}"

    # Kill Linux/WSL processes
    for PID in $PIDS; do
        PROC=$(ps -p "$PID" -o comm= 2>/dev/null || echo "unknown")
        echo -e "    Killing PID $PID ($PROC)"
        sudo kill -9 "$PID" 2>/dev/null || true
    done

    # Stop common system services that grab port 80
    if [ "$PORT" = "80" ] || [ "$PORT" = "$HTTP_PORT" ]; then
        for SVC in apache2 nginx lighttpd; do
            if systemctl is-active --quiet "$SVC" 2>/dev/null; then
                echo -e "    Stopping $SVC service..."
                sudo systemctl stop "$SVC" 2>/dev/null || true
                sudo systemctl disable "$SVC" 2>/dev/null || true
            fi
        done
        # WSL2: Windows-side services hold ports — Docker Desktop handles this
        # but sometimes needs a nudge
        if grep -qi microsoft /proc/version 2>/dev/null; then
            echo -e "    ${CYAN}WSL2 detected — if port is still blocked, a Windows service"
            echo -e "    (IIS, World Wide Web Publishing) may be holding it.${NC}"
            echo -e "    ${CYAN}Run in Windows PowerShell as Admin:${NC}"
            echo -e "    ${CYAN}  net stop W3SVC${NC}"
            echo -e "    ${CYAN}  net stop WAS${NC}"
        fi
    fi

    sleep 1

    # Verify
    STILL=$(ss -tlnp 2>/dev/null | grep -c ":${PORT} " || true)
    if [ "$STILL" -gt 0 ]; then
        echo ""
        echo -e "${RED}  Port $PORT still blocked after kill attempt.${NC}"
        echo ""
        echo -e "${YELLOW}  Options:${NC}"
        echo -e "  1. Run on a different port:  ${CYAN}bash deploy.sh --port 8080${NC}"
        echo -e "  2. Kill Windows service (run in PowerShell as Admin):"
        echo -e "     ${CYAN}net stop W3SVC ; net stop WAS ; net stop http${NC}"
        echo -e "  3. Then re-run:  ${CYAN}bash deploy.sh${NC}"
        echo ""
        echo -e "${YELLOW}  Trying port 8080 automatically...${NC}"
        HTTP_PORT=8080
        REQUIRED_PORTS=($HTTP_PORT 7880 7881)
        sed -i "s|\"[0-9]*:80\"|\"$HTTP_PORT:80\"|g" docker-compose.yml
        echo -e "${GREEN}  Switched nginx to port $HTTP_PORT${NC}"
        break
    fi
    echo -e "${GREEN}  Port $PORT — now free${NC}"
done

# ── Step 5: Build and start ───────────────────────────────────
echo ""
echo -e "${YELLOW}[5/5] Building and starting all containers...${NC}"
echo ""

DOCKER_BUILDKIT=1 $COMPOSE_CMD up -d --build

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${GREEN}  All containers started!${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

$COMPOSE_CMD ps

echo ""
SERVER_IP=$(grep '^SERVER_IP=' "$ENV_FILE" | cut -d'=' -f2 | tr -d ' \r')
echo -e "${CYAN}Access the app:${NC}"
echo -e "  Local:   ${GREEN}http://localhost:${HTTP_PORT}${NC}"
echo -e "  Network: ${GREEN}http://${SERVER_IP}:${HTTP_PORT}${NC}"
echo -e "  Admin:   ${GREEN}http://localhost:${HTTP_PORT}/admin/${NC}"
echo ""
echo -e "${YELLOW}First time? Create admin:${NC}"
echo -e "  ${CYAN}docker compose --env-file .env.docker exec web python manage.py createsuperuser${NC}"
echo ""
