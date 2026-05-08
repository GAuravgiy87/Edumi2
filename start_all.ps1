# =============================================================================
#  Edumi -- One-Click Startup Script
#  Starts: Redis, LiveKit, ngrok, Migrations, Static, Camera Service,
#          Celery Worker, Daphne ASGI (foreground)
#
#  Usage:
#    powershell -ExecutionPolicy Bypass -File start_all.ps1
# =============================================================================

# -- Paths --------------------------------------------------------------------
$PYTHON    = "C:\Users\hp123\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$DAPHNE    = "C:\Users\hp123\AppData\Local\Python\pythoncore-3.14-64\Scripts\daphne.exe"
$CELERY    = "C:\Users\hp123\AppData\Local\Python\pythoncore-3.14-64\Scripts\celery.exe"
$NGROK     = "C:\Users\hp123\Downloads\ngrok-v3-stable-windows-amd64\ngrok.exe"
$LIVEKIT   = ".\livekit-bin\livekit-server.exe"
$NGROK_API = "http://localhost:4040/api/tunnels"
$PROJECT   = $PSScriptRoot

# -- Helpers ------------------------------------------------------------------
function Write-Step($n, $total, $msg) {
    Write-Host ""
    Write-Host "  [$n/$total] $msg" -ForegroundColor Cyan
}
function Write-OK($msg)   { Write-Host "         OK  $msg" -ForegroundColor Green  }
function Write-Warn($msg) { Write-Host "       WARN  $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "       FAIL  $msg" -ForegroundColor Red    }

function Kill-Port($port) {
    $lines = netstat -ano 2>$null | Select-String ":$port\s"
    foreach ($line in $lines) {
        $p = ($line -split '\s+')[-1]
        if ($p -match '^\d+$' -and [int]$p -gt 0) {
            Stop-Process -Id ([int]$p) -Force -ErrorAction SilentlyContinue
        }
    }
}

function Wait-Port($port, $timeoutSec = 20) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $tcp.Connect("127.0.0.1", $port)
            $tcp.Close()
            return $true
        } catch { Start-Sleep -Milliseconds 500 }
    }
    return $false
}

# -- Banner -------------------------------------------------------------------
Clear-Host
Write-Host ""
Write-Host "  +==================================================+" -ForegroundColor Cyan
Write-Host "  |           E D U M I   B Y    G A U R A V               |" -ForegroundColor Cyan
Write-Host "  +==================================================+" -ForegroundColor Cyan
Write-Host ""

Set-Location $PROJECT

# =============================================================================
#  STEP 0 -- Kill stale processes and free ports
# =============================================================================
Write-Step 0 8 "Cleaning up stale processes..."

Get-Process | Where-Object { $_.Name -like "*ngrok*"   } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process | Where-Object { $_.Name -like "*livekit*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process | Where-Object { $_.Name -like "*celery*"  } | Stop-Process -Force -ErrorAction SilentlyContinue

foreach ($port in @(80, 8000, 8001)) {
    Kill-Port $port
}
Start-Sleep -Seconds 1
Write-OK "Ports cleared"

# =============================================================================
#  STEP 1 -- Redis
# =============================================================================
Write-Step 1 8 "Redis  (WebSocket channel layer + Celery broker)"

$redisSvc = Get-Service Redis -ErrorAction SilentlyContinue
if ($null -eq $redisSvc) {
    Write-Fail "Redis service not found.  Run:  winget install Redis.Redis"
    Write-Warn "Continuing without Redis -- WebSocket uses in-memory layer"
} elseif ($redisSvc.Status -ne 'Running') {
    Start-Service Redis
    Start-Sleep -Seconds 2
    Write-OK "Redis started  :6379"
} else {
    Write-OK "Redis already running  :6379"
}

# =============================================================================
#  STEP 2 -- LiveKit SFU
# =============================================================================
Write-Step 2 8 "LiveKit SFU  (WebRTC video/audio  :7880)"

if (-not (Test-Path $LIVEKIT)) {
    Write-Fail "livekit-server.exe not found at $LIVEKIT"
    Write-Warn "Video meetings will not work"
} else {
    Start-Process -FilePath $LIVEKIT -ArgumentList "--config", "livekit.yaml", "--bind", "0.0.0.0" `
        -RedirectStandardOutput "livekit.log" -RedirectStandardError "livekit_err.log" `
        -WindowStyle Hidden
    Start-Sleep -Seconds 2
    if (Wait-Port 7880 10) {
        Write-OK "LiveKit running  :7880"
    } else {
        Write-Warn "LiveKit may still be starting..."
    }
}

# =============================================================================
#  STEP 3 -- URL Info
# =============================================================================
Write-Step 3 8 "URL Configuration"

$localUrl = "http://localhost:8000"
$lanUrl   = "http://$(hostname):8000"
Write-OK "Local Access: $localUrl"
Write-OK "LAN Access  : $lanUrl"
Write-Warn "Note: For remote access, run ngrok manually: ngrok http 8000"

# =============================================================================
#  STEP 4 -- Write .env
# =============================================================================
Write-Step 4 8 "Writing .env"

$envLines = @(
    "SECRET_KEY=django-insecure-@j!l-9t=qs!b&lkynb=zq`$-h3f9d(_nm!hvctk`$9ij()0kaja%",
    "DEBUG=True",
    "ALLOWED_HOSTS=*",
    "REDIS_URL=redis://localhost:6379/0",
    "CAMERA_SERVICE_URL=http://127.0.0.1:8001",
    "LIVEKIT_API_KEY=devkey",
    "LIVEKIT_API_SECRET=devsecret32charsshallbeusedhere1"
)
$envLines | Set-Content -Path ".env" -Encoding UTF8
Write-OK ".env written  (LiveKit URL auto-derived from request - no hardcoding needed)"

# =============================================================================
#  STEP 5 -- Database migrations + collectstatic
# =============================================================================
Write-Step 5 8 "Database migrations + static files"

Write-Host "         Running migrations..." -ForegroundColor Gray
$migrateResult = & $PYTHON manage.py migrate --run-syncdb 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-OK "Migrations applied"
} else {
    Write-Warn "Migration issue (last line): $($migrateResult | Select-Object -Last 1)"
}

Write-Host "         Collecting static files..." -ForegroundColor Gray
$staticResult = & $PYTHON manage.py collectstatic --noinput 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-OK "Static files collected -> staticfiles/"
} else {
    Write-Warn "collectstatic issue: $($staticResult | Select-Object -Last 1)"
}

# =============================================================================
#  STEP 6 -- Camera Service
# =============================================================================
Write-Step 6 8 "Camera Service  (:8001  RTSP -> HLS)"

Kill-Port 8001
Start-Sleep -Milliseconds 500

Start-Process -FilePath $PYTHON `
    -ArgumentList "camera_service\manage.py", "runserver", "127.0.0.1:8001", "--noreload" `
    -WindowStyle Hidden

Write-Host "         Waiting for camera service..." -ForegroundColor Gray
if (Wait-Port 8001 25) {
    Write-OK "Camera service running  :8001"
} else {
    Write-Warn "Camera service slow to start -- will retry on first camera request"
}

# =============================================================================
#  STEP 7 -- Celery Worker
# =============================================================================
Write-Step 7 8 "Celery worker  (background tasks)"

Start-Process -FilePath $CELERY `
    -ArgumentList "-A", "school_project", "worker", "-l", "warning", "-P", "solo", "--without-heartbeat" `
    -WindowStyle Hidden
Start-Sleep -Seconds 2
Write-OK "Celery worker started"

# =============================================================================
#  STEP 8 -- Daphne ASGI  (foreground -- Ctrl+C stops everything)
# =============================================================================
Write-Step 8 8 "Daphne ASGI  (:8000  foreground)"

Write-Host ""
Write-Host "  +============================================================+" -ForegroundColor Green
Write-Host "  |  Edumi is RUNNING                                          |" -ForegroundColor Green
Write-Host "  +============================================================+" -ForegroundColor Green
Write-Host "  |  Local   ->  http://localhost:8000" -ForegroundColor White
Write-Host "  |  LAN     ->  http://$(hostname):8000" -ForegroundColor White
Write-Host "  +------------------------------------------------------------+" -ForegroundColor Green
Write-Host "  |  Redis      :6379   WebSocket + Celery                     |" -ForegroundColor Gray
Write-Host "  |  LiveKit    :7880   WebRTC SFU                             |" -ForegroundColor Gray
Write-Host "  |  Camera svc :8001   RTSP -> HLS                            |" -ForegroundColor Gray
Write-Host "  |  Celery             Background tasks                       |" -ForegroundColor Gray
Write-Host "  +------------------------------------------------------------+" -ForegroundColor Green
Write-Host "  |  Press Ctrl+C to stop everything                           |" -ForegroundColor Yellow
Write-Host "  +============================================================+" -ForegroundColor Green
Write-Host ""

try {
    & $DAPHNE -b 0.0.0.0 -p 8000 -v 0 school_project.asgi:application
} finally {
    Write-Host ""
    Write-Host "  Stopping all services..." -ForegroundColor Red

    # Camera service
    Kill-Port 8001

    # Celery
    Get-Process | Where-Object { $_.Name -like "*celery*" } |
        Stop-Process -Force -ErrorAction SilentlyContinue

    # LiveKit
    Get-Process | Where-Object { $_.Name -like "*livekit*" } |
        Stop-Process -Force -ErrorAction SilentlyContinue

    Write-Host "  All services stopped." -ForegroundColor Gray
    Write-Host ""
}
