"""Read-only SQL helpers for the dashboard API."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select

from quantis.db.engine import session_scope
from quantis.db.models import DailyBar, IngestRun, Symbol


def coverage() -> dict:
    with session_scope() as session:
        n = session.scalar(select(func.count()).select_from(DailyBar))
        nsym = session.scalar(select(func.count(func.distinct(DailyBar.symbol))))
        dmin = session.scalar(select(func.min(DailyBar.date)))
        dmax = session.scalar(select(func.max(DailyBar.date)))
    return {
        "rows": int(n or 0),
        "symbols": int(nsym or 0),
        "start": dmin.isoformat() if dmin else None,
        "end": dmax.isoformat() if dmax else None,
    }


def universe_rows() -> list[dict]:
    with session_scope() as session:
        query = (
            select(
                Symbol.symbol,
                Symbol.name,
                Symbol.sector,
                func.count(DailyBar.date).label("bars"),
                func.max(DailyBar.date).label("last_bar"),
            )
            .outerjoin(DailyBar, DailyBar.symbol == Symbol.symbol)
            .where(Symbol.active.is_(True))
            .group_by(Symbol.symbol, Symbol.name, Symbol.sector)
            .order_by(Symbol.symbol)
        )
        rows = session.execute(query).all()
    return [
        {
            "symbol": row.symbol,
            "name": row.name,
            "sector": row.sector,
            "bars": int(row.bars or 0),
            "last_bar": row.last_bar.isoformat() if row.last_bar else None,
        }
        for row in rows
    ]


def sector_counts() -> list[dict]:
    with session_scope() as session:
        query = (
            select(Symbol.sector, func.count())
            .where(Symbol.active.is_(True))
            .group_by(Symbol.sector)
            .order_by(func.count().desc())
        )
        rows = session.execute(query).all()
    return [{"sector": row[0] or "Unknown", "count": int(row[1])} for row in rows]


def daily_bars(symbol: str, start: dt.date) -> list[dict]:
    with session_scope() as session:
        query = (
            select(DailyBar)
            .where(DailyBar.symbol == symbol, DailyBar.date >= start)
            .order_by(DailyBar.date)
        )
        rows = session.scalars(query).all()
    return [
        {
            "date": row.date.isoformat(),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": int(row.volume),
        }
        for row in rows
    ]


def ingest_runs(limit: int = 20) -> list[dict]:
    with session_scope() as session:
        query = select(IngestRun).order_by(IngestRun.started_at.desc()).limit(limit)
        rows = session.scalars(query).all()
    return [
        {
            "id": row.id,
            "flow": row.flow,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "symbols_processed": row.symbols_processed,
            "rows_written": row.rows_written,
            "status": row.status,
            "detail": row.detail,
        }
        for row in rows
    ]
