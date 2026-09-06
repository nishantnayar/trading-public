"""Audit rows and portfolio API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from quantis.api.main import app
from quantis.data.store import finish_ingest_run, start_ingest_run
from quantis.db.engine import get_engine
from quantis.db.models import Base

client = TestClient(app)


def test_ingest_run_round_trip() -> None:
    Base.metadata.create_all(get_engine())
    run_id = start_ingest_run("test-audit")
    finish_ingest_run(run_id, status="success", symbols_processed=3, rows_written=9, detail="ok")
    from quantis.api.queries import ingest_runs

    rows = ingest_runs(limit=20)
    match = next(r for r in rows if r["id"] == run_id)
    assert match["status"] == "success"
    assert match["rows_written"] == 9
    assert match["flow"] == "test-audit"


def test_api_portfolio_endpoints_respond() -> None:
    Base.metadata.create_all(get_engine())
    for path in ("/signals", "/signals/quintiles", "/positions", "/model"):
        response = client.get(path)
        assert response.status_code == 200, path
