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


if __name__ == "__main__":
    print(ingest_daily_bars())
