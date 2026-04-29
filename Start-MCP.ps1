# AI Test Platform MCP Server 启动脚本
Write-Host "🚀 启动 AI Test Platform MCP Server..." -ForegroundColor Cyan

$backendDir = Join-Path $PSScriptRoot "backend"
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "⚠️ 未找到虚拟环境，使用系统 Python" -ForegroundColor Yellow
    $venvPython = "python"
}

Write-Host "📋 MCP Server 配置:" -ForegroundColor Gray
Write-Host "   Python: $venvPython"
Write-Host "   Module: mcp.server"
Write-Host ""

Set-Location $backendDir
& $venvPython -m mcp.server
