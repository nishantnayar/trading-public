"""Prefect window helper — no Alpaca calls."""

from __future__ import annotations

import datetime as dt
import os

import pytest

from quantis.orchestration import flows


def test_incremental_window_overlaps_last_bar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flows, "bar_coverage", lambda: {"end": dt.date(2026, 9, 1)})
    start, end = flows.incremental_window(today=dt.date(2026, 9, 6))
    assert end == dt.date(2026, 9, 6)
    assert start == dt.date(2026, 8, 22)  # 10 calendar days back


def test_incremental_window_full_history_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flows, "bar_coverage", lambda: {"end": None})
    start, end = flows.incremental_window(today=dt.date(2026, 1, 15))
    assert start == flows.DEFAULT_START
    assert end == dt.date(2026, 1, 15)


def test_weekly_rebalance_does_not_hardcode_alpaca(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_rebalance(kind: str | None = None, persist: bool = True) -> dict:
        seen["kind"] = kind
        return {
            "n_orders": 0,
            "n_filled": 0,
            "broker": "simulated",
            "equity": 100_000.0,
        }

    monkeypatch.setattr("quantis.execution.broker.rebalance", fake_rebalance)
    monkeypatch.setattr(flows, "start_ingest_run", lambda *a, **k: 1)
    monkeypatch.setattr(flows, "finish_ingest_run", lambda *a, **k: None)
    result = flows.weekly_rebalance.fn()
    assert seen["kind"] is None
    assert result["broker"] == "simulated"


def test_pin_quantis_prefect_env_points_at_project_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PREFECT_API_URL", raising=False)
    monkeypatch.delenv("PREFECT_HOME", raising=False)
    from quantis.orchestration.serve import pin_quantis_prefect_env

    url = pin_quantis_prefect_env()
    assert url.endswith("/api")
    assert "4201" in url
    assert os.environ["PREFECT_API_URL"] == url
    assert os.environ["PREFECT_HOME"].endswith(".prefect")


def test_ensure_work_pool_swallows_already_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    from prefect.exceptions import ObjectAlreadyExists

    from quantis.orchestration.serve import ensure_work_pool

    class _FakeHTTPError(Exception):
        pass

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def create_work_pool(self, work_pool: object, overwrite: bool = False) -> None:
            raise ObjectAlreadyExists(http_exc=_FakeHTTPError("409"))

    monkeypatch.setattr("prefect.client.orchestration.get_client", lambda: _Client())
    assert ensure_work_pool("quantis-ingestion") == "quantis-ingestion"
