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
Start-Process -FilePath $LIVEKIT -ArgumentList "--config","livekit.yaml" -WindowStyle Minimized
Start-Sleep -Seconds 3

# 4. Run Migrations
Write-Host "[4/7] Preparing Database..." -ForegroundColor Yellow
python manage.py migrate

# 5. Start Celery Worker
Write-Host "[5/7] Starting Celery Worker..." -ForegroundColor Yellow
Start-Process -FilePath "celery" -ArgumentList "-A school_project worker -l info -P solo" -WindowStyle Minimized
Start-Sleep -Seconds 2

# 6. Start Camera Service
Write-Host "[6/7] Starting Camera Service (port 8001)..." -ForegroundColor Yellow
Start-Process -FilePath "python" -ArgumentList "camera_service/manage.py runserver 0.0.0.0:8001" -WindowStyle Minimized
Start-Sleep -Seconds 2

# 7. Start Main App (Daphne)
Write-Host "[7/7] Starting Main Application (port 8000)..." -ForegroundColor Yellow
Write-Host ""
Write-Host "System is starting up!" -ForegroundColor Green
Write-Host "Access App: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Admin Panel: http://localhost:8000/admin/" -ForegroundColor Cyan
Write-Host ""
Write-Host "Keep this window open to see server logs." -ForegroundColor Gray
Write-Host "Press Ctrl+C to stop the web server." -ForegroundColor Gray
Write-Host ""
Write-Host "⚠️  IMPORTANT FOR OTHER STUDENTS:" -ForegroundColor Yellow
Write-Host "If students join via IP (e.g. http://192.168.x.x:8000), they MUST enable" -ForegroundColor Gray
Write-Host "camera permissions in Chrome by going to:" -ForegroundColor Gray
Write-Host "chrome://flags/#unsafely-treat-insecure-origin-as-secure" -ForegroundColor Cyan
Write-Host "And adding your server IP to the list." -ForegroundColor Gray
Write-Host ""

# Start the Main Application in the foreground
python manage.py runserver 0.0.0.0:8000
