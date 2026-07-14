# Runs the full daily ETL: Node (teams/players/games from balldontlie) then
# Python (stats from nba_api). Meant to be called by Windows Task Scheduler.
# Logs everything to logs\daily_run_YYYY-MM-DD.log so failures are visible
# without needing to watch the terminal.

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$dateStamp = Get-Date -Format "yyyy-MM-dd"
$logFile = Join-Path $logDir "daily_run_$dateStamp.log"

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Write-Output $line
    Add-Content -Path $logFile -Value $line
}

Log "=== Daily ETL run starting ==="

try {
    Log "Running Node ETL (teams/players/games)..."
    Push-Location $root
    node src/dailyEtl.js 2>&1 | ForEach-Object { Add-Content -Path $logFile -Value $_ }
    if ($LASTEXITCODE -ne 0) { throw "Node ETL failed with exit code $LASTEXITCODE" }
    Pop-Location

    Log "Running Python stats sync..."
    Push-Location (Join-Path $root "python")
    & ".\venv\Scripts\python.exe" sync_stats.py 2>&1 | ForEach-Object { Add-Content -Path $logFile -Value $_ }
    if ($LASTEXITCODE -ne 0) { throw "Python stats sync failed with exit code $LASTEXITCODE" }
    Pop-Location

    Log "=== Daily ETL run finished successfully ==="
}
catch {
    Log "=== Daily ETL run FAILED: $_ ==="
    exit 1
}
