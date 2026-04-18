@echo off
title WinEmpire - AI Content Empire Launcher
cd /d "%~dp0"

echo.
echo  ========================================
echo   WinEmpire - AI Content Empire
echo  ========================================
echo   Role     : Shadow (EMPIRE_ROLE=shadow)
echo   Backend  :8800  (LAN + Tailscale)
echo   Frontend :3000  (local dev)
echo   ComfyUI  :8188  (local only)
echo  ----------------------------------------
echo   Quick Connect to Mac:
echo     Tailscale : http://100.119.54.18:8800
echo     LAN       : http://10.0.1.10:8800
echo  ========================================
echo.

:: Kill stale processes on ports 8800 and 3000
echo Clearing stale processes on ports 8800 and 3000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8800 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
echo Ports cleared.
echo.

:: Start ComfyUI Desktop
echo Starting ComfyUI Desktop...
start "" "C:\Program Files\ComfyUI\ComfyUI.exe"
timeout /t 3 /nobreak >nul

:: Start Backend (FastAPI on 0.0.0.0:8800 — accessible via Tailscale + LAN)
echo Starting Backend (FastAPI :8800, role=shadow)...
start "WinEmpire - Backend :8800" cmd /k "cd /d "%~dp0" && .venv\Scripts\activate.bat && set EMPIRE_ROLE=shadow && set COMFY_PORT=8188 && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8800 --reload"

timeout /t 2 /nobreak >nul

:: Start Frontend (Next.js on localhost:3000)
echo Starting Frontend (Next.js :3000)...
start "WinEmpire - Frontend :3000" cmd /k "cd /d "%~dp0frontend" && set NEXT_PUBLIC_API_URL=http://localhost:8800 && npm run dev"

echo.
echo Waiting for services to warm up...
timeout /t 8 /nobreak >nul

:: Open browser
start http://localhost:3000

echo.
echo  WinEmpire is running!
echo   Local           : http://localhost:3000
echo   Mac (LAN)       : http://10.0.1.10:8800
echo   Mac (Tailscale) : http://100.119.54.18:8800
echo.
echo  Close this window anytime - services run independently.
pause
