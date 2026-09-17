# Start codex-model-router in the background if it is not already listening.

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = Join-Path (Join-Path $env:USERPROFILE '.codex') 'model-router.json'

if (-not (Test-Path $configPath)) {
    Write-Error "missing $configPath"
}

$listen = ((Get-Content $configPath -Raw | ConvertFrom-Json).listen) -split ':'
$port = [int]$listen[-1]

if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
    Write-Host "codex-model-router already listening on port $port"
    exit 0
}

$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) { $pythonw = 'pythonw.exe' }

Start-Process -FilePath $pythonw `
    -ArgumentList (Join-Path $root 'router.py') `
    -WindowStyle Hidden

Write-Host "codex-model-router starting on port $port"
