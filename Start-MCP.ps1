# AI Test Platform MCP Server startup script
Write-Host "🚀 Starting AI Test Platform MCP Server..." -ForegroundColor Cyan

$backendDir = Join-Path $PSScriptRoot "backend"
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "⚠️ Virtual environment not found; using system Python" -ForegroundColor Yellow
    $venvPython = "python"
}

Write-Host "📋 MCP Server configuration:" -ForegroundColor Gray
Write-Host "   Python: $venvPython"
Write-Host "   Module: mcp.server"
Write-Host ""

Set-Location $backendDir
& $venvPython -m mcp.server
