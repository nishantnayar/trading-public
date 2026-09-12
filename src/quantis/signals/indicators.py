"""Pure price-series indicators. No I/O, no state — easy to unit test."""

from __future__ import annotations

import pandas as pd

TRADING_DAYS_PER_MONTH = 21


def sma(close: pd.Series, window: int) -> pd.Series:
    """Simple moving average over `window` trading days."""
    return close.rolling(window).mean()


def momentum(close: pd.Series, months: int = 12, skip_months: int = 1) -> pd.Series:
    """Trailing `months`-month return, excluding the most recent `skip_months`.

    The 12-1 convention (12 months back, skip the last 1) avoids the short-term
    reversal effect that contaminates raw 12-month momentum.
    """
    lookback = months * TRADING_DAYS_PER_MONTH
    skip = skip_months * TRADING_DAYS_PER_MONTH
    return close.shift(skip) / close.shift(lookback + skip) - 1
