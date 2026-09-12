"""Load price history from the DB and evaluate the trend rule over the watchlist."""

from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy import select

from quantis.db.engine import session_scope
from quantis.db.models import DailyBar
from quantis.signals.rules import TrendParams, compute_signal
from quantis.signals.universe import WATCHLIST


def load_price_history(symbol: str, start: dt.date | None = None) -> pd.DataFrame:
    """Ascending (date, close) history for `symbol`, in a DataFrame."""
    with session_scope() as session:
        query = select(DailyBar.date, DailyBar.close).where(DailyBar.symbol == symbol)
        if start is not None:
            query = query.where(DailyBar.date >= start)
        rows = session.execute(query.order_by(DailyBar.date)).all()
    return pd.DataFrame(rows, columns=["date", "close"]).astype({"close": "float64"})


def latest_signals(
    symbols: list[str] = WATCHLIST,
    params: TrendParams | None = None,
) -> list[dict]:
    """The most recent signal row for each symbol, or a `no_data` stub if empty."""
    params = params or TrendParams()
    results: list[dict] = []
    for symbol in symbols:
        history = load_price_history(symbol)
        if history.empty:
            results.append({"symbol": symbol, "signal": "no_data"})
            continue
        signals = compute_signal(history, params)
        last = signals.iloc[-1]
        results.append(
            {
                "symbol": symbol,
                "date": last["date"].isoformat(),
                "signal": last["signal"],
                "close": float(last["close"]),
                "sma_fast": _clean(last["sma_fast"]),
                "sma_slow": _clean(last["sma_slow"]),
                "mom_12_1": _clean(last["mom_12_1"]),
            }
        )
    return results


def _clean(value: float) -> float | None:
    return None if pd.isna(value) else float(value)
