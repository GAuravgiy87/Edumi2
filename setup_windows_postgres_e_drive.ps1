# ==============================================================================
#  EduMi2 — Windows PostgreSQL E: Drive Setup & Remote Access Configurator
# ==============================================================================
#  Run this script on your Windows PC as Administrator.
#  Usage: Right-click → "Run with PowerShell"  OR
#         Start-Process powershell -Verb RunAs -ArgumentList "-File setup_windows_postgres_e_drive.ps1"
# ==============================================================================

# Ensure Administrator Privileges
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]"Administrator")) {
    Write-Host "Elevating privileges to Administrator..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  EduMi2 Windows PostgreSQL (E: Drive) Configurator" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

$EDUMI_DB_DIR = "E:\edumi_postgres_data"
$DB_NAME = "edumi_db"
$DB_USER = "edumi_user"
$DB_PASS = "edumi_secure_pass_123"

# ------------------------------------------------------------------------------
# 1. Verify E: Drive Exists
# ------------------------------------------------------------------------------
if (-not (Test-Path "E:\")) {
    Write-Host "[ERROR] E:\ Drive not found on this system! Please check your disk drives." -ForegroundColor Red
    Pause
    exit 1
}

Write-Host "[✓] E:\ Drive detected." -ForegroundColor Green

# Create Data Directory on E: Drive
if (-not (Test-Path $EDUMI_DB_DIR)) {
    New-Item -ItemType Directory -Path $EDUMI_DB_DIR | Out-Null
    Write-Host "[✓] Created database directory: $EDUMI_DB_DIR" -ForegroundColor Green
} else {
    Write-Host "[✓] Database directory already exists: $EDUMI_DB_DIR" -ForegroundColor Green
}


# ------------------------------------------------------------------------------
# 2. Detect PostgreSQL Installation Path
# ------------------------------------------------------------------------------
$pgPath = $null
$possiblePaths = @(
    "C:\Program Files\PostgreSQL\16\bin",
    "C:\Program Files\PostgreSQL\15\bin",
    "C:\Program Files\PostgreSQL\14\bin",
    "C:\Program Files\PostgreSQL\13\bin"
)

foreach ($path in $possiblePaths) {
    if (Test-Path "$path\postgres.exe") {
        $pgPath = $path
        break
    }
}

if ($null -eq $pgPath) {
    $pgCmd = Get-Command "psql.exe" -ErrorAction SilentlyContinue
    if ($pgCmd) {
        $pgPath = Split-Path $pgCmd.Source
    }
}

if ($null -eq $pgPath) {
    Write-Host "[!] PostgreSQL binaries not detected in standard C:\Program Files\PostgreSQL path." -ForegroundColor Yellow
    Write-Host "    If PostgreSQL is installed via Docker or custom path, ensure port 5432 is open." -ForegroundColor Yellow
} else {
    Write-Host "[✓] PostgreSQL Binaries found at: $pgPath" -ForegroundColor Green
}


# ------------------------------------------------------------------------------
# 3. Configure Windows Firewall Rule for Remote Connection
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "Configuring Windows Firewall to allow remote server access on Port 5432..." -ForegroundColor Cyan

Remove-NetFirewallRule -DisplayName "Edumi-PostgreSQL-5432" -ErrorAction SilentlyContinue

New-NetFirewallRule `
    -DisplayName "Edumi-PostgreSQL-5432" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 5432 `
    -Action Allow `
    -Profile Any `
    -Description "Allow Ubuntu Server to connect to Windows PC PostgreSQL Database on Port 5432" | Out-Null

Write-Host "[✓] Windows Firewall rule applied for Port 5432." -ForegroundColor Green


# ------------------------------------------------------------------------------
# 4. Configure postgresql.conf & pg_hba.conf for Remote Connections
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "Locating PostgreSQL Data Configuration files..." -ForegroundColor Cyan

$dataPaths = @(
    "E:\edumi_postgres_data",
    "C:\Program Files\PostgreSQL\16\data",
    "C:\Program Files\PostgreSQL\15\data",
    "C:\Program Files\PostgreSQL\14\data",
    "C:\ProgramData\PostgreSQL\15\data"
)

$foundDataDir = $null
foreach ($dp in $dataPaths) {
    if (Test-Path "$dp\postgresql.conf") {
        $foundDataDir = $dp
        break
    }
}

if ($foundDataDir) {
    Write-Host "[✓] PostgreSQL Config found in: $foundDataDir" -ForegroundColor Green
    
    # Enable listen_addresses = '*'
    $confFile = "$foundDataDir\postgresql.conf"
    $confContent = Get-Content $confFile
    if ($confContent -notmatch "^listen_addresses\s*=\s*'\*'") {
        Add-Content -Path $confFile -Value "`nlisten_addresses = '*'`n"
        Write-Host "[✓] Enabled listen_addresses = '*' in postgresql.conf" -ForegroundColor Green
    }

    # Enable remote authentication in pg_hba.conf
    $hbaFile = "$foundDataDir\pg_hba.conf"
    $hbaContent = Get-Content $hbaFile
    if ($hbaContent -notmatch "0.0.0.0/0") {
        Add-Content -Path $hbaFile -Value "`nhost    all             all             0.0.0.0/0               scram-sha-256`n"
        Write-Host "[✓] Allowed remote host connections (0.0.0.0/0) in pg_hba.conf" -ForegroundColor Green
    }

    # Restart PostgreSQL Service
    Get-Service -Name "postgresql*" | Restart-Service -ErrorAction SilentlyContinue
    Write-Host "[✓] PostgreSQL Service restarted with remote connection support." -ForegroundColor Green
} else {
    Write-Host "[!] Configuration files not automatically modified. Ensure postgresql.conf has 'listen_addresses = '*'' and pg_hba.conf allows your Ubuntu IP." -ForegroundColor Yellow
}


# ------------------------------------------------------------------------------
# 5. Detect Windows PC LAN IP Address
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  YOUR WINDOWS PC DATABASE SERVER CONNECTION INFO" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$lanIPs = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -ExpandProperty IPAddress

Write-Host ""
Write-Host "  Windows PC LAN IP Address(es):" -ForegroundColor BOLD
foreach ($ip in $lanIPs) {
    Write-Host "  👉 $ip" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Database Name : $DB_NAME" -ForegroundColor Green
Write-Host "  Database User : $DB_USER" -ForegroundColor Green
Write-Host "  Database Pass : $DB_PASS" -ForegroundColor Green
Write-Host "  Data Storage  : $EDUMI_DB_DIR (E: Drive)" -ForegroundColor Green
Write-Host ""
Write-Host "--------------------------------------------------" -ForegroundColor Cyan
Write-Host "  COMMAND TO RUN ON YOUR UBUNTU SERVER:" -ForegroundColor Cyan
Write-Host "--------------------------------------------------" -ForegroundColor Cyan
if ($lanIPs.Count -gt 0) {
    $firstIP = $lanIPs[0]
    Write-Host "  sudo bash deploy_ubuntu_native.sh --db-host $firstIP" -ForegroundColor Yellow
} else {
    Write-Host "  sudo bash deploy_ubuntu_native.sh --db-host <YOUR_WINDOWS_PC_IP>" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
