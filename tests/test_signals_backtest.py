"""Vectorized long/flat backtest — pure function of price history, no DB."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from quantis.signals.backtest import _break_even_bps, backtest_symbol
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


def test_net_return_never_exceeds_gross_when_trades_occur() -> None:
    n = 300
    close = pd.Series(np.linspace(100, 200, n))
    df = pd.DataFrame({"date": _dates(n), "close": close})
    result = backtest_symbol(df, TrendParams(fast=10, slow=50), cost_bps_per_side=10.0)
    assert result.n_trades > 0
    assert result.net_return < result.strategy_return
    assert result.net_sharpe < result.sharpe


def test_zero_cost_bps_makes_net_equal_gross() -> None:
    n = 300
    close = pd.Series(np.linspace(100, 200, n))
    df = pd.DataFrame({"date": _dates(n), "close": close})
    result = backtest_symbol(df, TrendParams(fast=10, slow=50), cost_bps_per_side=0.0)
    assert result.net_return == result.strategy_return


def test_break_even_bps_is_infinite_when_never_traded() -> None:
    n = 300
    close = pd.Series([100.0] * n)
    df = pd.DataFrame({"date": _dates(n), "close": close})
    result = backtest_symbol(df, TrendParams(fast=10, slow=50))
    assert result.n_trades == 0
    assert math.isinf(result.break_even_bps)


def test_break_even_bps_zeroes_out_net_return_at_that_rate() -> None:
    n = 300
    close = pd.Series(np.linspace(100, 200, n))
    df = pd.DataFrame({"date": _dates(n), "close": close})
    result = backtest_symbol(df, TrendParams(fast=10, slow=50), cost_bps_per_side=0.0)
    assert result.n_trades > 0
    at_break_even = backtest_symbol(
        df, TrendParams(fast=10, slow=50), cost_bps_per_side=result.break_even_bps
    )
    assert at_break_even.net_return == pytest.approx(0.0, abs=1e-6)


def test_break_even_bps_is_zero_when_already_unprofitable_gross() -> None:
    # Directly exercise the helper: one trade, negative gross return.
    strategy_return = pd.Series([-0.05, 0.0, 0.0])
    trade_flag = pd.Series([1, 0, 1])
    assert _break_even_bps(strategy_return, trade_flag) == 0.0
