"""Environment gate as a test — asserts required imports and (if configured) DB ping."""

from __future__ import annotations

import importlib

import pytest

REQUIRED = [
    "pandas",
    "numpy",
    "sqlalchemy",
    "psycopg",
    "lightgbm",
    "xgboost",
    "shap",
    "mlflow",
    "vectorbt",
    "numba",
    "quantstats",
    "prefect",
    "fastapi",
    "uvicorn",
    "streamlit",
    "alpaca",
]


@pytest.mark.parametrize("module", REQUIRED)
def test_required_import(module: str) -> None:
    importlib.import_module(module)


def test_db_ping_if_configured() -> None:
    """Skips unless PGPASSWORD is set; otherwise requires a live connection."""
    from quantis.config import get_settings

    settings = get_settings()
    if not settings.has_db_password:
        pytest.skip("PGPASSWORD not set in .env — DB ping skipped")

    import psycopg

    dsn = (
        f"host={settings.pghost} port={settings.pgport} "
        f"dbname={settings.pgdatabase} user={settings.pguser} "
        f"password={settings.pgpassword}"
    )
    with psycopg.connect(dsn, connect_timeout=5) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1;")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1
