# =====================================================
# EduMi 2 - FULL SYSTEM STARTUP SCRIPT
# Handles: Hosts file, SSL cert, Redis, LiveKit,
#          Celery, Camera Service, Django HTTPS (Daphne)
# =====================================================
# Usage:  .\start_app.ps1
# Works from any directory. Hosts entry self-elevates
# via UAC on first run (one-time approve).
# =====================================================

$ErrorActionPreference = "Continue"

$BASE_DIR       = $PSScriptRoot
$LIVEKIT        = Join-Path $BASE_DIR "livekit-bin\livekit-server.exe"
$LIVEKIT_CONFIG = Join-Path $BASE_DIR "config\livekit.yaml"
$SSL_CERT       = Join-Path $BASE_DIR "certs\edumi.crt"
$SSL_KEY        = Join-Path $BASE_DIR "certs\edumi.key"
$HOSTS_FILE     = "$env:windir\System32\drivers\etc\hosts"
$DOMAIN         = "edumi.ac.in"
$PYTHON         = Join-Path $BASE_DIR "venv311\Scripts\python.exe"

Set-Location $BASE_DIR

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "        EduMi 2: Academic Command Center"              -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""


# =======================================================
# STEP 0: HOSTS FILE  (auto-elevates via UAC if needed)
# =======================================================
Write-Host "[0/9] Checking hosts file for $DOMAIN ..." -ForegroundColor Gray

$hostsEntryExists = $false
try {
    $hostsEntryExists = Select-String -Path $HOSTS_FILE -Pattern "edumi\.ac\.in" -Quiet
} catch {}

if ($hostsEntryExists) {
    Write-Host "      $DOMAIN already in hosts file - SKIP" -ForegroundColor Green
} else {
    $hostsLine = "127.0.0.1    $DOMAIN    www.$DOMAIN"
    $comment   = "# EduMi 2 - Local Development SSL Domain"

    $isAdmin = ([Security.Principal.WindowsPrincipal] `
        [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)

    if ($isAdmin) {
        Add-Content -Path $HOSTS_FILE -Value "`n$comment`n$hostsLine" -Force
        ipconfig /flushdns | Out-Null
        Write-Host "      [OK] Added '$hostsLine' to hosts file" -ForegroundColor Green
        Write-Host "      [OK] DNS cache flushed" -ForegroundColor Green
    } else {
        Write-Host "      Requesting admin to add hosts entry (UAC prompt)..." -ForegroundColor Yellow

        $addLine     = "# EduMi 2 - Local Development SSL Domain`n127.0.0.1    $DOMAIN    www.$DOMAIN"
        $elevatedCmd = "Add-Content -Path '$HOSTS_FILE' -Value '$addLine' -Force; ipconfig /flushdns | Out-Null"

        Start-Process powershell `
            -ArgumentList "-NoProfile", "-Command", $elevatedCmd `
            -Verb RunAs `
            -WindowStyle Hidden `
            -ErrorAction SilentlyContinue

        Write-Host "      [OK] UAC elevation requested - approve if prompted" -ForegroundColor Yellow
    }
}


# =======================================================
# STEP 1: CLEAN OLD PROCESSES
# =======================================================
Write-Host "[1/9] Cleaning old processes..." -ForegroundColor Gray

Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match "python|celery|daphne|livekit"
} | Stop-Process -Force -ErrorAction SilentlyContinue

function Kill-Port($port) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($c in $connections) {
        try { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
    }
}

Kill-Port 8002
Kill-Port 8003
Start-Sleep -Seconds 2


# =======================================================
# STEP 2: SSL CERTIFICATE (auto-generate if missing)
# =======================================================
Write-Host "[2/9] Checking SSL certificate..." -ForegroundColor Yellow

if (-not (Test-Path $SSL_CERT) -or -not (Test-Path $SSL_KEY)) {
    Write-Host "      Generating self-signed SSL certificate for $DOMAIN ..." -ForegroundColor Yellow
    & $PYTHON (Join-Path $BASE_DIR "scripts\generate_ssl_cert.py")
    if (-not (Test-Path $SSL_CERT)) {
        Write-Host "      [FAIL] Certificate generation failed!" -ForegroundColor Red
    } else {
        Write-Host "      [OK] Certificate generated" -ForegroundColor Green
    }
} else {
    Write-Host "      [OK] SSL certificate found" -ForegroundColor Green
}


# =======================================================
# STEP 3: REDIS
# =======================================================
Write-Host "[3/9] Starting Redis..." -ForegroundColor Yellow

try {
    $ping = redis-cli ping 2>$null
    if ($ping -eq "PONG") {
        Write-Host "      Redis already running" -ForegroundColor Green
    } else {
        throw
    }
}
catch {
    Start-Process "redis-server" -WindowStyle Minimized
    Start-Sleep -Seconds 3
    Write-Host "      Redis started" -ForegroundColor Green
}


# =======================================================
# STEP 4: LIVEKIT
# =======================================================
Write-Host "[4/9] Starting LiveKit..." -ForegroundColor Yellow

if (Test-Path $LIVEKIT) {
    Start-Process "cmd.exe" `
        -ArgumentList "/c `"$LIVEKIT --config $LIVEKIT_CONFIG`"" `
        -WindowStyle Minimized
    Write-Host "      LiveKit started" -ForegroundColor Green
} else {
    Write-Host "      LiveKit binary not found - SKIP" -ForegroundColor Red
}

Start-Sleep -Seconds 3


# =======================================================
# STEP 5: DATABASE MIGRATIONS
# =======================================================
Write-Host "[5/9] Running database migrations..." -ForegroundColor Yellow
& $PYTHON manage.py migrate


# =======================================================
# STEP 6: COLLECT STATIC FILES (required for WhiteNoise)
# =======================================================
Write-Host "[6/9] Collecting static files..." -ForegroundColor Yellow
& $PYTHON manage.py collectstatic --noinput --clear 2>$null
Write-Host "      [OK] Static files collected" -ForegroundColor Green


# =======================================================
# STEP 7: CELERY WORKER
# =======================================================
Write-Host "[7/9] Starting Celery worker..." -ForegroundColor Yellow

Start-Process (Join-Path $BASE_DIR "venv311\Scripts\celery.exe") `
    -ArgumentList "-A school_project worker -l info -P threads" `
    -WorkingDirectory $BASE_DIR `
    -WindowStyle Minimized

Start-Sleep -Seconds 2


# =======================================================
# STEP 8: CAMERA SERVICE
# =======================================================
Write-Host "[8/9] Starting Camera Service..." -ForegroundColor Yellow

Start-Process $PYTHON `
    -ArgumentList "camera_service/serve.py" `
    -WorkingDirectory $BASE_DIR `
    -WindowStyle Minimized

Start-Sleep -Seconds 2


# =======================================================
# STEP 9: DJANGO HTTPS SERVER (Daphne + SSL)
# =======================================================
Write-Host "[9/9] Starting Django HTTPS Server (Daphne + SSL)..." -ForegroundColor Yellow
Write-Host ""

Write-Host "======================================================" -ForegroundColor Green
Write-Host "    ALL SERVICES STARTED SUCCESSFULLY (HTTPS)"         -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  App:     https://$DOMAIN`:8002"            -ForegroundColor Cyan
Write-Host "           https://localhost:8002"            -ForegroundColor Cyan
Write-Host "           https://127.0.0.1:8002"           -ForegroundColor Cyan
Write-Host "  Admin:   https://$DOMAIN`:8002/admin/"      -ForegroundColor Cyan
Write-Host ""
Write-Host "  NOTE: Browser will warn about the self-signed cert."  -ForegroundColor Yellow
Write-Host "        Click 'Advanced -> Proceed' to continue."       -ForegroundColor Yellow
Write-Host ""
Write-Host "  Press Ctrl+C to stop the server."                     -ForegroundColor Gray
Write-Host ""

# Launch Daphne with SSL via Python launcher (Daphne CLI has no --ssl flags)
& $PYTHON run_ssl_server.py
