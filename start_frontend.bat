@echo off
title Multi-Agent AI Chatbot - Frontend
cd /d "%~dp0frontend"
echo Starting Vite Frontend on http://localhost:5173 ...
call npm run dev
pause
