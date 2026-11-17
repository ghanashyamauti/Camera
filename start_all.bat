@echo off
title Camera Thing Detector Launcher
echo ====================================================
echo Starting Camera Thing Detector (Backend & Frontend)
echo ====================================================
echo.
start "Camera Backend (FastAPI)" cmd /k "run_backend.bat"
timeout /t 3 /nobreak >nul
start "Camera Frontend (React)" cmd /k "run_frontend.bat"
echo.
echo Both servers are starting up:
echo  - Backend API: http://localhost:8000
echo  - Frontend UI:  http://localhost:5173
echo.
echo Opening browser in 3 seconds...
timeout /t 3 /nobreak >nul
start http://localhost:5173
