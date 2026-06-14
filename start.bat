@echo off
echo ===================================================
echo             MAIL SARTHI Startup Script
echo ===================================================
echo.

echo Starting Flask Server (Port 5000)...
start "MAIL SARTHI Server" cmd /k "cd backend && python app.py"

echo.
echo ===================================================
echo Server is launching:
echo - Access MAIL SARTHI at: http://127.0.0.1:5000
echo ===================================================
echo.
pause
