@echo off
REM Edumi2 Production Startup Script for Windows
REM Usage: start_production.bat [start|stop|restart|status]

setlocal enabledelayedexpansion

set "APP_NAME=edumi2"
set "PIDFILE=gunicorn.pid"
set "LOG_DIR=logs"

REM Ensure log directory exists
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Function to check if server is running
:is_running
if exist "%PIDFILE%" (
    set /p PID=<"%PIDFILE%"
    tasklist /FI "PID eq !PID!" 2>nul | findstr "!PID!" >nul
    if !errorlevel! == 0 (
        exit /b 0
    )
)
exit /b 1

REM Function to start the server
:start_server
call :is_running
if !errorlevel! == 0 (
    echo [WARNING] %APP_NAME% is already running
    exit /b 1
)

echo [INFO] Starting %APP_NAME% in production mode...

REM Set production environment variables
set DEBUG=False
set PYTHONUNBUFFERED=1

REM Optional: Set these for your environment
REM set SECRET_KEY=your-production-secret-key
REM set REDIS_URL=redis://localhost:6379/0
REM set GUNICORN_WORKERS=4

REM Collect static files
echo [INFO] Collecting static files...
python manage.py collectstatic --noinput --clear 2>nul || (
    echo [WARNING] Static collection had issues, continuing...
)

REM Run database migrations
echo [INFO] Running database migrations...
python manage.py migrate --noinput

REM Start Gunicorn
echo [INFO] Starting Gunicorn server...
start /B gunicorn school_project.asgi:application --config gunicorn.conf.py

timeout /t 3 /nobreak >nul

call :is_running
if !errorlevel! == 0 (
    echo [SUCCESS] %APP_NAME% started successfully
    echo [INFO] Server running at: http://localhost:8000
) else (
    echo [ERROR] Failed to start %APP_NAME%
    exit /b 1
)
exit /b 0

REM Function to stop the server
:stop_server
call :is_running
if !errorlevel! == 1 (
    echo [WARNING] %APP_NAME% is not running
    exit /b 1
)

echo [INFO] Stopping %APP_NAME%...

set /p PID=<"%PIDFILE%"
taskkill /PID !PID! /T /F >nul 2>&1

if exist "%PIDFILE%" del "%PIDFILE%"
echo [SUCCESS] %APP_NAME% stopped
exit /b 0

REM Function to restart the server
:restart_server
echo [INFO] Restarting %APP_NAME%...
call :stop_server
timeout /t 2 /nobreak >nul
call :start_server
exit /b 0

REM Function to check status
:show_status
call :is_running
if !errorlevel! == 0 (
    set /p PID=<"%PIDFILE%"
    echo [SUCCESS] %APP_NAME% is running (PID: !PID!)
) else (
    echo [INFO] %APP_NAME% is not running
)
exit /b 0

REM Main script logic
if "%~1"=="" goto :start
if /I "%~1"=="start" goto :start
if /I "%~1"=="stop" goto :stop
if /I "%~1"=="restart" goto :restart
if /I "%~1"=="status" goto :status
echo Usage: %0 [start^|stop^|restart^|status]
exit /b 1

:start
call :start_server
exit /b %errorlevel%

:stop
call :stop_server
exit /b %errorlevel%

:restart
call :restart_server
exit /b %errorlevel%

:status
call :show_status
exit /b 0
