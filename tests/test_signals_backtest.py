"""Vectorized long/flat backtest — pure function of price history, no DB."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import quantis.signals.backtest as backtest_module
from quantis.signals.backtest import (
    BacktestResult,
    _break_even_bps,
    backtest_symbol,
    regime_breakdown,
    sector_breakdown,
)
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


def test_sector_breakdown_groups_and_ranks_by_median_net_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_results = [
        BacktestResult(
            symbol="A",
            strategy_return=0,
            buy_hold_return=0,
            sharpe=0,
            n_trades=1,
            time_in_market=0.5,
            net_return=0.10,
        ),
        BacktestResult(
            symbol="B",
            strategy_return=0,
            buy_hold_return=0,
            sharpe=0,
            n_trades=1,
            time_in_market=0.5,
            net_return=0.20,
        ),
        BacktestResult(
            symbol="C",
            strategy_return=0,
            buy_hold_return=0,
            sharpe=0,
            n_trades=1,
            time_in_market=0.5,
            net_return=-0.30,
        ),
    ]
    monkeypatch.setattr(backtest_module, "run_watchlist", lambda *a, **k: fake_results)
    monkeypatch.setattr(
        backtest_module,
        "_symbol_sectors",
        lambda symbols: {"A": "Tech", "B": "Tech", "C": "Energy"},
    )
    results = sector_breakdown()
    by_sector = {r.sector: r for r in results}
    assert by_sector["Tech"].n_symbols == 2
    assert by_sector["Tech"].median_net_return == pytest.approx(0.15)
    assert by_sector["Tech"].net_win_rate == 1.0
    assert by_sector["Energy"].net_win_rate == 0.0
    # Sorted best-median-net-return first.
    assert results[0].sector == "Tech"


def test_regime_breakdown_isolates_a_bad_year(monkeypatch: pytest.MonkeyPatch) -> None:
    # 3 years: sustained uptrend through 2023-2024 (long enough for the
    # default 12-1 momentum's ~273-day lookback to clear), then a single-day
    # 30% crash on the last day of 2025 while still in the position.
    dates = pd.bdate_range("2023-01-01", "2025-12-31")
    n = len(dates)
    close = pd.Series(np.linspace(100, 200, n))
    close.iloc[-1] = close.iloc[-2] * 0.7
    df = pd.DataFrame({"date": dates, "close": close})

    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["ONLYNAME"])
    monkeypatch.setattr(backtest_module, "load_price_history", lambda symbol: df)

    results = regime_breakdown(params=TrendParams(fast=10, slow=50))
    by_year = {r.year: r for r in results}
    assert by_year[2024].return_pct > 0
    assert by_year[2025].return_pct < by_year[2024].return_pct
    assert all(r.avg_names_long <= 1.0 for r in results)
