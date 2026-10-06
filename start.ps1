# ARP System - Start All Services Script
# Starts Backend (FastAPI) and Frontend (Vite) in separate windows

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   ARP System - Starting All Services" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python not found. Please install Python 3.10+" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check Node
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Node.js not found. Please install Node.js 18+" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check DB
$DB_PATH = Join-Path $ROOT "backend\arp.db"
if (Test-Path $DB_PATH) {
    $DB_SIZE = [math]::Round((Get-Item $DB_PATH).Length / 1KB, 1)
    Write-Host "[DB]  arp.db found ($DB_SIZE KB)" -ForegroundColor Green
} else {
    Write-Host "[DB]  arp.db will be created on first backend start" -ForegroundColor Yellow
}

Write-Host ""

# Start Backend
Write-Host "[1/2] Starting Backend (FastAPI + Uvicorn)..." -ForegroundColor Yellow
Write-Host "      URL: http://127.0.0.1:8000" -ForegroundColor Gray
Write-Host "      API Docs: http://127.0.0.1:8000/docs" -ForegroundColor Gray

$backendCmd = "cd '$ROOT\backend'; `$host.UI.RawUI.WindowTitle = 'ARP Backend :8000'; Write-Host ''; Write-Host '=== ARP Backend ===' -ForegroundColor Cyan; Write-Host '  http://127.0.0.1:8000' -ForegroundColor Green; Write-Host '  http://127.0.0.1:8000/docs' -ForegroundColor Yellow; Write-Host ''; python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

Start-Sleep -Seconds 2

# Start Frontend
Write-Host "[2/2] Starting Frontend (Vite + React)..." -ForegroundColor Yellow
Write-Host "      URL: http://localhost:5173" -ForegroundColor Gray

$frontendCmd = "cd '$ROOT\frontend'; `$host.UI.RawUI.WindowTitle = 'ARP Frontend :5173'; Write-Host ''; Write-Host '=== ARP Frontend ===' -ForegroundColor Cyan; Write-Host '  http://localhost:5173' -ForegroundColor Green; Write-Host ''; npm run dev"

Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Start-Sleep -Seconds 4

# Summary
Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  [OK] All services started successfully!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend  --> http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "  Frontend --> http://localhost:5173" -ForegroundColor Cyan
Write-Host "  API Docs --> http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host ""

# Open browser
$answer = Read-Host "Open browser? (y/n) [default: y]"
if ($answer -ne "n" -and $answer -ne "N") {
    Start-Process "http://localhost:5173"
    Write-Host "[OK] Browser opened" -ForegroundColor Green
}

Write-Host ""
Write-Host "This window will close in 5 seconds..." -ForegroundColor Gray
Start-Sleep -Seconds 5
