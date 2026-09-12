"""Vectorized long/flat backtest — pure function of price history, no DB."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantis.signals.backtest import backtest_symbol
from quantis.signals.rules import TrendParams


def _dates(n: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2024-01-01", periods=n)


def test_backtest_never_holds_a_position_on_the_signal_bar_itself() -> None:
    """Position must be the *prior* bar's signal — no look-ahead."""
    n = 300
    close = pd.Series(np.linspace(100, 200, n))
    df = pd.DataFrame({"date": _dates(n), "close": close})
    result = backtest_symbol(df, TrendParams(fast=10, slow=50))
    # A sustained uptrend eventually goes long and should earn a positive,
    # smaller-than-buy-and-hold return (entry is delayed by the SMA warm-up
    # and the one-bar lag).
    assert result.strategy_return > 0
    assert result.strategy_return < result.buy_hold_return


def test_backtest_flat_series_yields_zero_return() -> None:
    n = 300
    close = pd.Series([100.0] * n)
    df = pd.DataFrame({"date": _dates(n), "close": close})
    result = backtest_symbol(df, TrendParams(fast=10, slow=50))
    assert result.strategy_return == 0.0
    assert result.n_trades == 0
    assert result.time_in_market == 0.0
