# Thin wrapper — scripts/start.py is the canonical launcher (Python is the core stack).
# Usage:  ./scripts/start.ps1            (all args are forwarded, e.g. --skip prefect)

uv run python (Join-Path $PSScriptRoot "start.py") @args
