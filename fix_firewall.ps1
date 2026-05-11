# Edumi Firewall Fixer
# Run this script as Administrator to open necessary ports

function Add-FirewallRule($name, $port, $protocol) {
    Write-Host "Checking rule for $name ($port/$protocol)..." -ForegroundColor Cyan
    $existing = Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "  Rule already exists. Updating..." -ForegroundColor Yellow
        Set-NetFirewallRule -DisplayName $name -LocalPort $port -Protocol $protocol -Action Allow -Enabled True
    } else {
        Write-Host "  Creating new rule..." -ForegroundColor Green
        New-NetFirewallRule -DisplayName $name -Direction Inbound -LocalPort $port -Protocol $protocol -Action Allow -Enabled True
    }
}

# Check for Admin rights
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script MUST be run as Administrator!" -ForegroundColor Red
    Write-Host "Please right-click PowerShell and select 'Run as Administrator'." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host "       E D U M I   F I R E W A L L   F I X" -ForegroundColor Cyan
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Django Web Server (ASGI)
Add-FirewallRule "Edumi-Django-Web" 8000 "TCP"

# 2. Edumi Camera Service
Add-FirewallRule "Edumi-Camera-Service" 8001 "TCP"

# 3. LiveKit Signaling
Add-FirewallRule "LiveKit-Signaling" 7880 "TCP"

# 4. LiveKit WebRTC (Media) - Very Important!
Add-FirewallRule "LiveKit-WebRTC-UDP" "7881,7882" "UDP"
Add-FirewallRule "LiveKit-WebRTC-TCP" "7881,7882" "TCP"

# 5. Redis (Internal but good to have)
Add-FirewallRule "Edumi-Redis" 6379 "TCP"

Write-Host ""
Write-Host "  SUCCESS: All Edumi ports are now open in your firewall." -ForegroundColor Green
Write-Host "  You can now close this window." -ForegroundColor White
Write-Host ""
pause
