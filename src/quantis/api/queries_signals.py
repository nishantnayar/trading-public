"""Read-only SQL helpers for the current trend-rule watchlist snapshot."""

from __future__ import annotations

from sqlalchemy import select

from quantis.db.engine import session_scope
from quantis.db.models import Signal


def latest_signals() -> list[dict]:
    with session_scope() as session:
        rows = session.scalars(select(Signal).order_by(Signal.symbol)).all()
    return [
        {
            "symbol": row.symbol,
            "date": row.date.isoformat(),
            "signal": row.signal,
            "close": float(row.close),
            "sma_fast": float(row.sma_fast) if row.sma_fast is not None else None,
            "sma_slow": float(row.sma_slow) if row.sma_slow is not None else None,
            "mom_12_1": float(row.mom_12_1) if row.mom_12_1 is not None else None,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        }
        for row in rows
    ]
