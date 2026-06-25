# =====================================================
# EduMi 2 - Trust Self-Signed SSL Certificate
# Installs certs/edumi.crt into Windows Trusted Root CA
# so browsers stop showing the "Not Secure" warning.
#
# Run as Administrator (or this script will self-elevate).
# =====================================================

$BASE_DIR  = Split-Path -Parent $PSScriptRoot
$CERT_FILE = Join-Path $BASE_DIR "certs\edumi.crt"
$CERT_NAME = "EduMi Academic - Local Dev"

# ── Check if already trusted ──────────────────────────────────────────
$existing = Get-ChildItem -Path "Cert:\LocalMachine\Root" |
    Where-Object { $_.Subject -match "edumi\.ac\.in" }

if ($existing) {
    Write-Host "[OK] Certificate is already trusted in this machine." -ForegroundColor Green
    Write-Host "     Subject : $($existing.Subject)" -ForegroundColor Gray
    Write-Host "     Thumbprint: $($existing.Thumbprint)" -ForegroundColor Gray
    exit 0
}

# ── Self-elevate if not running as admin ──────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Requesting administrator privileges (UAC prompt)..." -ForegroundColor Yellow
    Start-Process powershell `
        -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`"" `
        -Verb RunAs `
        -Wait
    exit
}

# ── Install the certificate ───────────────────────────────────────────
Write-Host ""
Write-Host "Installing EduMi SSL certificate as Trusted Root CA..." -ForegroundColor Cyan
Write-Host "  File: $CERT_FILE" -ForegroundColor Gray
Write-Host ""

if (-not (Test-Path $CERT_FILE)) {
    Write-Host "[ERROR] Certificate file not found: $CERT_FILE" -ForegroundColor Red
    Write-Host "        Run: python scripts\generate_ssl_cert.py" -ForegroundColor Yellow
    exit 1
}

try {
    # Import into LocalMachine\Root (trusted for all users on this PC)
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($CERT_FILE)
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store(
        [System.Security.Cryptography.X509Certificates.StoreName]::Root,
        [System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine
    )
    $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    $store.Add($cert)
    $store.Close()

    Write-Host "[OK] Certificate installed successfully!" -ForegroundColor Green
    Write-Host "     Subject   : $($cert.Subject)" -ForegroundColor Gray
    Write-Host "     Thumbprint: $($cert.Thumbprint)" -ForegroundColor Gray
    Write-Host "     Valid until: $($cert.NotAfter)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host " DONE! Restart Chrome and go to https://edumi.ac.in:8002" -ForegroundColor Green
    Write-Host " The padlock should now show as SECURE (green/locked)."  -ForegroundColor Green
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host " If Chrome still warns, open a new tab and go to:"      -ForegroundColor Yellow
    Write-Host "   chrome://restart"                                      -ForegroundColor Yellow
    Write-Host " or close ALL Chrome windows and reopen."                -ForegroundColor Yellow
}
catch {
    Write-Host "[ERROR] Failed to install certificate: $_" -ForegroundColor Red
    exit 1
}
