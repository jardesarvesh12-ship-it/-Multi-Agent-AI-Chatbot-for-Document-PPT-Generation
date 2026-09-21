@echo off
title Multi-Agent AI Chatbot - Backend
cd /d "%~dp0"
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo Starting FastAPI Backend on http://127.0.0.1:8000 ...
python -m uvicorn backend.main:app --reload --port 8000
pause
