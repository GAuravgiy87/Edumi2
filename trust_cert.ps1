# =====================================================
# EduMi 2 - Trust SSL Certificate in Windows
# Run this as Administrator to fix "Not Secure"
# =====================================================
param(
    [string]$CertPath = "$PSScriptRoot\certs\edumi-trust-this.crt"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "======================================================"  -ForegroundColor Cyan
Write-Host "   EduMi 2 - Installing SSL Certificate (Windows)"       -ForegroundColor Cyan
Write-Host "======================================================"  -ForegroundColor Cyan
Write-Host ""

# ── Check cert file exists ─────────────────────────────────────────────────────
if (-not (Test-Path $CertPath)) {
    Write-Host "[ERROR] Certificate not found: $CertPath" -ForegroundColor Red
    Write-Host "        Run start_app.sh first to generate the cert." -ForegroundColor Yellow
    exit 1
}

# ── Check admin ────────────────────────────────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$targetStore = "LocalMachine"

if (-not $isAdmin) {
    Write-Host "[INFO] Not running as Administrator. Attempting to elevate..." -ForegroundColor Yellow
    try {
        # Auto-relaunch as admin
        Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -CertPath `"$CertPath`"" -Verb RunAs -Wait -ErrorAction Stop
        exit 0
    } catch {
        Write-Host "[WARNING] Elevation declined or failed. Falling back to installing for the Current User." -ForegroundColor Yellow
        Write-Host "          Note: A Windows Security Warning dialog may pop up to ask for your confirmation." -ForegroundColor Yellow
        $targetStore = "CurrentUser"
    }
}

# ── Remove old EduMi certs ─────────────────────────────────────────────────────
Write-Host "[1/3] Removing old EduMi certificates..." -ForegroundColor Gray
$stores = @(
    [System.Security.Cryptography.X509Certificates.X509Store]::new("Root", "LocalMachine"),
    [System.Security.Cryptography.X509Certificates.X509Store]::new("Root", "CurrentUser")
)
foreach ($store in $stores) {
    try {
        $store.Open("ReadWrite")
        $old = $store.Certificates | Where-Object { $_.Subject -match "edumi" -or $_.Issuer -match "edumi" }
        foreach ($c in $old) {
            $store.Remove($c)
            Write-Host "      Removed: $($c.Thumbprint) ($($c.Subject)) from $($store.Location)" -ForegroundColor DarkYellow
        }
        $store.Close()
    } catch {}
}

# ── Install new cert ───────────────────────────────────────────────────────────
Write-Host "[2/3] Installing new certificate into Trusted Root CA ($targetStore)..." -ForegroundColor Gray
$newCert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($CertPath)

try {
    $rootStore = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", $targetStore)
    $rootStore.Open("ReadWrite")
    $rootStore.Add($newCert)
    $rootStore.Close()
    
    Write-Host "      [OK] Installed to $($targetStore): $($newCert.Thumbprint)" -ForegroundColor Green
    Write-Host "      [OK] Subject  : $($newCert.Subject)"   -ForegroundColor Green
    Write-Host "      [OK] Expires  : $($newCert.NotAfter)"  -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to install certificate: $_" -ForegroundColor Red
    exit 1
}

# ── Flush DNS ──────────────────────────────────────────────────────────────────
Write-Host "[3/3] Flushing DNS cache..." -ForegroundColor Gray
ipconfig /flushdns | Out-Null

# ── Clear Chrome SSL cache ────────────────────────────────────────────────────
$chromeSslFiles = @(
    "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\TransportSecurity",
    "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Certificate Revocation Lists"
)
foreach ($f in $chromeSslFiles) {
    if (Test-Path $f) {
        Remove-Item $f -Force -ErrorAction SilentlyContinue
        Write-Host "      [OK] Cleared Chrome SSL cache: $(Split-Path $f -Leaf)" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "======================================================"  -ForegroundColor Green
Write-Host "  Certificate installed successfully!"                    -ForegroundColor Green
Write-Host ""
Write-Host "  IMPORTANT: Close ALL Chrome windows and reopen."       -ForegroundColor Yellow
Write-Host "  Chrome caches cert trust - a full restart is needed."  -ForegroundColor Yellow
Write-Host ""
Write-Host "  Then visit: https://edumi.ac.in:8002"                  -ForegroundColor Cyan
Write-Host "======================================================"  -ForegroundColor Green
Write-Host ""
