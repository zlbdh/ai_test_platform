$backendPort = "8020"

$env:VITE_API_URL = "http://127.0.0.1:$backendPort"
$env:VITE_WS_URL = "ws://127.0.0.1:$backendPort"
$env:VITE_PROXY_TARGET = "http://127.0.0.1:$backendPort"
$env:VITE_PROXY_WS_TARGET = "ws://127.0.0.1:$backendPort"

Set-Location "$PSScriptRoot\frontend"
npm run dev -- --host 127.0.0.1 --port 8010 --strictPort
