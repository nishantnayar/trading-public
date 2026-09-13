"""Equal-weight portfolio construction — pure function of price history, no DB."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import quantis.signals.backtest as backtest_module
from quantis.signals.portfolio import daily_book_returns, portfolio_summary
from quantis.signals.rules import TrendParams


def _uptrend(start: str, periods: int, base: float = 100.0) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=periods)
    close = pd.Series(np.linspace(base, base * 2, periods))
    return pd.DataFrame({"date": dates, "close": close})


def test_daily_book_return_is_average_of_currently_long_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Two symbols, identical uptrend, offset so only one is long on any given
    # day early on, then both are long later — daily_book_returns should
    # average across whichever are actually long that day, not all symbols.
    df_a = _uptrend("2023-01-01", 400, base=100.0)
    df_b = _uptrend("2023-01-01", 400, base=100.0)

    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["A", "B"])
    monkeypatch.setattr(
        backtest_module,
        "load_price_history",
        lambda symbol: df_a if symbol == "A" else df_b,
    )

    daily = daily_book_returns(params=TrendParams(fast=10, slow=50))
    assert not daily.empty
    # Identical series -> identical signals -> n_long is 0 or 2, never 1.
    assert set(daily["n_long"].unique()) <= {0, 2}


def test_portfolio_summary_flat_book_is_zero_everywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    n = 300
    flat = pd.DataFrame({"date": pd.bdate_range("2024-01-01", periods=n), "close": [100.0] * n})
    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["FLAT"])
    monkeypatch.setattr(backtest_module, "load_price_history", lambda symbol: flat)

    result = portfolio_summary(params=TrendParams(fast=10, slow=50))
    assert result.total_return == 0.0
    assert result.sharpe == 0.0
    assert result.max_drawdown == 0.0
    assert result.avg_names_long == 0.0
    assert result.annualized_turnover == 0.0


def test_portfolio_summary_sustained_uptrend_is_profitable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    df = _uptrend("2023-01-01", 500)
    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["ONLYNAME"])
    monkeypatch.setattr(backtest_module, "load_price_history", lambda symbol: df)

    result = portfolio_summary(params=TrendParams(fast=10, slow=50))
    assert result.total_return > 0
    assert result.sharpe > 0
    assert result.avg_names_long <= 1.0
    assert result.max_drawdown <= 0.0  # a drawdown series is always <= 0
