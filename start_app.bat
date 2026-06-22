@echo off
:: EduMi 2 - Double-click to start all services (HTTPS)
:: Bypasses PowerShell execution policy automatically
powershell -ExecutionPolicy Bypass -File "%~dp0start_app.ps1"
pause
