# Start quantis' Prefect server with an ISOLATED home + port 4201.
# This guarantees quantis uses its own prefect.db (not another project's shared one)
# and binds to 4201 so it never collides with trading-system (4200).
#
# Usage (from repo root):  ./scripts/prefect_server.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$env:PREFECT_HOME = Join-Path $root ".prefect"
$env:PREFECT_SERVER_API_HOST = "127.0.0.1"
$env:PREFECT_SERVER_API_PORT = "4201"
$env:PREFECT_API_URL = "http://127.0.0.1:4201/api"
# SQLite cannot take the notification loop plus deployment writes at once.
$env:PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED = "false"
$env:PREFECT_API_DATABASE_CONNECTION_TIMEOUT = "60"
$env:PREFECT_API_DATABASE_TIMEOUT = "60"

New-Item -ItemType Directory -Force -Path $env:PREFECT_HOME | Out-Null

Write-Host "PREFECT_HOME = $env:PREFECT_HOME"
Write-Host "Starting Prefect server on http://127.0.0.1:4201 ..."
uv run prefect server start
