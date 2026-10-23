# ensure-router.ps1 - Idempotent watchdog: start codex-model-router only if it
# is not already listening. Safe to run on a schedule; it never starts a second
# copy and exits quietly when the router is up.
$ErrorActionPreference = 'SilentlyContinue'

$root       = Split-Path -Parent $MyInvocation.MyCommand.Path
$routerPy   = Join-Path $root 'router.py'
$configPath = Join-Path (Join-Path $env:USERPROFILE '.codex') 'model-router.json'

# Read the listen port from model-router.json; default 8765.
$port = 8765
if (Test-Path $configPath) {
    try {
        $cfg = Get-Content $configPath -Raw | ConvertFrom-Json
        if ($cfg.listen) { $port = [int]($cfg.listen.ToString().Split(':')[-1]) }
    } catch { }
}

# Already listening -> nothing to do.
if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
    exit 0
}

if (-not (Test-Path $routerPy)) { exit 1 }

# Pick a stable pythonw.exe (hidden, no console). Prefer the fixed Python311
# used by mcp-autostart; fall back to PATH.
$pythonw = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\pythonw.exe'
if (-not (Test-Path $pythonw)) {
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($cmd) { $pythonw = $cmd.Source } else { exit 1 }
}

Start-Process -FilePath $pythonw -ArgumentList $routerPy -WindowStyle Hidden

# Wait briefly for the socket to come up.
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Milliseconds 500
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) { break }
}
exit 0
