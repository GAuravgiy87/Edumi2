#!/usr/bin/env bash
# =====================================================
# EduMi 2 - FULL SYSTEM STARTUP SCRIPT (Linux/WSL)
# One file does everything:
#   - SSL cert generation + LAN-aware cert
#   - Cert trust (this machine)
#   - Redis, LiveKit, Celery, Camera Service
#   - DB migrations, static files
#   - Django HTTPS (Daphne)
# =====================================================
# Usage:  chmod +x start_app.sh && ./start_app.sh
# =====================================================

set -uo pipefail  # treat unset vars as errors, propagate pipe errors

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v livekit-server &>/dev/null; then
    LIVEKIT="livekit-server"
elif [ -f "$BASE_DIR/livekit-bin/livekit-server" ]; then
    LIVEKIT="$BASE_DIR/livekit-bin/livekit-server"
else
    LIVEKIT=""
fi

LIVEKIT_CONFIG="$BASE_DIR/config/livekit.yaml"
SSL_CERT="$BASE_DIR/certs/edumi.crt"
SSL_KEY="$BASE_DIR/certs/edumi.key"
SSL_EXPORT="$BASE_DIR/certs/edumi-trust-this.crt"
DOMAIN="edumi.ac.in"

if [ -f "$BASE_DIR/venv/bin/python" ]; then
    PYTHON="$BASE_DIR/venv/bin/python"
elif [ -f "$BASE_DIR/venv_linux/bin/python" ]; then
    PYTHON="$BASE_DIR/venv_linux/bin/python"
elif [ -f "$BASE_DIR/.venv/bin/python" ]; then
    PYTHON="$BASE_DIR/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo "[ERROR] Python not found!"
    exit 1
fi

cd "$BASE_DIR"

# ── Check root ─────────────────────────────────────────────────────────────────
IS_ROOT=false
if [ "$(id -u)" -eq 0 ]; then IS_ROOT=true; fi

echo ""
echo "======================================================"
echo "        EduMi 2: Academic Command Center"
if [ "$IS_ROOT" = false ]; then
    echo "  (tip: run as root/sudo for hosts + cert trust)"
fi
echo "======================================================"
echo ""

# ── Detect LAN IP ─────────────────────────────────────────────────────────────
LAN_IP=$(ip route get 8.8.8.8 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1); exit}')
if [ -z "$LAN_IP" ]; then
    LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi
if [ -z "$LAN_IP" ]; then
    LAN_IP="127.0.0.1"
fi
echo "      Detected LAN IP: $LAN_IP"


# =======================================================
# STEP 0: FIREWALL RULES (iptables / ufw)
# =======================================================
echo "[0/9] Applying firewall rules..."

if [ "$IS_ROOT" = true ]; then
    if command -v ufw &>/dev/null; then
        ufw allow 8002/tcp  || true
        ufw allow 8003/tcp  || true
        ufw allow 7880/tcp  || true
        ufw allow 7881/tcp  || true
        ufw allow 7882/udp  || true
        ufw allow 50000:50200/udp || true
        echo "      [OK] ufw rules applied"
    else
        echo "      [SKIP] ufw not found — configure firewall manually if needed"
    fi
else
    echo "      [SKIP] Need root to set firewall rules"
    echo "             Re-run with sudo for full setup"
fi


# =======================================================
# STEP 1: HOSTS FILE
# =======================================================
echo "[1/9] Checking hosts file for $DOMAIN ..."

HOSTS_FILE="/etc/hosts"
if grep -q "edumi\.ac\.in" "$HOSTS_FILE" 2>/dev/null; then
    echo "      $DOMAIN already in hosts file - SKIP"
elif [ "$IS_ROOT" = true ]; then
    echo "" >> "$HOSTS_FILE"
    echo "# EduMi 2 - Local SSL Domain" >> "$HOSTS_FILE"
    echo "127.0.0.1    $DOMAIN    www.$DOMAIN" >> "$HOSTS_FILE"
    echo "      [OK] Added: 127.0.0.1    $DOMAIN    www.$DOMAIN"
else
    echo "      [SKIP] Need root to edit /etc/hosts"
    echo "             Run: sudo sh -c 'echo \"127.0.0.1 $DOMAIN www.$DOMAIN\" >> /etc/hosts'"
fi


# =======================================================
# STEP 2: CLEAN OLD PROCESSES
# =======================================================
echo "[2/9] Cleaning old processes..."

pkill -f "python.*manage.py"  || true
pkill -f "celery"             || true
pkill -f "daphne"             || true
pkill -f "livekit-server"     || true
pkill -f "camera_service"     || true

# Free ports 8002 and 8003
for port in 8002 8003; do
    pid=$(lsof -ti tcp:"$port" 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill -9 $pid 2>/dev/null || true
        echo "      Killed process on port $port (PID $pid)"
    fi
done

sleep 2
echo "      [OK] Ports cleared"


# =======================================================
# STEP 3: SSL CERTIFICATE
# =======================================================
echo "[3/9] Generating SSL certificate (LAN-aware)..."

mkdir -p "$BASE_DIR/certs"

"$PYTHON" - <<PYEOF
import datetime, ipaddress, socket, sys, shutil
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from pathlib import Path

DOMAIN   = 'edumi.ac.in'
CERT_DIR = Path('$BASE_DIR/certs')
CERT_DIR.mkdir(parents=True, exist_ok=True)

lan_ips = ['127.0.0.1', '$LAN_IP']
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80)); detected = s.getsockname()[0]; s.close()
    if detected not in lan_ips: lan_ips.append(detected)
except: pass

hostname = socket.gethostname()

# ── Root CA ───────────────────────────────────────────────────────────
CA_KEY_FILE = CERT_DIR / 'edumi-root-ca.key'
CA_CERT_FILE = CERT_DIR / 'edumi-root-ca.crt'
TRUST_FILE = CERT_DIR / 'edumi-trust-this.crt'

if CA_KEY_FILE.exists() and CA_CERT_FILE.exists():
    ca_key = serialization.load_pem_private_key(CA_KEY_FILE.read_bytes(), password=None, backend=default_backend())
    ca_cert = x509.load_pem_x509_certificate(CA_CERT_FILE.read_bytes(), default_backend())
    ca_subj = ca_cert.subject
    print('[OK] Using existing Local Root CA')
else:
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    ca_subj = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'IN'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'EduMi Academic Local CA'),
        x509.NameAttribute(NameOID.COMMON_NAME, 'EduMi Local Root CA'),
    ])
    now = datetime.datetime.utcnow()
    ca_cert = (x509.CertificateBuilder()
        .subject_name(ca_subj).issuer_name(ca_subj)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False
        ), critical=True)
        .sign(ca_key, hashes.SHA256(), default_backend()))
    
    CA_KEY_FILE.write_bytes(ca_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))
    CA_CERT_FILE.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    TRUST_FILE.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    print('[OK] Generated new Local Root CA')

# ── Leaf Server Key & Certificate ─────────────────────────────────────
key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

san = [
    x509.DNSName(DOMAIN), x509.DNSName(f'www.{DOMAIN}'),
    x509.DNSName('localhost'), x509.DNSName(hostname),
    x509.DNSName('localdns'),
]
for ip in lan_ips:
    try: san.append(x509.IPAddress(ipaddress.IPv4Address(ip)))
    except: pass
san.append(x509.IPAddress(ipaddress.IPv6Address('::1')))

subj = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'IN'),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'EduMi Academic'),
    x509.NameAttribute(NameOID.COMMON_NAME, DOMAIN),
])

now = datetime.datetime.utcnow()
cert = (x509.CertificateBuilder()
    .subject_name(subj).issuer_name(ca_subj)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now - datetime.timedelta(days=1))
    .not_valid_after(now + datetime.timedelta(days=3650))
    .add_extension(x509.SubjectAlternativeName(san), critical=False)
    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    .add_extension(x509.KeyUsage(
        digital_signature=True, content_commitment=False, key_encipherment=True,
        data_encipherment=False, key_agreement=False, key_cert_sign=False,
        crl_sign=False, encipher_only=False, decipher_only=False
    ), critical=True)
    .add_extension(x509.ExtendedKeyUsage([
        x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
        x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH
    ]), critical=False)
    .sign(ca_key, hashes.SHA256(), default_backend()))

(CERT_DIR / 'edumi.key').write_bytes(key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
    serialization.NoEncryption()))
(CERT_DIR / 'edumi.crt').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
print('[OK] cert covers:', [str(s) for s in san])
PYEOF

if [ ! -f "$SSL_CERT" ]; then
    echo "      [FAIL] Certificate generation failed!"
    exit 1
fi
echo "      [OK] Certificate generated (covers LAN IP: $LAN_IP)"


# =======================================================
# STEP 4: TRUST CERT
# =======================================================
echo "[4/9] Installing certificate into trusted CA store..."

# ── Linux system trust (for curl/wget/Python inside WSL) ──────────────────────
if [ "$IS_ROOT" = true ]; then
    if command -v update-ca-certificates &>/dev/null; then
        cp "$SSL_EXPORT" /usr/local/share/ca-certificates/edumi.crt
        update-ca-certificates 2>/dev/null || true
        echo "      [OK] Certificate trusted in Linux system store"
    elif command -v update-ca-trust &>/dev/null; then
        cp "$SSL_EXPORT" /etc/pki/ca-trust/source/anchors/edumi.crt
        update-ca-trust extract 2>/dev/null || true
        echo "      [OK] Certificate trusted (RHEL/Fedora)"
    fi
else
    echo "      [INFO] Skipping Linux system store (not root) — browser trust handled below"
fi

# ── Windows trust via PowerShell (browser runs on Windows, not Linux) ─────────
# WSL can call powershell.exe directly to install into Windows cert store
WIN_PS_SCRIPT=$(wslpath -w "$BASE_DIR/trust_cert.ps1" 2>/dev/null || echo "")
WIN_CERT=$(wslpath -w "$SSL_EXPORT" 2>/dev/null || echo "")

if command -v powershell.exe &>/dev/null && [ -n "$WIN_PS_SCRIPT" ]; then
    echo "      Running trust_cert.ps1 via Windows PowerShell..."
    powershell.exe -NoProfile -ExecutionPolicy Bypass \
        -File "$WIN_PS_SCRIPT" -CertPath "$WIN_CERT" 2>/dev/null
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo "      [OK] Certificate trusted in Windows — close ALL Chrome windows and reopen!"
    else
        echo "      [WARN] PowerShell returned code $EXIT_CODE"
        echo "             Try running trust_cert.ps1 manually as Administrator:"
        echo "             Right-click trust_cert.ps1 -> Run with PowerShell (as Admin)"
    fi
else
    echo ""
    echo "  ┌─────────────────────────────────────────────────────────────┐"
    echo "  │  Fix 'Not Secure': Run in Windows PowerShell (Admin):       │"
    echo "  │                                                             │"
    echo "  │  Import-Certificate \\"
    echo "  │    -FilePath 'D:\\Edumi2-my-work2\\certs\\edumi-trust-this.crt' \\"
    echo "  │    -CertStoreLocation Cert:\\LocalMachine\\Root              │"
    echo "  │                                                             │"
    echo "  │  OR: double-click trust_cert.ps1 -> Run as Administrator    │"
    echo "  └─────────────────────────────────────────────────────────────┘"
    echo ""
fi


# =======================================================
# STEP 5: REDIS
# =======================================================
echo "[5/9] Starting Redis..."

if redis-cli ping 2>/dev/null | grep -q "PONG"; then
    echo "      Redis already running"
else
    if ! command -v redis-server &>/dev/null; then
        echo "      Redis not found — installing..."
        sudo apt-get update -qq && sudo apt-get install -y redis-server
    fi
    if command -v redis-server &>/dev/null; then
        redis-server --daemonize yes
        sleep 2
        if redis-cli ping 2>/dev/null | grep -q "PONG"; then
            echo "      [OK] Redis started"
        else
            echo "      [WARN] Redis failed to start — check logs"
        fi
    else
        echo "      [WARN] redis-server still not found after install attempt"
    fi
fi


# =======================================================
# STEP 6: LIVEKIT
# =======================================================
echo "[6/9] Starting LiveKit..."

if [ -n "$LIVEKIT" ]; then
    nohup $LIVEKIT --config "$LIVEKIT_CONFIG" > "$BASE_DIR/logs/livekit.log" 2>&1 &
    echo "      [OK] LiveKit started (PID $!)"
else
    echo "      [SKIP] LiveKit binary not found"
    echo "             To install LiveKit in WSL/Linux, run:"
    echo "             curl -sSL https://get.livekit.io | bash"
fi


# =======================================================
# STEP 6.5: POSTGRESQL
# =======================================================
echo "[6.5/9] Starting PostgreSQL service..."

# ── Install PostgreSQL if missing ─────────────────────────────────────────────
if ! command -v psql &>/dev/null; then
    echo "      PostgreSQL not found — installing..."
    sudo apt-get update -qq && sudo apt-get install -y postgresql postgresql-contrib
fi

# ── Start PostgreSQL (WSL-safe: prefer pg_ctlcluster over systemctl) ──────────
PG_STARTED=false

# Method 1: pg_ctlcluster (most reliable on Debian/Ubuntu WSL)
if command -v pg_ctlcluster &>/dev/null && command -v pg_lsclusters &>/dev/null; then
    PG_VERSION=$(pg_lsclusters -h 2>/dev/null | awk 'NR==1{print $1}')
    PG_CLUSTER=$(pg_lsclusters -h 2>/dev/null | awk 'NR==1{print $2}')
    if [ -n "$PG_VERSION" ] && [ -n "$PG_CLUSTER" ]; then
        pg_ctlcluster "$PG_VERSION" "$PG_CLUSTER" start 2>/dev/null || true
        sleep 2
        # Verify it actually started
        if pg_ctlcluster "$PG_VERSION" "$PG_CLUSTER" status 2>/dev/null | grep -q "online\|running"; then
            echo "      [OK] PostgreSQL $PG_VERSION/$PG_CLUSTER started (pg_ctlcluster)"
            PG_STARTED=true
        fi
    fi
fi

# Method 2: service command (WSL fallback — works without systemd)
if [ "$PG_STARTED" = false ]; then
    service postgresql start 2>/dev/null || true
    sleep 2
    if pg_isready -q 2>/dev/null; then
        echo "      [OK] PostgreSQL started (service)"
        PG_STARTED=true
    fi
fi

# Method 3: systemctl (only works if systemd is running)
if [ "$PG_STARTED" = false ] && command -v systemctl &>/dev/null; then
    systemctl start postgresql 2>/dev/null || true
    sleep 2
    if pg_isready -q 2>/dev/null; then
        echo "      [OK] PostgreSQL started (systemctl)"
        PG_STARTED=true
    fi
fi

# Verify port 5432 is actually open
if ! pg_isready -q 2>/dev/null; then
    echo "      [ERROR] PostgreSQL is not accepting connections on port 5432!"
    echo "              Try manually: sudo service postgresql start"
    echo "              Or check logs: sudo tail /var/log/postgresql/*.log"
    exit 1
fi

sleep 1

# ── Ensure DB user and database exist ─────────────────────────────────────────
echo "      Ensuring PostgreSQL user and database exist..."

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='edumi_user'" 2>/dev/null \
    | grep -q 1 \
    || sudo -u postgres psql -c "CREATE USER edumi_user WITH PASSWORD 'edumi_pass';" 2>/dev/null \
    || true

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='edumi_db'" 2>/dev/null \
    | grep -q 1 \
    || sudo -u postgres psql -c "CREATE DATABASE edumi_db OWNER edumi_user;" 2>/dev/null \
    || true

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE edumi_db TO edumi_user;" 2>/dev/null || true
echo "      [OK] Database ready"

sleep 1


# =======================================================
# STEP 7: DB MIGRATIONS + STATIC FILES
# =======================================================
echo "[7/9] Running migrations and collecting static files..."

"$PYTHON" manage.py migrate --noinput || {
    echo "      [ERROR] Migration failed! Check DB connection and credentials."
    echo "              DATABASE_URL in .env should use 'localhost', not 'db'"
    exit 1
}

# CRITICAL: Do NOT use --clear flag.
# --clear deletes staticfiles.json (the WhiteNoise manifest).
# Without the manifest, WhiteNoise can't resolve hashed filenames
# and returns empty 200 responses with no Content-Type header,
# which causes "Refused to apply style" MIME type errors in Chrome.
"$PYTHON" manage.py collectstatic --noinput

echo "      [OK] Migrations done, static files collected"


# =======================================================
# STEP 8: CELERY + CAMERA SERVICE
# =======================================================
echo "[8/9] Starting Celery worker and Camera Service..."

mkdir -p "$BASE_DIR/logs"

nohup "$BASE_DIR/venv/bin/celery" \
    -A school_project worker -l info -P threads \
    > "$BASE_DIR/logs/celery.log" 2>&1 &
echo "      [OK] Celery started (PID $!, log: logs/celery.log)"

nohup "$PYTHON" camera_service/serve.py \
    > "$BASE_DIR/logs/camera.log" 2>&1 &
echo "      [OK] Camera Service started (PID $!, log: logs/camera.log)"

sleep 2


# =======================================================
# STEP 9: DISPLAY ACCESS INFO + START DAPHNE
# =======================================================
echo ""
echo "======================================================"
echo "    EduMi 2 is starting on HTTPS"
echo "======================================================"
echo ""
echo "  ACCESS FROM THIS MACHINE:"
echo "    https://localhost:8002"
echo "    https://127.0.0.1:8002"
echo "    https://${DOMAIN}:8002"
echo ""
echo "  ACCESS FROM OTHER DEVICES ON THIS NETWORK:"
echo "    https://${LAN_IP}:8002"
echo ""
echo "  FOR OTHER DEVICES - TO REMOVE 'NOT SECURE' WARNING:"
echo "    Copy this file to the other device and trust it:"
echo "    $SSL_EXPORT"
echo ""
echo "    Android/Chrome: Settings > Security > Install cert"
echo "    iPhone/Safari:  Settings > General > VPN & Device"
echo "    Windows:        Double-click > Install > Trusted Root CA"
echo "    Linux:          sudo cp edumi-trust-this.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates"
echo ""
echo "  Or just click 'Advanced -> Proceed' in the browser"
echo ""
echo "  Press Ctrl+C to stop."
echo "======================================================"
echo ""

# Launch Daphne HTTPS server (foreground — blocks until Ctrl+C)
exec "$PYTHON" run_ssl_server.py
