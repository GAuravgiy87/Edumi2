#!/bin/bash
# ==============================================================================
#  EduMi 2 — Zero-Downtime Update Script
#  Run after pushing new code to auto-deploy latest changes
#
#  USAGE (on the server):
#    sudo bash /opt/edumi/scripts/update.sh
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${CYAN}[i]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

APP_DIR="/opt/edumi"
APP_USER="edumi"
BRANCH="${1:-new_edumi}"

[[ "$EUID" -ne 0 ]] && err "Run as root: sudo bash scripts/update.sh"

echo -e "\n${BOLD}${CYAN}EduMi 2 — Updating to latest code (branch: $BRANCH)${NC}\n"

# 1. Pull latest code
info "Pulling latest code..."
cd "$APP_DIR"
sudo -u "$APP_USER" git fetch origin
sudo -u "$APP_USER" git checkout "$BRANCH"
sudo -u "$APP_USER" git pull origin "$BRANCH"
log "Code updated"

# 2. Install any new dependencies
info "Updating Python dependencies..."
sudo -u "$APP_USER" venv/bin/pip install -r requirements.txt -q
log "Dependencies updated"

# 3. Apply DB migrations
info "Running database migrations..."
sudo -u "$APP_USER" venv/bin/python manage.py migrate --noinput
log "Migrations applied"

# 4. Collect static files
info "Collecting static files..."
sudo -u "$APP_USER" venv/bin/python manage.py collectstatic --noinput -v 0
log "Static files collected"

# 5. Restart services gracefully
info "Restarting services..."
systemctl restart edumi-web edumi-celery edumi-camera
sleep 3

# 6. Verify
for svc in edumi-web edumi-celery edumi-camera; do
    STATUS=$(systemctl is-active "$svc" 2>/dev/null || echo "inactive")
    if [[ "$STATUS" == "active" ]]; then
        log "$svc is running"
    else
        warn "$svc failed to start — check: journalctl -u $svc -n 30"
    fi
done

echo -e "\n${BOLD}${GREEN}✅ Update complete!${NC}"
echo -e "  Watch logs : ${CYAN}journalctl -u edumi-web -f${NC}"
