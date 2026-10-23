# Stop codex-model-router by the port it listens on.

$configPath = Join-Path (Join-Path $env:USERPROFILE '.codex') 'model-router.json'
$listen = ((Get-Content $configPath -Raw | ConvertFrom-Json).listen) -split ':'
$port = [int]$listen[-1]

$owners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique

if (-not $owners) {
    Write-Host "nothing listening on port $port"
    exit 0
}

foreach ($id in $owners) {
    Stop-Process -Id $id -Force
    Write-Host "stopped process $id"
}
