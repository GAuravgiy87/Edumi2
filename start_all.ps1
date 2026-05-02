# ── Edumi Full Startup Script ─────────────────────────────────────────────────
# Starts: LiveKit → ngrok → writes .env → Daphne (ASGI)
# Usage:  powershell -ExecutionPolicy Bypass -File start_all.ps1

$NGROK     = "C:\Users\hp123\Downloads\ngrok-v3-stable-windows-amd64\ngrok.exe"
$LIVEKIT   = ".\livekit-bin\livekit-server.exe"
$NGROK_API = "http://localhost:4040/api/tunnels"

Write-Host ""
Write-Host "=== Edumi Meet Startup ===" -ForegroundColor Cyan
Write-Host ""

# ── 0. Kill any stale processes ───────────────────────────────────────────────
Write-Host "[0/4] Cleaning up old processes..." -ForegroundColor Gray
Get-Process | Where-Object { $_.Name -like "*ngrok*"   } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process | Where-Object { $_.Name -like "*livekit*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# ── 1. Start LiveKit ──────────────────────────────────────────────────────────
Write-Host "[1/4] Starting LiveKit SFU on localhost:7880..." -ForegroundColor Yellow
Start-Process -FilePath $LIVEKIT -ArgumentList "--config","livekit.yaml" -WindowStyle Minimized
Start-Sleep -Seconds 3

try {
    $r = Invoke-WebRequest "http://localhost:7880" -UseBasicParsing -TimeoutSec 5
    Write-Host "      LiveKit OK" -ForegroundColor Green
} catch {
    Write-Host "      LiveKit started" -ForegroundColor Green
}

# ── 2. Start ngrok ────────────────────────────────────────────────────────────
Write-Host "[2/4] Starting ngrok tunnel (port 8000)..." -ForegroundColor Yellow
Start-Process -FilePath $NGROK -ArgumentList "start","django","--config","ngrok.yml" -WindowStyle Minimized
Start-Sleep -Seconds 4

# Read tunnel URL with retries
$ngrokUrl = ""
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Seconds 2
    try {
        $tunnels = (Invoke-RestMethod $NGROK_API).tunnels
        foreach ($t in $tunnels) {
            if ($t.public_url -like "https://*") {
                $ngrokUrl = $t.public_url
                break
            }
        }
        if ($ngrokUrl -ne "") { break }
    } catch {}
}

if ($ngrokUrl -eq "") {
    Write-Host "ERROR: ngrok tunnel not found. Is ngrok authenticated?" -ForegroundColor Red
    exit 1
}

$livekitProxyUrl = ($ngrokUrl -replace "^https://","wss://") + "/livekit-proxy"

Write-Host "      ngrok OK" -ForegroundColor Green
Write-Host ""
Write-Host "  App URL     : $ngrokUrl"        -ForegroundColor Cyan
Write-Host "  LiveKit URL : $livekitProxyUrl"  -ForegroundColor Cyan
Write-Host ""

# ── 3. Write .env ─────────────────────────────────────────────────────────────
Write-Host "[3/4] Writing .env..." -ForegroundColor Yellow

$envContent = @"
SECRET_KEY=django-insecure-@j!l-9t=qs!b&lkynb=zq`$-h3f9d(_nm!hvctk`$9ij()0kaja%
DEBUG=True
ALLOWED_HOSTS=*
LIVEKIT_URL=$livekitProxyUrl
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=devsecret_must_be_32_characters_long_1234
"@

Set-Content -Path ".env" -Value $envContent
Write-Host "      .env written" -ForegroundColor Green

# ── 4. Start Camera Service ──────────────────────────────────────────────────
Write-Host "[4/6] Starting Camera Service on port 8001..." -ForegroundColor Yellow
$pids8001 = (netstat -ano | Select-String ":8001 ") | ForEach-Object {
    ($_ -split '\s+')[-1]
} | Sort-Object -Unique
foreach ($p in $pids8001) {
    if ($p -match '^\d+$' -and $p -ne '0') {
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 1
Start-Process -FilePath "python" -ArgumentList "camera_service/manage.py runserver 0.0.0.0:8001" -WindowStyle Minimized

# ── 5. Start Celery Worker ───────────────────────────────────────────────────
Write-Host "[5/6] Starting Celery Worker..." -ForegroundColor Yellow
Start-Process -FilePath "celery" -ArgumentList "-A school_project worker -l info -P solo" -WindowStyle Minimized
Start-Sleep -Seconds 2

# ── 6. Kill anything on port 8000 then start Django ──────────────────────────
Write-Host "[6/6] Starting Django on port 8000..." -ForegroundColor Yellow

# Free port 8000 if something is already using it
$pids = (netstat -ano | Select-String ":8000 ") | ForEach-Object {
    ($_ -split '\s+')[-1]
} | Sort-Object -Unique
foreach ($p in $pids) {
    if ($p -match '^\d+$' -and $p -ne '0') {
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 1
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Share this URL with students:"            -ForegroundColor White
Write-Host "  $ngrokUrl"                                -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop all services."
Write-Host ""

try {
    # Start Django with Daphne (better for WebSockets)
    daphne -b 0.0.0.0 -p 8000 school_project.asgi:application
}
finally {
    Write-Host ""
    Write-Host "=== Stopping all services ===" -ForegroundColor Red
    
    # 1. Kill Camera Service
    Get-Process | Where-Object { $_.CommandLine -like "*camera_service*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    # 2. Kill Celery
    Get-Process | Where-Object { $_.Name -eq "celery" } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    # 3. Kill ngrok
    Get-Process | Where-Object { $_.Name -like "*ngrok*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    # 4. Kill LiveKit
    Get-Process | Where-Object { $_.Name -like "*livekit*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    Write-Host "Cleanup complete." -ForegroundColor Gray
}
