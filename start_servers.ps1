# PowerShell script to start the chatbot server
Write-Host "🚀 Starting Vimeo Video Chatbot Server..." -ForegroundColor Green
Write-Host ""

# Start Backend Server (serves both API and Frontend)
Write-Host "🔧 Starting Chatbot Server (API + Frontend)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; .\venv\Scripts\Activate.ps1; python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

# Wait for server to start
Write-Host "⏳ Waiting for server to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "✅ Server is starting up!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Chatbot: http://127.0.0.1:8000" -ForegroundColor Blue
Write-Host "📚 API Docs: http://127.0.0.1:8000/docs" -ForegroundColor Blue
Write-Host ""

# Open chatbot in browser
Write-Host "🌐 Opening chatbot in browser..." -ForegroundColor Green
Start-Process "http://127.0.0.1:8000"
