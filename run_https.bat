@echo off
echo ========================================
echo Starting Django Server with HTTPS
echo ========================================
echo.

REM Check if django-extensions is installed
python -c "import django_extensions" 2>nul
if errorlevel 1 (
    echo Installing required packages...
    pip install django-extensions werkzeug pyOpenSSL
    echo.
)

echo Starting server on https://0.0.0.0:8000
echo.
echo Access from:
echo - This computer: https://localhost:8000
echo - Other devices: https://YOUR_IP:8000
echo.
echo NOTE: You will see a security warning in the browser.
echo Click "Advanced" and "Proceed anyway" to continue.
echo.
echo Press Ctrl+C to stop the server
echo.

python manage.py runserver_plus --cert-file cert 0.0.0.0:8000

pause
