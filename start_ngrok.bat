@echo off
echo ========================================
echo Starting ngrok for EduMi
echo ========================================
echo.

REM Check if ngrok exists
if not exist "ngrok.exe" (
    echo ERROR: ngrok.exe not found!
    echo.
    echo Please download ngrok:
    echo 1. Go to https://ngrok.com/download
    echo 2. Download ngrok for Windows
    echo 3. Extract ngrok.exe to this folder
    echo.
    pause
    exit /b 1
)

echo Checking if Django is running on port 8000...
netstat -ano | findstr :8000 >nul
if errorlevel 1 (
    echo.
    echo WARNING: Django doesn't seem to be running on port 8000
    echo.
    echo Please start Django first:
    echo    python manage.py runserver 0.0.0.0:8000
    echo.
    echo Then run this script again.
    echo.
    pause
    exit /b 1
)

echo.
echo Django is running! Starting ngrok...
echo.
echo ========================================
echo IMPORTANT:
echo ========================================
echo 1. Copy the HTTPS URL shown below
echo    (looks like: https://abc123.ngrok.io)
echo.
echo 2. Use that URL to access EduMi
echo.
echo 3. Camera and mic will work!
echo.
echo 4. Keep this window open
echo.
echo Press Ctrl+C to stop ngrok
echo ========================================
echo.

ngrok http 8000

pause
