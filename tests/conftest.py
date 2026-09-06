"""Shared fixtures."""

from __future__ import annotations

import pytest


def postgres_reachable() -> bool:
    """True when a short Postgres ping succeeds."""
    try:
        import psycopg

        from quantis.config import get_settings

        settings = get_settings()
        dsn = (
            f"host={settings.pghost} port={settings.pgport} "
            f"dbname={settings.pgdatabase} user={settings.pguser} "
            f"password={settings.pgpassword}"
        )
        with psycopg.connect(dsn, connect_timeout=2) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.fixture
def require_postgres() -> None:
    if not postgres_reachable():
        pytest.skip("Postgres is not reachable")
