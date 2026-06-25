@echo off
:: EduMi 2 - Quick HTTPS-only launcher (no Redis/Celery/LiveKit)
:: Use this for fast dev restarts when other services are already running.
:: For a full system start, use start_app.bat instead.

cd /d "%~dp0"
echo.
echo Starting EduMi HTTPS server...
echo   URL: https://127.0.0.1:8002
echo   URL: https://localhost:8002
echo.
echo NOTE: Browser will show a certificate warning for the self-signed cert.
echo       Click "Advanced" then "Proceed" to continue.
echo.
venv\Scripts\python.exe run_ssl_server.py
pause
