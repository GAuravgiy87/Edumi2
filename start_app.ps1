# =====================================================
# EduMi 2 - FULL SYSTEM STARTUP SCRIPT
# One file does everything:
#   - Firewall rules
#   - Hosts file
#   - SSL cert generation + LAN-aware cert
#   - Cert trust (this machine)
#   - Cert export for other devices
#   - Redis, LiveKit, Celery, Camera Service
#   - DB migrations, static files
#   - Django HTTPS (Daphne)
# =====================================================
# Usage:  .\start_app.bat   (double-click)
#         .\start_app.ps1   (PowerShell)
# =====================================================

$ErrorActionPreference = "Continue"

$BASE_DIR       = $PSScriptRoot
$LIVEKIT        = Join-Path $BASE_DIR "livekit-bin\livekit-server.exe"
$LIVEKIT_CONFIG = Join-Path $BASE_DIR "config\livekit.yaml"
$SSL_CERT       = Join-Path $BASE_DIR "certs\edumi.crt"
$SSL_KEY        = Join-Path $BASE_DIR "certs\edumi.key"
$SSL_EXPORT     = Join-Path $BASE_DIR "certs\edumi-trust-this.crt"
$HOSTS_FILE     = "$env:windir\System32\drivers\etc\hosts"
$DOMAIN         = "edumi.ac.in"
$PYTHON         = Join-Path $BASE_DIR "venv\Scripts\python.exe"

Set-Location $BASE_DIR

# ── Check admin ────────────────────────────────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "        EduMi 2: Academic Command Center"              -ForegroundColor Cyan
if (-not $isAdmin) {
Write-Host "  (tip: run as Administrator for firewall + hosts)"    -ForegroundColor DarkYellow
}
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# ── Detect LAN IP early (used in cert + display) ───────────────────────────────
$LAN_IP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.InterfaceAlias -notlike "*Loopback*" -and
    $_.InterfaceAlias -notlike "*Bluetooth*" -and
    $_.InterfaceAlias -notlike "*Virtual*"  -and
    $_.IPAddress      -notlike "169.254.*"  -and
    $_.IPAddress      -ne "127.0.0.1"
} | Sort-Object { [System.Version]$_.IPAddress } | Select-Object -First 1).IPAddress

if (-not $LAN_IP) { $LAN_IP = "10.7.11.141" }
Write-Host "      Detected LAN IP: $LAN_IP" -ForegroundColor DarkCyan


# =======================================================
# STEP 0: FIREWALL RULES
# =======================================================
Write-Host "[0/9] Applying firewall rules..." -ForegroundColor Gray

if ($isAdmin) {
    $fw_ports = @(
        @{Name="EduMi-8002-HTTPS"; Port=8002;         Proto="TCP"},
        @{Name="EduMi-8003-Cam";   Port=8003;         Proto="TCP"},
        @{Name="EduMi-7880-LK";    Port=7880;         Proto="TCP"},
        @{Name="EduMi-7881-LK";    Port=7881;         Proto="TCP"},
        @{Name="EduMi-7882-LK";    Port=7882;         Proto="UDP"},
        @{Name="EduMi-LK-Media";   Port="50000-50200"; Proto="UDP"}
    )
    foreach ($r in $fw_ports) {
        Remove-NetFirewallRule -DisplayName "$($r.Name)-In"  -ErrorAction SilentlyContinue
        Remove-NetFirewallRule -DisplayName "$($r.Name)-Out" -ErrorAction SilentlyContinue
        New-NetFirewallRule -DisplayName "$($r.Name)-In"  -Direction Inbound  -Protocol $r.Proto -LocalPort $r.Port -Action Allow -Profile Any | Out-Null
        New-NetFirewallRule -DisplayName "$($r.Name)-Out" -Direction Outbound -Protocol $r.Proto -LocalPort $r.Port -Action Allow -Profile Any | Out-Null
    }
    # Allow Python exe itself
    $pyPath = $PYTHON
    Remove-NetFirewallRule -DisplayName "EduMi-Python-In" -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName "EduMi-Python-In" -Direction Inbound -Program $pyPath -Action Allow -Profile Any | Out-Null
    Write-Host "      [OK] Firewall rules applied (8002, 8003, 7880-7882, 50000-50200)" -ForegroundColor Green
} else {
    Write-Host "      [SKIP] Need Administrator to set firewall rules" -ForegroundColor Yellow
    Write-Host "             Re-run as Administrator for full setup"   -ForegroundColor Yellow
}


# =======================================================
# STEP 1: HOSTS FILE
# =======================================================
Write-Host "[1/9] Checking hosts file for $DOMAIN ..." -ForegroundColor Gray

$hostsHasEntry = $false
try { $hostsHasEntry = Select-String -Path $HOSTS_FILE -Pattern "edumi\.ac\.in" -Quiet } catch {}

if ($hostsHasEntry) {
    Write-Host "      $DOMAIN already in hosts file - SKIP" -ForegroundColor Green
} elseif ($isAdmin) {
    $hostsLine = "127.0.0.1    $DOMAIN    www.$DOMAIN"
    Add-Content -Path $HOSTS_FILE -Value "`n# EduMi 2 - Local SSL Domain`n$hostsLine" -Force
    ipconfig /flushdns | Out-Null
    Write-Host "      [OK] Added: $hostsLine" -ForegroundColor Green
} else {
    Write-Host "      [SKIP] Need Administrator to edit hosts file" -ForegroundColor Yellow
}


# =======================================================
# STEP 2: CLEAN OLD PROCESSES
# =======================================================
Write-Host "[2/9] Cleaning old processes..." -ForegroundColor Gray

Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match "python|celery|daphne|livekit"
} | Stop-Process -Force -ErrorAction SilentlyContinue

function Kill-Port($port) {
    $conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        try { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
    }
}
Kill-Port 8002
Kill-Port 8003
Start-Sleep -Seconds 2
Write-Host "      [OK] Ports cleared" -ForegroundColor Green


# =======================================================
# STEP 3: SSL CERTIFICATE
# Always regenerate to pick up current LAN IP.
# Then ALWAYS reinstall into trusted store so server cert
# and trusted cert are ALWAYS the same file.
# =======================================================
Write-Host "[3/9] Generating SSL certificate (LAN-aware)..." -ForegroundColor Yellow

& $PYTHON -c @"
import datetime, ipaddress, socket, sys, shutil
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from pathlib import Path

DOMAIN   = 'edumi.ac.in'
CERT_DIR = Path(r'$BASE_DIR\certs')
CERT_DIR.mkdir(parents=True, exist_ok=True)

lan_ips = ['127.0.0.1', '$LAN_IP']
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80)); detected = s.getsockname()[0]; s.close()
    if detected not in lan_ips: lan_ips.append(detected)
except: pass

hostname = socket.gethostname()

key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

san = [
    x509.DNSName(DOMAIN), x509.DNSName(f'www.{DOMAIN}'),
    x509.DNSName('localhost'), x509.DNSName(hostname),
]
for ip in lan_ips:
    try: san.append(x509.IPAddress(ipaddress.IPv4Address(ip)))
    except: pass
san.append(x509.IPAddress(ipaddress.IPv6Address('::1')))

subj = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'IN'),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'EduMi Academic'),
    x509.NameAttribute(NameOID.COMMON_NAME, DOMAIN),
])
now = datetime.datetime.utcnow()
cert = (x509.CertificateBuilder()
    .subject_name(subj).issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now)
    .not_valid_after(now + datetime.timedelta(days=3650))
    .add_extension(x509.SubjectAlternativeName(san), critical=False)
    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    .sign(key, hashes.SHA256(), default_backend()))

(CERT_DIR / 'edumi.key').write_bytes(key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
    serialization.NoEncryption()))
(CERT_DIR / 'edumi.crt').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
shutil.copy2(CERT_DIR / 'edumi.crt', CERT_DIR / 'edumi-trust-this.crt')
print('[OK] cert covers:', [str(s) for s in san])
"@

if (-not (Test-Path $SSL_CERT)) {
    Write-Host "      [FAIL] Certificate generation failed!" -ForegroundColor Red
    exit 1
}
Write-Host "      [OK] Certificate generated (covers LAN IP: $LAN_IP)" -ForegroundColor Green


# =======================================================
# STEP 4: TRUST CERT — always reinstall after regeneration
# This ensures the trusted cert and the server cert are
# ALWAYS the same file, eliminating "Not secure" errors.
# =======================================================
Write-Host "[4/9] Installing certificate into Trusted Root CA..." -ForegroundColor Yellow

$installScript = @"
`$certPath = '$SSL_CERT'
`$newCert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2(`$certPath)

# Remove all old EduMi certs from LocalMachine Root
`$store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root','LocalMachine')
`$store.Open('ReadWrite')
`$store.Certificates | Where-Object { `$_.Subject -match 'edumi' -or `$_.Issuer -match 'edumi' } | ForEach-Object { `$store.Remove(`$_) }
`$store.Add(`$newCert)
`$store.Close()
Write-Host 'Installed:' `$newCert.Thumbprint
"@

$tmpScript = "$env:TEMP\edumi_trust.ps1"
$installScript | Out-File $tmpScript -Encoding UTF8

if ($isAdmin) {
    # Already admin — install directly
    & powershell -ExecutionPolicy Bypass -File $tmpScript
    Write-Host "      [OK] Certificate trusted (admin)" -ForegroundColor Green
} else {
    # Need UAC elevation
    Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$tmpScript`"" -Verb RunAs -Wait
    Write-Host "      [OK] Certificate trusted (elevated)" -ForegroundColor Green
}

Remove-Item $tmpScript -ErrorAction SilentlyContinue

# Clear Chrome's SSL cache so it picks up the new cert immediately
# (Chrome caches cert trust decisions — must be cleared after cert change)
Get-Process -Name "chrome" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$chromeSslFiles = @(
    "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\TransportSecurity",
    "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Certificate Revocation Lists"
)
foreach ($f in $chromeSslFiles) {
    if (Test-Path $f) { Remove-Item $f -Force -ErrorAction SilentlyContinue }
}
ipconfig /flushdns | Out-Null
Write-Host "      [OK] Chrome SSL cache cleared, DNS flushed" -ForegroundColor Green


# =======================================================
# STEP 5: REDIS
# =======================================================
Write-Host "[5/9] Starting Redis..." -ForegroundColor Yellow

$redisPing = redis-cli ping 2>$null
if ($redisPing -eq "PONG") {
    Write-Host "      Redis already running" -ForegroundColor Green
} else {
    Start-Process "redis-server" -WindowStyle Minimized
    Start-Sleep -Seconds 3
    Write-Host "      Redis started" -ForegroundColor Green
}


# =======================================================
# STEP 6: LIVEKIT
# =======================================================
Write-Host "[6/9] Starting LiveKit..." -ForegroundColor Yellow

if (Test-Path $LIVEKIT) {
    Start-Process "cmd.exe" -ArgumentList "/c `"$LIVEKIT --config $LIVEKIT_CONFIG`"" -WindowStyle Minimized
    Write-Host "      LiveKit started" -ForegroundColor Green
} else {
    Write-Host "      LiveKit binary not found - SKIP" -ForegroundColor DarkYellow
}
Start-Sleep -Seconds 2


# =======================================================
# STEP 7: DB MIGRATIONS + STATIC FILES
# =======================================================
Write-Host "[7/9] Running migrations and collecting static files..." -ForegroundColor Yellow
& $PYTHON manage.py migrate --noinput

# CRITICAL: Do NOT use --clear flag.
# --clear deletes staticfiles.json (the WhiteNoise manifest).
# Without the manifest, WhiteNoise can't resolve hashed filenames
# and returns empty 200 responses with no Content-Type header,
# which causes "Refused to apply style" MIME type errors in Chrome.
& $PYTHON manage.py collectstatic --noinput
Write-Host "      [OK] Migrations done, static files collected" -ForegroundColor Green


# =======================================================
# STEP 8: CELERY + CAMERA SERVICE
# =======================================================
Write-Host "[8/9] Starting Celery worker and Camera Service..." -ForegroundColor Yellow

Start-Process (Join-Path $BASE_DIR "venv\Scripts\celery.exe") `
    -ArgumentList "-A school_project worker -l info -P threads" `
    -WorkingDirectory $BASE_DIR -WindowStyle Minimized

Start-Process $PYTHON `
    -ArgumentList "camera_service/serve.py" `
    -WorkingDirectory $BASE_DIR -WindowStyle Minimized

Start-Sleep -Seconds 2
Write-Host "      [OK] Celery and Camera Service started" -ForegroundColor Green


# =======================================================
# STEP 9: DISPLAY ACCESS INFO + START DAPHNE
# =======================================================
Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "    EduMi 2 is starting on HTTPS                     " -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  ACCESS FROM THIS MACHINE:"                           -ForegroundColor Cyan
Write-Host "    https://localhost:8002"                            -ForegroundColor White
Write-Host "    https://127.0.0.1:8002"                           -ForegroundColor White
Write-Host "    https://$DOMAIN`:8002"                            -ForegroundColor White
Write-Host ""
Write-Host "  ACCESS FROM OTHER DEVICES ON THIS NETWORK:"         -ForegroundColor Yellow
Write-Host "    https://$LAN_IP`:8002"                            -ForegroundColor White
Write-Host ""
Write-Host "  FOR OTHER DEVICES - TO REMOVE 'NOT SECURE' WARNING:"  -ForegroundColor Magenta
Write-Host "    Copy this file to the other device and trust it:"   -ForegroundColor White
Write-Host "    $SSL_EXPORT"                                       -ForegroundColor DarkGray
Write-Host ""
Write-Host "    Android/Chrome: Settings > Security > Install cert" -ForegroundColor DarkGray
Write-Host "    iPhone/Safari:  Settings > General > VPN & Device" -ForegroundColor DarkGray
Write-Host "    Windows:        Double-click > Install > Trusted Root CA" -ForegroundColor DarkGray
Write-Host "    Linux:          sudo cp edumi-trust-this.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Or just click 'Advanced -> Proceed' in the browser"  -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Press Ctrl+C to stop."                               -ForegroundColor Gray
Write-Host "======================================================"  -ForegroundColor Green
Write-Host ""

# Launch Daphne HTTPS server (foreground — blocks until Ctrl+C)
& $PYTHON run_ssl_server.py
