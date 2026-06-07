@echo off
echo ===================================================
echo             MAIL SARTHI Startup Script
echo ===================================================
echo.

echo Starting Flask Backend API (Port 5000)...
start "MAIL SARTHI Backend API" cmd /k "cd backend && python app.py"

echo.
echo Starting Static Frontend Client Server (Port 8000)...
start "MAIL SARTHI Frontend Client" cmd /k "python -m http.server 8000 --directory frontend"

echo.
echo ===================================================
echo Servers are launching:
echo - Backend API: http://127.0.0.1:5000/api
echo - Frontend: http://127.0.0.1:8000
echo ===================================================
echo.
pause
