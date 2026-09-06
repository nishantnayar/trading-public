"""Environment gate: verify every key package imports and the DB is reachable.

Run with:  uv run python scripts/env_check.py
Exit code 0 = all required checks passed.
"""

from __future__ import annotations

import importlib
import sys

# (import_name, pretty_label, group) — group is informational only.
CHECKS: list[tuple[str, str, str]] = [
    ("pandas", "pandas", "core"),
    ("numpy", "numpy", "core"),
    ("pyarrow", "pyarrow", "core"),
    ("sqlalchemy", "SQLAlchemy", "core"),
    ("psycopg", "psycopg (v3)", "core"),
    ("alembic", "alembic", "core"),
    ("pydantic", "pydantic", "core"),
    ("pydantic_settings", "pydantic-settings", "core"),
    ("dotenv", "python-dotenv", "core"),
    ("httpx", "httpx", "core"),
    ("tenacity", "tenacity", "core"),
    ("loguru", "loguru", "core"),
    ("alpaca", "alpaca-py", "data"),
    ("yfinance", "yfinance", "data"),
    ("pandas_datareader", "pandas-datareader", "data"),
    ("sklearn", "scikit-learn", "ml"),
    ("lightgbm", "lightgbm", "ml"),
    ("xgboost", "xgboost", "ml"),
    ("shap", "shap", "ml"),
    ("mlflow", "mlflow", "ml"),
    ("vectorbt", "vectorbt", "backtest"),
    ("numba", "numba (via vectorbt)", "backtest"),
    ("llvmlite", "llvmlite (via numba)", "backtest"),
    ("quantstats", "quantstats", "backtest"),
    ("prefect", "prefect", "orchestration"),
    ("fastapi", "fastapi", "api"),
    ("uvicorn", "uvicorn", "api"),
    ("streamlit", "streamlit", "app"),
    ("plotly", "plotly", "app"),
    ("altair", "altair", "app"),
]

# Optional (RL group — only present when installed with --group rl).
OPTIONAL_CHECKS: list[tuple[str, str, str]] = [
    ("gymnasium", "gymnasium", "rl"),
    ("stable_baselines3", "stable-baselines3", "rl"),
    ("torch", "torch", "rl"),
]


def _version(mod) -> str:
    for attr in ("__version__", "version", "VERSION"):
        v = getattr(mod, attr, None)
        if isinstance(v, str):
            return v
    return "?"


def run_import_checks() -> int:
    failures = 0
    print(f"Python {sys.version.split()[0]}  ({sys.executable})\n")
    print("Required packages")
    print("-" * 52)
    for import_name, label, group in CHECKS:
        try:
            mod = importlib.import_module(import_name)
            print(f"  [ ok ] {label:<26} {_version(mod):<12} ({group})")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  [FAIL] {label:<26} {type(exc).__name__}: {exc}")

    print("\nOptional (RL group)")
    print("-" * 52)
    for import_name, label, group in OPTIONAL_CHECKS:
        try:
            mod = importlib.import_module(import_name)
            print(f"  [ ok ] {label:<26} {_version(mod):<12} ({group})")
        except Exception:  # noqa: BLE001
            print(f"  [skip] {label:<26} not installed        ({group})")
    return failures


def run_db_check() -> tuple[bool, str]:
    """Returns (ok, message). Skipped (ok=True) when no password is configured."""
    try:
        from quantis.config import get_settings

        settings = get_settings()
    except Exception as exc:  # noqa: BLE001
        return False, f"could not load settings: {exc}"

    if not settings.has_db_password:
        return True, "SKIPPED — no PGPASSWORD in .env yet (set it to run the DB ping)"

    try:
        import psycopg

        dsn = (
            f"host={settings.pghost} port={settings.pgport} "
            f"dbname={settings.pgdatabase} user={settings.pguser} "
            f"password={settings.pgpassword}"
        )
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                ver = cur.fetchone()[0]
        return True, f"connected — {ver.split(',')[0]}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    import_failures = run_import_checks()

    print("\nPostgres connectivity")
    print("-" * 52)
    db_ok, db_msg = run_db_check()
    tag = "ok" if db_ok else "FAIL"
    print(f"  [{tag:>4}] {db_msg}")

    print("\n" + "=" * 52)
    if import_failures == 0 and db_ok:
        print("ENV GATE: PASS")
        return 0
    print(f"ENV GATE: FAIL  ({import_failures} import failure(s), db_ok={db_ok})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
