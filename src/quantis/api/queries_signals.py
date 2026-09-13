"""Read-only SQL helpers for the current trend-rule watchlist snapshot."""

from __future__ import annotations

from sqlalchemy import select

from quantis.db.engine import session_scope
from quantis.db.models import Signal, Symbol


def latest_signals() -> list[dict]:
    with session_scope() as session:
        rows = session.execute(
            select(Signal, Symbol.name, Symbol.sector)
            .outerjoin(Symbol, Symbol.symbol == Signal.symbol)
            .order_by(Signal.symbol)
        ).all()
    return [
        {
            "symbol": sig.symbol,
            "name": name,
            "sector": sector,
            "date": sig.date.isoformat(),
            "signal": sig.signal,
            "close": float(sig.close),
            "sma_fast": float(sig.sma_fast) if sig.sma_fast is not None else None,
            "sma_slow": float(sig.sma_slow) if sig.sma_slow is not None else None,
            "mom_12_1": float(sig.mom_12_1) if sig.mom_12_1 is not None else None,
            "computed_at": sig.computed_at.isoformat() if sig.computed_at else None,
        }
        for sig, name, sector in rows
    ]
