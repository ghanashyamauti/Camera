@echo off
title Camera Thing Detector - Backend
cd /d "%~dp0backend"
echo [Backend] Activating virtual environment...
call .\venv\Scripts\activate.bat
echo [Backend] Starting FastAPI Server on http://localhost:8000...
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
