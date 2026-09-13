"""Equal-weight portfolio construction — pure function of price history, no DB."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import quantis.signals.backtest as backtest_module
import quantis.signals.portfolio as portfolio_module
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


def _three_identical_tech_names(monkeypatch: pytest.MonkeyPatch) -> pd.DataFrame:
    df = _uptrend("2023-01-01", 400)
    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["A", "B", "C"])
    monkeypatch.setattr(backtest_module, "load_price_history", lambda symbol: df)
    monkeypatch.setattr(
        portfolio_module,
        "_symbol_sectors",
        lambda symbols: {"A": "Tech", "B": "Tech", "C": "Tech"},
    )
    return df


def test_uncapped_book_is_fully_invested_when_names_are_long(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _three_identical_tech_names(monkeypatch)
    daily = daily_book_returns(params=TrendParams(fast=10, slow=50))
    long_days = daily[daily["n_long"] > 0]
    assert not long_days.empty
    assert np.allclose(long_days["exposure"], 1.0)


def test_sector_cap_reduces_exposure_when_one_sector_dominates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # All three names are the same sector, so an uncapped day is 100% Tech;
    # capping Tech at 50% should cut exposure on those days to exactly 0.5,
    # not reallocate the freed weight elsewhere.
    _three_identical_tech_names(monkeypatch)
    daily = daily_book_returns(params=TrendParams(fast=10, slow=50), max_sector_weight=0.5)
    long_days = daily[daily["n_long"] > 0]
    assert not long_days.empty
    assert np.allclose(long_days["exposure"], 0.5)


def test_sector_cap_leaves_an_uncrowded_sector_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    df = _uptrend("2023-01-01", 400)
    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["A", "B"])
    monkeypatch.setattr(backtest_module, "load_price_history", lambda symbol: df)
    monkeypatch.setattr(
        portfolio_module, "_symbol_sectors", lambda symbols: {"A": "Tech", "B": "Energy"}
    )
    # Each sector has exactly one name at 1/2 = 50% weight; a 60% cap should
    # not touch either one.
    daily = daily_book_returns(params=TrendParams(fast=10, slow=50), max_sector_weight=0.6)
    long_days = daily[daily["n_long"] > 0]
    assert not long_days.empty
    assert np.allclose(long_days["exposure"], 1.0)


def test_sector_cap_lowers_avg_exposure_in_portfolio_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _three_identical_tech_names(monkeypatch)
    uncapped = portfolio_summary(params=TrendParams(fast=10, slow=50))
    capped = portfolio_summary(params=TrendParams(fast=10, slow=50), max_sector_weight=0.5)
    # Every long day goes from 100% to 50% exposure, so the full-period
    # (including flat/warm-up days) average should exactly halve too.
    assert capped.avg_exposure == pytest.approx(uncapped.avg_exposure * 0.5)
    assert capped.max_sector_weight == 0.5
    assert uncapped.max_sector_weight is None
