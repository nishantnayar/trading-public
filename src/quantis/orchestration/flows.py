"""Prefect flows for data ingestion.

Runs against quantis' own Prefect profile (SQLite backend, port 4201). The flow is a
plain callable too, so it can run without a Prefect server (ephemeral mode).
"""

from __future__ import annotations

import datetime as dt

from loguru import logger
from prefect import flow, task

from quantis.data.prices import AlpacaDailyBars
from quantis.data.store import (
    bar_coverage,
    finish_ingest_run,
    start_ingest_run,
    upsert_daily_bars,
)
from quantis.data.universe import active_symbols, seed_symbols

DEFAULT_START = dt.date(2016, 1, 1)  # Alpaca IEX history begins ~2016
INGEST_OVERLAP_DAYS = 10


def incremental_window(today: dt.date | None = None) -> tuple[dt.date, dt.date]:
    """Start from the last stored bar minus a few days of overlap, not 2016.

    The scheduled daily job must not re-download the whole history every evening.
    A 10-day overlap covers weekends, holidays, and a missed run.
    """
    end = today or dt.date.today()
    last = bar_coverage().get("end")
    if last is None:
        return DEFAULT_START, end
    if not isinstance(last, dt.date):
        last = dt.date.fromisoformat(str(last)[:10])
    return last - dt.timedelta(days=INGEST_OVERLAP_DAYS), end


@task(retries=2, retry_delay_seconds=10)
def _fetch_and_store(symbols: list[str], start: dt.date, end: dt.date) -> int:
    source = AlpacaDailyBars()
    df = source.get_daily_bars(symbols, start, end)
    return upsert_daily_bars(df, source=source.name)


@flow(name="ingest-daily-bars")
def ingest_daily_bars(
    start: dt.date | None = None,
    end: dt.date | None = None,
    batch_size: int = 100,
) -> dict:
    """Seed the universe, then fetch daily bars from Alpaca in batches and upsert."""
    start = start or DEFAULT_START
    end = end or dt.date.today()

    seed_symbols()
    symbols = active_symbols()
    logger.info("ingesting {} symbols {} .. {}", len(symbols), start, end)

    run_id = start_ingest_run("ingest-daily-bars")
    total = 0
    try:
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            total += _fetch_and_store(batch, start, end)
        coverage = bar_coverage()
        finish_ingest_run(
            run_id,
            status="success",
            symbols_processed=len(symbols),
            rows_written=total,
            detail=f"{coverage.get('start')} -> {coverage.get('end')}",
        )
        logger.info("ingest complete: {}", coverage)
        return coverage
    except Exception as exc:
        finish_ingest_run(
            run_id,
            status="failed",
            symbols_processed=len(symbols),
            rows_written=total,
            detail=str(exc),
        )
        raise


@flow(name="ingest-daily-incremental")
def ingest_incremental() -> dict:
    """Scheduled ingest: last bar minus overlap, not a full 2016 backfill."""
    start, end = incremental_window()
    logger.info("incremental window {} .. {}", start, end)
    return ingest_daily_bars.fn(start=start, end=end)


@flow(name="rebuild-features")
def rebuild_features() -> dict:
    from quantis.features.build import run as build_features

    return build_features()


@flow(name="weekly-research")
def weekly_research() -> dict:
    """Features -> train -> publish. Heavy; Saturday morning is the intended slot."""
    from quantis.backtest.publish import publish
    from quantis.features.build import run as build_features
    from quantis.models.train import run as train_model

    features = build_features()
    metrics = train_model(log_mlflow=True)
    snapshot = publish()
    return {
        "features": features,
        "rank_ic": metrics.get("rank_ic"),
        "published": snapshot.get("as_of"),
    }


@flow(name="weekly-rebalance")
def weekly_rebalance(broker: str | None = None) -> dict:
    """Move the configured broker toward the published target book.

    Defaults to the simulated ledger. Set QUANTIS_BROKER=alpaca-paper (and keep
    ALPACA_PAPER=true) to submit paper orders. There is no live path.
    """
    from quantis.execution.broker import rebalance

    run_id = start_ingest_run("weekly-rebalance")
    try:
        result = rebalance(kind=broker)
        finish_ingest_run(
            run_id,
            status="success",
            symbols_processed=result["n_orders"],
            rows_written=result["n_filled"],
            detail=f"{result['broker']} equity={result['equity']:.0f}",
        )
        return result
    except Exception as exc:
        finish_ingest_run(run_id, status="failed", detail=str(exc))
        raise


if __name__ == "__main__":
    print(ingest_daily_bars())
