# AI Test Platform - Backend Startup Script
# Features: Port conflict detection, clean startup

$ErrorActionPreference = "Stop"
$PORT = 8020
$BACKEND_DIR = "$PSScriptRoot\backend"

Write-Host "`n[AI Test Platform] Starting Backend..." -ForegroundColor Cyan
Write-Host "  Port: $PORT | Dir: $BACKEND_DIR" -ForegroundColor DarkGray

# Check if port is already in use
$existing = Get-NetTCPConnection -LocalPort $PORT -ErrorAction SilentlyContinue | Where-Object State -eq 'Listen'
if ($existing) {
    $pid = $existing.OwningProcess | Select-Object -First 1
    Write-Host "`n[ERROR] Port $PORT is already in use by PID $pid" -ForegroundColor Red
    Write-Host "  To kill the existing process: Stop-Process -Id $pid -Force" -ForegroundColor Yellow
    Write-Host "  Or use a different port." -ForegroundColor Yellow
    exit 1
}

# Navigate and start
Set-Location $BACKEND_DIR

# Activate venv if exists
$venvPath = "$PSScriptRoot\.venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    . $venvPath
    Write-Host "  Virtual environment activated." -ForegroundColor DarkGray
}

if (-not $env:DEV_AUTH_BYPASS) {
    $env:DEV_AUTH_BYPASS = "true"
    Write-Host "  DEV_AUTH_BYPASS enabled for local development." -ForegroundColor DarkGray
}

Write-Host "`n[OK] Launching uvicorn on port $PORT..." -ForegroundColor Green
uvicorn main:app --host 0.0.0.0 --port $PORT --reload
