# Wire codex-model-router to Codex's lifecycle: register mcp-autostart.py as a
# no-tool MCP server. Codex launches MCP servers when it starts, so the router
# comes up with Codex and never needs a logon task.

$ErrorActionPreference = 'Stop'

$root       = Split-Path -Parent $MyInvocation.MyCommand.Path
$hook       = Join-Path $root 'mcp-autostart.py'
$configPath = Join-Path (Join-Path $env:USERPROFILE '.codex') 'config.toml'

if (-not (Test-Path $hook))       { Write-Error "missing $hook" }
if (-not (Test-Path $configPath)) { Write-Error "missing $configPath" }

# Pick a stable python.exe for the stdio side of the MCP connection. Skip
# AI-sandbox runtimes whose per-update hash path disappears on the next launch.
function Find-PythonExe {
    $candidates = @(
        (Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue | ForEach-Object FullName)
        (Get-ChildItem "C:\Program Files\Python*\python.exe" -ErrorAction SilentlyContinue | ForEach-Object FullName)
        (where.exe python 2>$null)
    )
    $seen = @{}
    foreach ($p in $candidates) {
        if (-not $p) { continue }
        $p = $p.Trim()
        if ($seen.ContainsKey($p.ToLower())) { continue }
        $seen[$p.ToLower()] = $true
        if ($p -match 'sandbox_runtime|Doubao\\User Data|\\.doubao\\') { continue }
        if (Test-Path $p) { return $p }
    }
    return $null
}

$python = Find-PythonExe
if (-not $python) {
    $python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}
if (-not $python) {
    Write-Error "python.exe not found. Install Python 3.8+ first."
}

$content = Get-Content $configPath -Raw
if ($content -match '(?m)^\s*\[mcp_servers\.router-autostart\]') {
    Write-Host "mcp-autostart is already registered in config.toml - nothing to do."
    Write-Host "If you just changed the path, restart Codex to pick it up."
    exit 0
}

# TOML sections can be appended at end of file; existing [mcp_servers.*] blocks
# stay untouched.
$block = @"

[mcp_servers.router-autostart]
command = '$($python -replace '\\','\\')'
args = [
    '$($hook -replace '\\','\\')',
]
startup_timeout_sec = 30
"@

Add-Content -Path $configPath -Value $block -Encoding utf8
Write-Host "added [mcp_servers.router-autostart] to $configPath"
Write-Host "  command: $python"
Write-Host "  args:    $hook"
Write-Host ""
Write-Host "Restart Codex now. On launch it will start this MCP hook, which in"
Write-Host "turn starts router.py if it is not already running."
