# =============================================================================
#  Edumi -- One-Click Startup Script
#  Starts: Redis, LiveKit, ngrok, Migrations, Static, Camera Service,
#          Celery Worker, Daphne ASGI (HTTP :8000 + HTTPS :8443)
#
#  Usage:
#    powershell -ExecutionPolicy Bypass -File start_all.ps1
#
#  HTTPS is required for WebRTC (camera/mic) to work in the browser.
#  Access the app at https://10.7.11.141:8443  (accept the self-signed cert)
# =============================================================================

# -- Paths --------------------------------------------------------------------
$PYTHON    = "C:\Users\hp123\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$DAPHNE    = "C:\Users\hp123\AppData\Local\Python\pythoncore-3.14-64\Scripts\daphne.exe"
$CELERY    = "C:\Users\hp123\AppData\Local\Python\pythoncore-3.14-64\Scripts\celery.exe"
$NGROK     = "C:\Users\hp123\Downloads\ngrok-v3-stable-windows-amd64\ngrok.exe"
$LIVEKIT   = ".\livekit-bin\livekit-server.exe"
$NGROK_API = "http://localhost:4040/api/tunnels"
$PROJECT   = $PSScriptRoot

# SSL cert paths — use relative paths to avoid Windows drive letter
# being parsed as a Twisted endpoint argument (C: looks like certKey=C)
$CERT = "ssl/cert.pem"
$KEY  = "ssl/key.pem"

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
Write-Host "  |           E D U M I   S T A R T U P            |" -ForegroundColor Cyan
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

foreach ($port in @(80, 8000, 8001, 8443)) {
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
    Write-Fail "Redis not found.  Run:  winget install Redis.Redis"
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
Write-Step 2 8 "LiveKit SFU  (WebRTC  :7880)"

if (-not (Test-Path $LIVEKIT)) {
    Write-Fail "livekit-server.exe not found"
} else {
    Start-Process -FilePath $LIVEKIT -ArgumentList "--config", "livekit.yaml" -WindowStyle Hidden
    Start-Sleep -Seconds 2
    if (Wait-Port 7880 10) {
        Write-OK "LiveKit running  :7880"
    } else {
        Write-Warn "LiveKit may still be starting..."
    }
}

# =============================================================================
#  STEP 3 -- ngrok tunnel
# =============================================================================
Write-Step 3 8 "ngrok  (public HTTPS tunnel -> :8443)"

# Point ngrok at the HTTPS port so the tunnel is end-to-end secure
$ngrokLines = @(
    'version: "3"',
    'agent:',
    '  authtoken: 3Cyj0XsReXGd9C2Nww5Xr03iexV_2CtxYGFbUapetBGZLC2XE',
    'tunnels:',
    '  django:',
    '    proto: http',
    '    addr: 8000',
    '    inspect: false',
    '    request_header:',
    '      add:',
    '        - "ngrok-skip-browser-warning: true"',
    '  livekit:',
    '    proto: http',
    '    addr: 7880',
    '    inspect: false'
)
$ngrokLines | Set-Content -Path "ngrok.yml" -Encoding UTF8

$ngrokUrl = ""
$livekitNgrokUrl = ""
if (-not (Test-Path $NGROK)) {
    Write-Fail "ngrok not found"
    $ngrokUrl = "https://10.7.11.141:8443"
} else {
    Start-Process -FilePath $NGROK -ArgumentList "start", "django", "livekit", "--config", "ngrok.yml" -WindowStyle Hidden
    Write-Host "         Waiting for ngrok tunnels..." -ForegroundColor Gray

    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 2
        try {
            $tunnels = (Invoke-RestMethod $NGROK_API -TimeoutSec 3).tunnels
            foreach ($t in $tunnels) {
                if ($t.public_url -like "https://*" -and $t.name -eq "django") {
                    $ngrokUrl = $t.public_url
                }
                if ($t.public_url -like "https://*" -and $t.name -eq "livekit") {
                    $livekitNgrokUrl = $t.public_url
                }
            }
            if ($ngrokUrl -ne "" -and $livekitNgrokUrl -ne "") { break }
        } catch {}
    }

    if ($ngrokUrl -eq "") {
        Write-Warn "ngrok tunnel not found -- using LAN HTTPS"
        $ngrokUrl = "https://10.7.11.141:8443"
    } else {
        Write-OK "ngrok app tunnel:     $ngrokUrl"
    }
    if ($livekitNgrokUrl -ne "") {
        Write-OK "ngrok livekit tunnel: $livekitNgrokUrl"
    } else {
        Write-Warn "LiveKit ngrok tunnel not found -- will use proxy fallback"
        $livekitNgrokUrl = ""
    }
}

$livekitProxyUrl = ($ngrokUrl -replace "^https://", "wss://") + "/livekit-proxy"

# If we have a direct LiveKit ngrok tunnel, use it — no proxy needed
if ($livekitNgrokUrl -ne "") {
    $livekitWsUrl = $livekitNgrokUrl -replace "^https://", "wss://"
} else {
    # Fall back to proxy through Django
    $livekitWsUrl = $livekitProxyUrl
}

# =============================================================================
#  STEP 4 -- Write .env
# =============================================================================
Write-Step 4 8 "Writing .env"

$serverIp = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.*" } |
    Select-Object -First 1).IPAddress

$envLines = @(
    "SECRET_KEY=django-insecure-@j!l-9t=qs!b&lkynb=zq`$-h3f9d(_nm!hvctk`$9ij()0kaja%",
    "DEBUG=True",
    "ALLOWED_HOSTS=*",
    "REDIS_URL=redis://localhost:6379/0",
    "CAMERA_SERVICE_URL=http://localhost:8001",
    "LIVEKIT_URL=$livekitWsUrl",
    "LIVEKIT_API_KEY=devkey",
    "LIVEKIT_API_SECRET=devsecret_must_be_32_characters_long_1234",
    "SERVER_IP=$serverIp"
)
$envLines | Set-Content -Path ".env" -Encoding UTF8
Write-OK ".env written  (LiveKit -> $livekitWsUrl)"

# Open firewall for LiveKit WebRTC ports
$fwRules = @(
    @{ Name="Edumi-LiveKit-7880"; Port=7880; Proto="TCP" },
    @{ Name="Edumi-LiveKit-7881"; Port=7881; Proto="TCP" },
    @{ Name="Edumi-LiveKit-7882"; Port=7882; Proto="UDP" },
    @{ Name="Edumi-HTTPS-8443";   Port=8443; Proto="TCP" },
    @{ Name="Edumi-HTTP-8000";    Port=8000; Proto="TCP" }
)
foreach ($rule in $fwRules) {
    $exists = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if (-not $exists) {
        New-NetFirewallRule -DisplayName $rule.Name `
            -Direction Inbound -Protocol $rule.Proto `
            -LocalPort $rule.Port -Action Allow `
            -ErrorAction SilentlyContinue | Out-Null
        Write-OK "Firewall: opened $($rule.Proto) :$($rule.Port)"
    }
}

# =============================================================================
#  STEP 5 -- Database migrations + collectstatic
# =============================================================================
Write-Step 5 8 "Database migrations + static files"

Write-Host "         Running migrations..." -ForegroundColor Gray
$migrateResult = & $PYTHON manage.py migrate --run-syncdb 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-OK "Migrations applied"
} else {
    Write-Warn "Migration issue: $($migrateResult | Select-Object -Last 1)"
}

Write-Host "         Collecting static files..." -ForegroundColor Gray
$staticResult = & $PYTHON manage.py collectstatic --noinput 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-OK "Static files collected"
} else {
    Write-Warn "collectstatic: $($staticResult | Select-Object -Last 1)"
}

# =============================================================================
#  STEP 6 -- Camera Service
# =============================================================================
Write-Step 6 8 "Camera Service  (:8001)"

Kill-Port 8001
Start-Sleep -Milliseconds 500

Start-Process -FilePath $PYTHON `
    -ArgumentList "camera_service\manage.py", "runserver", "0.0.0.0:8001", "--noreload" `
    -WindowStyle Hidden

if (Wait-Port 8001 25) {
    Write-OK "Camera service running  :8001"
} else {
    Write-Warn "Camera service slow to start"
}

# =============================================================================
#  STEP 7 -- Celery Worker
# =============================================================================
Write-Step 7 8 "Celery worker"

Start-Process -FilePath $CELERY `
    -ArgumentList "-A", "school_project", "worker", "-l", "warning", "-P", "solo", "--without-heartbeat" `
    -WindowStyle Hidden
Start-Sleep -Seconds 2
Write-OK "Celery worker started"

# =============================================================================
#  STEP 8 -- Daphne ASGI  (HTTP :8000 + HTTPS :8443)
# =============================================================================
Write-Step 8 8 "Daphne ASGI  (HTTP :8000 + HTTPS :8443)"

Write-Host ""
Write-Host "  +================================================================+" -ForegroundColor Green
Write-Host "  |  Edumi is RUNNING                                              |" -ForegroundColor Green
Write-Host "  +================================================================+" -ForegroundColor Green
Write-Host "  |  LAN HTTPS  ->  https://${serverIp}:8443  (use this for meetings) |" -ForegroundColor White
Write-Host "  |  LAN HTTP   ->  http://${serverIp}:8000                           |" -ForegroundColor Gray
Write-Host "  |  Public     ->  $ngrokUrl" -ForegroundColor White
Write-Host "  +----------------------------------------------------------------+" -ForegroundColor Green
Write-Host "  |  LiveKit    ->  $livekitWsUrl" -ForegroundColor Cyan
Write-Host "  +----------------------------------------------------------------+" -ForegroundColor Green
Write-Host "  |  IMPORTANT: Open https://${serverIp}:8443 in browser,            |" -ForegroundColor Yellow
Write-Host "  |  click 'Advanced' -> 'Proceed' to accept the self-signed cert.  |" -ForegroundColor Yellow
Write-Host "  +----------------------------------------------------------------+" -ForegroundColor Green
Write-Host "  |  Redis      :6379   LiveKit  :7880   Camera :8001              |" -ForegroundColor Gray
Write-Host "  |  Press Ctrl+C to stop everything                               |" -ForegroundColor Gray
Write-Host "  +================================================================+" -ForegroundColor Green
Write-Host ""

# SSL endpoint string for Daphne/Twisted
$sslEndpoint = "ssl:8443:privateKey=${KEY}:certKey=${CERT}"

try {
    & $DAPHNE `
        -b 0.0.0.0 -p 8000 `
        -e $sslEndpoint `
        --proxy-headers `
        -v 0 `
        school_project.asgi:application
} finally {
    Write-Host ""
    Write-Host "  Stopping all services..." -ForegroundColor Red

    Kill-Port 8001
    Kill-Port 8443

    Get-Process | Where-Object { $_.Name -like "*celery*"  } | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process | Where-Object { $_.Name -like "*ngrok*"   } | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process | Where-Object { $_.Name -like "*livekit*" } | Stop-Process -Force -ErrorAction SilentlyContinue

    Write-Host "  All services stopped." -ForegroundColor Gray
    Write-Host ""
}
