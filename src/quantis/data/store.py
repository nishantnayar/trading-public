"""Persistence helpers for market data (idempotent upserts)."""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pandas as pd
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from quantis.db.engine import session_scope
from quantis.db.models import DailyBar, Fundamental, IngestRun


def _clean(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def upsert_daily_bars(df: pd.DataFrame, source: str = "alpaca") -> int:
    """Upsert long-format daily bars (BAR_COLUMNS). Returns rows written."""
    if df.empty:
        return 0

    records = []
    for row in df.itertuples(index=False):
        d = row._asdict()
        records.append(
            {
                "symbol": d["symbol"],
                "date": d["date"],
                "open": _clean(d["open"]),
                "high": _clean(d["high"]),
                "low": _clean(d["low"]),
                "close": _clean(d["close"]),
                "volume": int(_clean(d["volume"]) or 0),
                "vwap": _clean(d.get("vwap")),
                "trade_count": _clean(d.get("trade_count")),
                "source": source,
            }
        )

    written = 0
    with session_scope() as session:
        # chunk to keep parameter counts sane
        for i in range(0, len(records), 1000):
            chunk = records[i : i + 1000]
            stmt = insert(DailyBar).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=[DailyBar.symbol, DailyBar.date],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                    "vwap": stmt.excluded.vwap,
                    "trade_count": stmt.excluded.trade_count,
                    "source": stmt.excluded.source,
                },
            )
            session.execute(stmt)
            written += len(chunk)
    logger.info("upserted {} daily bars", written)
    return written


_FUNDAMENTAL_FIELDS = (
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "total_assets",
    "total_equity",
    "total_debt",
    "shares_outstanding",
    "operating_cash_flow",
    "capex",
)


def upsert_fundamentals(df: pd.DataFrame, source: str = "yfinance") -> int:
    """Upsert long-format quarterly fundamentals. Returns rows written."""
    if df.empty:
        return 0

    records = []
    for row in df.itertuples(index=False):
        d = row._asdict()
        record = {
            "symbol": d["symbol"],
            "period_end": d["period_end"],
            "as_of": d["as_of"],
            "source": source,
        }
        for field in _FUNDAMENTAL_FIELDS:
            record[field] = _clean(d.get(field))
        records.append(record)

    written = 0
    with session_scope() as session:
        for i in range(0, len(records), 500):
            chunk = records[i : i + 500]
            stmt = insert(Fundamental).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Fundamental.symbol, Fundamental.period_end],
                set_={
                    "as_of": stmt.excluded.as_of,
                    "source": stmt.excluded.source,
                    **{f: getattr(stmt.excluded, f) for f in _FUNDAMENTAL_FIELDS},
                },
            )
            session.execute(stmt)
            written += len(chunk)
    logger.info("upserted {} fundamental rows", written)
    return written


def fundamental_coverage() -> dict:
    """Quick summary of what's in fundamentals."""
    with session_scope() as session:
        n = session.scalar(select(func.count()).select_from(Fundamental))
        nsym = session.scalar(select(func.count(func.distinct(Fundamental.symbol))))
        dmin = session.scalar(select(func.min(Fundamental.period_end)))
        dmax = session.scalar(select(func.max(Fundamental.period_end)))
    return {"rows": n, "symbols": nsym, "start": dmin, "end": dmax}


def bar_coverage() -> dict:
    """Quick summary of what's in daily_bars."""
    with session_scope() as session:
        n = session.scalar(select(func.count()).select_from(DailyBar))
        nsym = session.scalar(select(func.count(func.distinct(DailyBar.symbol))))
        dmin = session.scalar(select(func.min(DailyBar.date)))
        dmax = session.scalar(select(func.max(DailyBar.date)))
    return {"rows": n, "symbols": nsym, "start": dmin, "end": dmax}


def start_ingest_run(flow: str) -> int:
    """Insert a running audit row; returns its id."""
    with session_scope() as session:
        row = IngestRun(flow=flow, status="running")
        session.add(row)
        session.flush()
        return int(row.id)


def finish_ingest_run(
    run_id: int,
    *,
    status: str,
    symbols_processed: int | None = None,
    rows_written: int | None = None,
    detail: str | None = None,
) -> None:
    """Close an audit row started by `start_ingest_run`."""
    with session_scope() as session:
        row = session.get(IngestRun, run_id)
        if row is None:
            return
        row.status = status
        row.finished_at = datetime.now(UTC)
        row.symbols_processed = symbols_processed
        row.rows_written = rows_written
        row.detail = (detail or "")[:512] or None
