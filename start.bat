@echo off
setlocal

cd /d "%~dp0"

echo ── Virtual environment ───────────────────────────────────────────────────────
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating venv...
call venv\Scripts\activate.bat

python --version

echo ── Python dependencies ───────────────────────────────────────────────────────
echo Installing Python requirements...
pip install -r requirements.txt --quiet

echo ── Node.js / SFU dependencies ────────────────────────────────────────────────
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js not found. Install it first.
    exit /b 1
)

echo Installing SFU dependencies...
cd sfu
call npm install --omit=dev --silent
cd ..

echo ── Django setup ──────────────────────────────────────────────────────────────
echo Running migrations...
python manage.py migrate --run-syncdb

if not exist logs mkdir logs

echo ── Start Redis ───────────────────────────────────────────────────────────────
redis-server --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Starting Redis server...
    start /B "Redis" redis-server > logs\redis.log 2>&1
) else (
    echo WARNING: redis-server not found. Assuming Redis is running externally.
)

echo ── Start Celery ──────────────────────────────────────────────────────────────
celery --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Starting Celery worker...
    REM Using -P solo for Windows compatibility
    start /B "Celery Worker" celery -A school_project worker --loglevel=info -P solo > logs\celery.log 2>&1
    
    echo Starting Celery beat...
    start /B "Celery Beat" celery -A school_project beat --loglevel=info > logs\celery_beat.log 2>&1
) else (
    echo WARNING: Celery not found. Worker will not start.
)

echo ── Start SFU ─────────────────────────────────────────────────────────────────
echo Starting SFU media server...
cd sfu
start /B "SFU" node src\server.js > ..\logs\sfu.log 2>&1
cd ..

timeout /t 2 /nobreak >nul

echo ── Start Django ──────────────────────────────────────────────────────────────
echo Starting Django at http://127.0.0.1:8000
echo.
echo Press Ctrl+C to stop the server.
python manage.py runserver 0.0.0.0:8000

echo.
echo Stopping background tasks...
taskkill /F /IM node.exe >nul 2>&1
taskkill /F /IM celery.exe >nul 2>&1
taskkill /F /IM redis-server.exe >nul 2>&1
