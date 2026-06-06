# EduMi 2 Complete Startup Script
# Starts: Redis -> LiveKit -> Django (Daphne) -> Celery -> Camera Service

$LIVEKIT = ".\livekit-bin\livekit-server.exe"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "        EduMi 2: Academic Command Center" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Kill any stale processes
Write-Host "[1/7] Cleaning up old processes..." -ForegroundColor Gray
Get-Process | Where-Object { $_.Name -like "*livekit*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process | Where-Object { $_.Name -like "*python*" -and $_.CommandLine -like "*manage.py*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process | Where-Object { $_.Name -like "*celery*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# 2. Check/Start Redis
Write-Host "[2/7] Checking Redis Server..." -ForegroundColor Yellow
try {
    $redisTest = redis-cli ping
    if ($redisTest -eq "PONG") {
        Write-Host "      Redis is already running." -ForegroundColor Green
    } else {
        Write-Host "      Starting Redis..." -ForegroundColor Yellow
        Start-Process -FilePath "redis-server" -WindowStyle Minimized
        Start-Sleep -Seconds 2
    }
} catch {
    Write-Host "      Starting Redis..." -ForegroundColor Yellow
    Start-Process -FilePath "redis-server" -WindowStyle Minimized
    Start-Sleep -Seconds 2
}

# 3. Start LiveKit
Write-Host "[3/7] Starting LiveKit SFU (localhost:7880)..." -ForegroundColor Yellow
Start-Process -FilePath $LIVEKIT -ArgumentList "--config","config/livekit.yaml" -WindowStyle Minimized
Start-Sleep -Seconds 3

# 4. Run Migrations
Write-Host "[4/7] Preparing Database..." -ForegroundColor Yellow
python manage.py migrate

# 5. Start Celery Worker
Write-Host "[5/7] Starting Celery Worker..." -ForegroundColor Yellow
Start-Process -FilePath "celery" -ArgumentList "-A school_project worker -l info -P solo" -WindowStyle Minimized
Start-Sleep -Seconds 2

# 6. Start Camera Service
Write-Host "[6/7] Starting Camera Service (port 8003)..." -ForegroundColor Yellow
Start-Process -FilePath "python" -ArgumentList "camera_service/manage.py runserver 0.0.0.0:8003" -WindowStyle Minimized
Start-Sleep -Seconds 2

# 7. Start Main App (Django Extensions runserver_plus with HTTPS)
Write-Host "[7/7] Starting Main Application (HTTPS on port 8002)..." -ForegroundColor Yellow
Write-Host ""
Write-Host "System is starting up!" -ForegroundColor Green
Write-Host "Access App: https://localhost:8002" -ForegroundColor Cyan
Write-Host "Admin Panel: https://localhost:8002/admin/" -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 NOTE: You'll see a 'Your connection is not private' warning in Chrome" -ForegroundColor Yellow
Write-Host "Click 'Advanced' then 'Proceed to localhost (unsafe)' to continue" -ForegroundColor Gray
Write-Host ""
Write-Host "Keep this window open to see server logs." -ForegroundColor Gray
Write-Host "Press Ctrl+C to stop the web server." -ForegroundColor Gray
Write-Host ""

# Check if certs exist, create if not
$certDir = ".\certs"
if (-not (Test-Path $certDir)) {
    New-Item -ItemType Directory -Path $certDir | Out-Null
}

# Generate self-signed cert using OpenSSL if available, or let runserver_plus handle it
try {
    $hasOpenSSL = $null -ne (Get-Command openssl -ErrorAction SilentlyContinue)
    if ($hasOpenSSL -and -not (Test-Path "$certDir\server.crt")) {
        Write-Host "Generating self-signed SSL certificate..." -ForegroundColor Yellow
        openssl req -x509 -newkey rsa:4096 -keyout "$certDir\server.key" -out "$certDir\server.crt" -days 365 -nodes -subj "/CN=localhost" 2>&1 | Out-Null
        Write-Host "SSL certificate generated successfully!" -ForegroundColor Green
    }
} catch {
    Write-Host "OpenSSL not found, using built-in certificate generation..." -ForegroundColor Yellow
}

# Start the Main Application with HTTPS
if (Test-Path "$certDir\server.crt") {
    python manage.py runserver_plus 0.0.0.0:8002 --cert-file="$certDir\server.crt" --key-file="$certDir\server.key"
} else {
    python manage.py runserver_plus 0.0.0.0:8002
}
