# Start the quantis Streamlit dashboard on its dedicated port (8502).
# Usage (from repo root):  ./scripts/dashboard.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Starting Quantis dashboard on http://localhost:8502 ..."
uv run streamlit run dashboard/app.py --server.port 8502
