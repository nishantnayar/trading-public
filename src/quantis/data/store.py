"""Persistence helpers for market data (idempotent upserts)."""

from __future__ import annotations

import math

import pandas as pd
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from quantis.db.engine import session_scope
from quantis.db.models import DailyBar


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


def bar_coverage() -> dict:
    """Quick summary of what's in daily_bars."""
    with session_scope() as session:
        n = session.scalar(select(func.count()).select_from(DailyBar))
        nsym = session.scalar(select(func.count(func.distinct(DailyBar.symbol))))
        dmin = session.scalar(select(func.min(DailyBar.date)))
        dmax = session.scalar(select(func.max(DailyBar.date)))
    return {"rows": n, "symbols": nsym, "start": dmin, "end": dmax}
