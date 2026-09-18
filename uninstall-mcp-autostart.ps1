# Undo install-mcp-autostart.ps1: drop the MCP hook block from config.toml.
# Does not stop a router that is already running; run stop-router.ps1 for that.

$ErrorActionPreference = 'Stop'

$configPath = Join-Path (Join-Path $env:USERPROFILE '.codex') 'config.toml'
if (-not (Test-Path $configPath)) { Write-Error "missing $configPath" }

$lines = Get-Content $configPath
$out = New-Object System.Collections.Generic.List[string]
$skip = $false
foreach ($line in $lines) {
    if ($line -match '^\s*\[mcp_servers\.router-autostart\]') {
        $skip = $true
        continue
    }
    if ($skip -and $line -match '^\s*\[') {
        # Hit the next section; stop skipping.
        $skip = $false
    }
    if (-not $skip) { $out.Add($line) | Out-Null }
}

Set-Content -Path $configPath -Value $out -Encoding utf8
Write-Host "removed [mcp_servers.router-autostart] from $configPath"
Write-Host "Restart Codex for the change to take effect."
