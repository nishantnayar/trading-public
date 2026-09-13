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


def test_recompute_signals_records_rows_written(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flows, "persist_latest_signals", lambda: 22)
    finished: dict[str, object] = {}
    monkeypatch.setattr(flows, "start_ingest_run", lambda *a, **k: 1)
    monkeypatch.setattr(
        flows, "finish_ingest_run", lambda run_id, **kwargs: finished.update(kwargs)
    )
    result = flows.recompute_signals.fn()
    assert result == {"rows_written": 22}
    assert finished == {"status": "success", "rows_written": 22}


def test_recompute_portfolio_records_success(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}
    monkeypatch.setattr(flows, "persist_portfolio_summary", lambda: called.setdefault("ran", True))
    monkeypatch.setattr(flows, "start_ingest_run", lambda *a, **k: 1)
    finished: dict[str, object] = {}
    monkeypatch.setattr(
        flows, "finish_ingest_run", lambda run_id, **kwargs: finished.update(kwargs)
    )
    result = flows.recompute_portfolio.fn()
    assert result == {"status": "ok"}
    assert called == {"ran": True}
    assert finished == {"status": "success"}


def test_rebalance_paper_records_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeResult:
        equity = 100_000.0
        cash = 0.0
        n_fills = 12
        n_positions = 150
        unpriced_symbols: tuple[str, ...] = ()

    monkeypatch.setattr(flows, "rebalance_simulated", lambda: _FakeResult())
    monkeypatch.setattr(flows, "start_ingest_run", lambda *a, **k: 1)
    finished: dict[str, object] = {}
    monkeypatch.setattr(
        flows, "finish_ingest_run", lambda run_id, **kwargs: finished.update(kwargs)
    )
    result = flows.rebalance_paper.fn()
    assert result == {
        "equity": 100_000.0,
        "cash": 0.0,
        "n_fills": 12,
        "n_positions": 150,
        "unpriced_symbols": [],
    }
    assert finished["status"] == "success"
    assert finished["symbols_processed"] == 150
    assert finished["rows_written"] == 12
    assert "unpriced" not in str(finished["detail"])


def test_rebalance_paper_flags_unpriced_symbols_in_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeResult:
        equity = 100_000.0
        cash = 0.0
        n_fills = 12
        n_positions = 150
        unpriced_symbols: tuple[str, ...] = ("ZZZZ",)

    monkeypatch.setattr(flows, "rebalance_simulated", lambda: _FakeResult())
    monkeypatch.setattr(flows, "start_ingest_run", lambda *a, **k: 1)
    finished: dict[str, object] = {}
    monkeypatch.setattr(
        flows, "finish_ingest_run", lambda run_id, **kwargs: finished.update(kwargs)
    )
    result = flows.rebalance_paper.fn()
    assert result["unpriced_symbols"] == ["ZZZZ"]
    assert "ZZZZ" in str(finished["detail"])


def test_pin_quantis_prefect_env_points_at_project_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PREFECT_API_URL", raising=False)
    monkeypatch.delenv("PREFECT_HOME", raising=False)
    from quantis.orchestration.serve import pin_quantis_prefect_env

    url = pin_quantis_prefect_env()
    assert url.endswith("/api")
    assert "4201" in url
    assert os.environ["PREFECT_API_URL"] == url
    assert os.environ["PREFECT_HOME"].endswith(".prefect")


def test_apply_deployments_registers_all_four_flows_in_cron_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`to_deployment()` builds a `RunnerDeployment` purely locally - only
    `.apply()` hits the Prefect API - so this stubs that one method and
    asserts the cron schedule without needing a live server.
    """
    from prefect.client.schemas.schedules import CronSchedule
    from prefect.deployments.runner import RunnerDeployment

    from quantis.orchestration.serve import apply_deployments

    def cron_of(d: RunnerDeployment) -> str:
        assert d.schedules is not None
        schedule = d.schedules[0].schedule
        assert isinstance(schedule, CronSchedule)
        return schedule.cron

    applied: list[RunnerDeployment] = []
    monkeypatch.setattr(RunnerDeployment, "apply", lambda self, **kw: applied.append(self))

    apply_deployments("quantis-ingestion")

    by_name = {d.name: d for d in applied}
    assert set(by_name) == {"daily-ingest", "daily-signals", "daily-portfolio", "daily-rebalance"}
    for d in applied:
        assert d.work_pool_name == "quantis-ingestion"
        assert cron_of(d).endswith("* * 1-5")  # weekdays only

    # Each stage runs after the last, in the order ingest -> signals -> portfolio -> rebalance.
    minutes = [int(cron_of(by_name[n]).split()[0]) for n in by_name]
    assert minutes == sorted(minutes)
    assert by_name["daily-rebalance"].flow_name == "rebalance-simulated"


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
