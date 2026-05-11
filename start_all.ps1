# Edumi Startup Script
# Usage: powershell -ExecutionPolicy Bypass -File start_all.ps1

$PROJECT = $PSScriptRoot
Set-Location $PROJECT

$_pyPaths = @(
    "C:\Users\$env:USERNAME\AppData\Local\Python\pythoncore-3.14-64\python.exe",
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python313\python.exe",
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python312\python.exe",
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python311\python.exe",
    "C:\Python313\python.exe",
    "C:\Python312\python.exe"
)
$PYTHON = $null
foreach ($c in $_pyPaths) { if (Test-Path $c) { $PYTHON = $c; break } }
if (-not $PYTHON) {
    $PYTHON = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($PYTHON -like "*WindowsApps*") {
        $py = (Get-Command py -ErrorAction SilentlyContinue).Source
        if ($py) { $PYTHON = $py }
    }
}
$_scripts = Join-Path (Split-Path $PYTHON -Parent) "Scripts"
$DAPHNE = Join-Path $_scripts "daphne.exe"
$CELERY = Join-Path $_scripts "celery.exe"
if (-not (Test-Path $DAPHNE)) { $DAPHNE = (Get-Command daphne -ErrorAction SilentlyContinue).Source }
if (-not (Test-Path $CELERY)) { $CELERY = (Get-Command celery -ErrorAction SilentlyContinue).Source }
$LIVEKIT = ".\livekit-bin\livekit-server.exe"

function Write-Step($n, $total, $msg) { Write-Host ""; Write-Host "  [$n/$total] $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "         OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "       WARN  $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "       FAIL  $msg" -ForegroundColor Red }

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

Clear-Host
Write-Host ""
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host "       E D U M I   S T A R T U P" -ForegroundColor Cyan
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host ""

Write-Step 0 7 "Checking tools and cleaning up..."
if (-not $PYTHON -or -not (Test-Path $PYTHON)) { Write-Fail "Python not found!"; exit 1 }
Write-OK "Python: $PYTHON"
if (-not $DAPHNE -or -not (Test-Path $DAPHNE)) { Write-Fail "daphne not found. Run: pip install daphne"; exit 1 }
Write-OK "Daphne: $DAPHNE"
Get-Process | Where-Object { $_.Name -like "*livekit*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process | Where-Object { $_.Name -like "*celery*"  } | Stop-Process -Force -ErrorAction SilentlyContinue
foreach ($port in @(8000, 8001)) { Kill-Port $port }
Start-Sleep -Seconds 1
Write-OK "Ports cleared"

Write-Step 1 7 "Redis"
$redisSvc = Get-Service Redis -ErrorAction SilentlyContinue
if ($null -eq $redisSvc) { Write-Warn "Redis not found - run: winget install Redis.Redis" }
elseif ($redisSvc.Status -ne 'Running') { Start-Service Redis; Start-Sleep -Seconds 2; Write-OK "Redis started :6379" }
else { Write-OK "Redis already running :6379" }

Write-Step 2 7 "LiveKit SFU  (:7880)"
$LAN_IP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.*' } | Select-Object -First 1).IPAddress
if (-not $LAN_IP) { $LAN_IP = "127.0.0.1" }
if (-not (Test-Path $LIVEKIT)) {
    Write-Fail "livekit-server.exe not found"
    Write-Warn "Video meetings will not work"
} else {
    Start-Process -FilePath $LIVEKIT -ArgumentList "--config", "livekit.yaml", "--bind", "0.0.0.0", "--node-ip", $LAN_IP -WindowStyle Hidden
    Start-Sleep -Seconds 2
    if (Wait-Port 7880 15) { Write-OK "LiveKit running :7880  node_ip=$LAN_IP" }
    else { Write-Warn "LiveKit may still be starting..." }
}

Write-Step 3 7 "Writing .env"
$envContent = @(
    "SECRET_KEY=django-insecure-@j!l-9t=qs!b&lkynb=zq`$-h3f9d(_nm!hvctk`$9ij()0kaja%",
    "DEBUG=True",
    "ALLOWED_HOSTS=*",
    "REDIS_URL=redis://localhost:6379/0",
    "CAMERA_SERVICE_URL=http://127.0.0.1:8001",
    "LIVEKIT_API_KEY=devkey",
    "LIVEKIT_API_SECRET=devsecret_must_be_32_characters_long_1234"
)
$envContent | Set-Content -Path ".env" -Encoding UTF8
Write-OK ".env written"

Write-Step 4 7 "Database migrations + static files"
Write-Host "         Running migrations..." -ForegroundColor Gray
$r = & $PYTHON manage.py migrate --run-syncdb 2>&1
if ($LASTEXITCODE -eq 0) { Write-OK "Migrations applied" } else { Write-Warn "Migration issue: $($r | Select-Object -Last 1)" }
Write-Host "         Collecting static files..." -ForegroundColor Gray
$r = & $PYTHON manage.py collectstatic --noinput 2>&1
if ($LASTEXITCODE -eq 0) { Write-OK "Static files collected" } else { Write-Warn "collectstatic issue: $($r | Select-Object -Last 1)" }

Write-Step 5 7 "Camera Service  (:8001)"
Kill-Port 8001
Start-Sleep -Milliseconds 500
Start-Process -FilePath $PYTHON -ArgumentList "camera_service\manage.py", "runserver", "127.0.0.1:8001", "--noreload" -WindowStyle Hidden
if (Wait-Port 8001 25) { Write-OK "Camera service running :8001" } else { Write-Warn "Camera service slow to start" }

Write-Step 6 7 "Celery worker"
if ($CELERY -and (Test-Path $CELERY)) {
    Start-Process -FilePath $CELERY -ArgumentList "-A", "school_project", "worker", "-l", "warning", "-P", "solo", "--without-heartbeat" -WindowStyle Hidden
    Start-Sleep -Seconds 2
    Write-OK "Celery worker started"
} else { Write-Warn "Celery not found - skipping" }

Write-Step 7 7 "Daphne ASGI  (:8000)"
Write-Host ""
Write-Host "  ================================================" -ForegroundColor Green
Write-Host "  Edumi is RUNNING" -ForegroundColor Green
Write-Host "  ------------------------------------------------" -ForegroundColor Green
Write-Host "  Local  : http://localhost:8000" -ForegroundColor White
Write-Host "  LAN    : http://${LAN_IP}:8000" -ForegroundColor White
Write-Host "  ------------------------------------------------" -ForegroundColor Green
Write-Host "  LiveKit: :7880  node_ip=$LAN_IP" -ForegroundColor Gray
Write-Host "  Camera : :8001" -ForegroundColor Gray
Write-Host "  ------------------------------------------------" -ForegroundColor Green
Write-Host "  Remote: port-forward 8000, 7881, 7882" -ForegroundColor Yellow
Write-Host "  Ctrl+C to stop" -ForegroundColor Yellow
Write-Host "  ================================================" -ForegroundColor Green
Write-Host ""

try {
    & $DAPHNE -b 0.0.0.0 -p 8000 school_project.asgi:application
} catch {
    Write-Fail "Daphne failed to start: $_"
} finally {
    Write-Host ""
    Write-Host "  Stopping all services..." -ForegroundColor Red
    Kill-Port 8001
    Get-Process | Where-Object { $_.Name -like "*celery*"  } | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process | Where-Object { $_.Name -like "*livekit*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "  Done." -ForegroundColor Gray
    Write-Host ""
}
