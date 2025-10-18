@echo off
echo Starting Vimeo Video Chatbot Server...
echo.

echo Starting Backend Server (serves both API and Frontend)...
start "Vimeo Chatbot Server" cmd /k "cd /d %~dp0 && venv\Scripts\activate && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

echo Waiting for server to start...
timeout /t 5 /nobreak > nul

echo.
echo ✅ Server is starting up!
echo.
echo 🌐 Chatbot: http://127.0.0.1:8000
echo 📚 API Docs: http://127.0.0.1:8000/docs
echo.
echo Press any key to open the chatbot in your browser...
pause > nul

start http://127.0.0.1:8000
