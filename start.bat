@echo off
chcp 65001 >nul
title ARP System - Start All Services

echo.
echo ======================================================
echo    ARP System - Starting All Services
echo ======================================================
echo.

:: Start Backend in new window (green background)
echo [1/2] Starting Backend (FastAPI + Uvicorn)...
start "ARP Backend :8000" cmd /k "color 0A && cd /d %~dp0backend && echo. && echo === ARP Backend === && echo   http://127.0.0.1:8000 && echo   http://127.0.0.1:8000/docs && echo. && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

:: Wait 2 seconds before starting frontend
timeout /t 2 /nobreak >nul

:: Start Frontend in new window (blue background)
echo [2/2] Starting Frontend (Vite + React)...
start "ARP Frontend :5173" cmd /k "color 0B && cd /d %~dp0frontend && echo. && echo === ARP Frontend === && echo   http://localhost:5173 && echo. && npm run dev"

:: Wait for services to initialize
timeout /t 5 /nobreak >nul

echo.
echo ======================================================
echo   [OK] All services started!
echo ======================================================
echo.
echo   Backend  --^> http://127.0.0.1:8000
echo   Frontend --^> http://localhost:5173
echo   API Docs --^> http://127.0.0.1:8000/docs
echo.

:: Open browser automatically
start "" "http://localhost:5173"
echo   [OK] Browser opened

echo.
echo This window will close in 5 seconds...
timeout /t 5 /nobreak >nul
exit
