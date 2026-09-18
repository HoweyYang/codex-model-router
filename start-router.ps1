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

# pythonw has no console, so a busy port or bad config kills the process with
# no visible error. Wait for the socket to actually come up; if it does not,
# point the user at the log file instead of pretending we started fine.
$ok = $false
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Milliseconds 500
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        $ok = $true
        break
    }
}

if ($ok) {
    Write-Host "codex-model-router listening on port $port"
} else {
    Write-Warning "launched but nothing is listening on $port. Check ~/.codex/model-router.log for the startup error."
    exit 1
}
