@echo off
echo ========================================
echo Adding Windows Firewall Rules
echo ========================================
echo.
echo This will allow Python to accept connections on ports 8000 and 8001
echo You may need to run this as Administrator
echo.
pause

netsh advfirewall firewall add rule name="DigiRoom Main App (Port 8000)" dir=in action=allow protocol=TCP localport=8000
netsh advfirewall firewall add rule name="DigiRoom Camera Service (Port 8001)" dir=in action=allow protocol=TCP localport=8001

echo.
echo ========================================
echo Firewall rules added!
echo ========================================
echo.
echo If you see errors above, try:
echo 1. Right-click this file
echo 2. Select "Run as administrator"
echo.
pause
