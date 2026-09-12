"""Indicator math and trend-rule labeling — no DB required."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantis.signals import indicators
from quantis.signals.rules import TrendParams, compute_signal


def _dates(n: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2024-01-01", periods=n)


def test_sma_is_trailing_mean() -> None:
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = indicators.sma(close, window=3)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == pytest.approx(2.0)
    assert result.iloc[4] == pytest.approx(4.0)


def test_momentum_excludes_the_skip_window() -> None:
    # Flat for well over a year, then a 10% pop in the most recent month only.
    close = pd.Series([100.0] * (14 * indicators.TRADING_DAYS_PER_MONTH))
    close.iloc[-5:] = 110.0
    mom = indicators.momentum(close, months=12, skip_months=1)
    # 12-1 momentum measures month -13..-1, before the pop, so it reads ~flat.
    assert mom.iloc[-1] == pytest.approx(0.0, abs=1e-9)


def test_compute_signal_goes_long_in_a_sustained_uptrend() -> None:
    n = 300
    close = pd.Series(np.linspace(100, 200, n))
    df = pd.DataFrame({"date": _dates(n), "close": close})
    out = compute_signal(df, TrendParams(fast=10, slow=50))
    assert out["signal"].iloc[-1] == "long"


def test_compute_signal_stays_flat_in_a_downtrend() -> None:
    n = 300
    close = pd.Series(np.linspace(200, 100, n))
    df = pd.DataFrame({"date": _dates(n), "close": close})
    out = compute_signal(df, TrendParams(fast=10, slow=50))
    assert out["signal"].iloc[-1] == "flat"


def test_compute_signal_flat_when_not_enough_history_for_slow_sma() -> None:
    n = 30
    close = pd.Series(np.linspace(100, 110, n))
    df = pd.DataFrame({"date": _dates(n), "close": close})
    out = compute_signal(df, TrendParams(fast=10, slow=50))
    assert out["signal"].iloc[-1] == "flat"


def test_compute_signal_exits_on_close_below_fast_sma() -> None:
    # Uptrend long enough to be in a golden-cross regime, then a sharp drop
    # below the fast SMA on the last bar — the stop should flip it flat even
    # though the SMAs haven't crossed back yet.
    n = 300
    close = pd.Series(np.linspace(100, 200, n))
    close.iloc[-1] = close.iloc[-2] * 0.5
    df = pd.DataFrame({"date": _dates(n), "close": close})
    out = compute_signal(df, TrendParams(fast=10, slow=50))
    assert out["signal"].iloc[-1] == "flat"
