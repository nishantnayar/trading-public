"""Equal-weight portfolio construction — pure function of price history, no DB."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import quantis.signals.backtest as backtest_module
import quantis.signals.portfolio as portfolio_module
from quantis.signals.portfolio import (
    DEFAULT_MAX_NAME_WEIGHT,
    DEFAULT_MAX_SECTOR_WEIGHT,
    DEFAULT_REALLOCATE,
    DEFAULT_VOL_TARGET,
    _apply_name_cap,
    _vol_target_leverage,
    _water_fill_sector_weights,
    daily_book_returns,
    portfolio_summary,
)
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

    daily = daily_book_returns(params=TrendParams(fast=10, slow=50), max_sector_weight=None)
    assert not daily.empty
    # Identical series -> identical signals -> n_long is 0 or 2, never 1.
    assert set(daily["n_long"].unique()) <= {0, 2}


def test_portfolio_summary_flat_book_is_zero_everywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    n = 300
    flat = pd.DataFrame({"date": pd.bdate_range("2024-01-01", periods=n), "close": [100.0] * n})
    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["FLAT"])
    monkeypatch.setattr(backtest_module, "load_price_history", lambda symbol: flat)

    result = portfolio_summary(params=TrendParams(fast=10, slow=50), max_sector_weight=None)
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

    result = portfolio_summary(params=TrendParams(fast=10, slow=50), max_sector_weight=None)
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
    daily = daily_book_returns(params=TrendParams(fast=10, slow=50), max_sector_weight=None)
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
    uncapped = portfolio_summary(params=TrendParams(fast=10, slow=50), max_sector_weight=None)
    capped = portfolio_summary(params=TrendParams(fast=10, slow=50), max_sector_weight=0.5)
    # Every long day goes from 100% to 50% exposure, so the full-period
    # (including flat/warm-up days) average should exactly halve too.
    assert capped.avg_exposure == pytest.approx(uncapped.avg_exposure * 0.5)
    assert capped.max_sector_weight == 0.5
    assert uncapped.max_sector_weight is None


def test_water_fill_reallocates_freed_weight_to_under_cap_sectors() -> None:
    # 3 Tech, 1 Energy, 1 Health names; raw shares 0.6/0.2/0.2. Tech is over a
    # 0.4 cap, pinned there; the freed 0.2 splits proportionally between the
    # two untouched sectors (each already at 0.2, equal raw shares) -> 0.3 each.
    counts = pd.Series({"Tech": 3, "Energy": 1, "Health": 1})
    weights = _water_fill_sector_weights(counts, cap=0.4)
    assert weights["Tech"] == pytest.approx(0.4)
    assert weights["Energy"] == pytest.approx(0.3)
    assert weights["Health"] == pytest.approx(0.3)
    assert weights.sum() == pytest.approx(1.0)  # fully reallocated, nothing left as cash


def test_water_fill_leaves_cash_when_every_sector_is_pinned() -> None:
    # Two equal sectors, cap 0.4 each -> even fully allocated, 0.4+0.4 = 0.8;
    # the remaining 0.2 has nowhere to go under the constraint.
    counts = pd.Series({"Tech": 1, "Energy": 1})
    weights = _water_fill_sector_weights(counts, cap=0.4)
    assert weights["Tech"] == pytest.approx(0.4)
    assert weights["Energy"] == pytest.approx(0.4)
    assert weights.sum() == pytest.approx(0.8)


def test_reallocation_achieves_full_exposure_where_non_reallocation_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    df = _uptrend("2023-01-01", 400)
    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["A", "B", "C", "D", "E"])
    monkeypatch.setattr(backtest_module, "load_price_history", lambda symbol: df)
    monkeypatch.setattr(
        portfolio_module,
        "_symbol_sectors",
        lambda symbols: {"A": "Tech", "B": "Tech", "C": "Tech", "D": "Energy", "E": "Health"},
    )

    not_reallocated = daily_book_returns(
        params=TrendParams(fast=10, slow=50), max_sector_weight=0.4, reallocate=False
    )
    reallocated = daily_book_returns(
        params=TrendParams(fast=10, slow=50), max_sector_weight=0.4, reallocate=True
    )
    long_days_a = not_reallocated[not_reallocated["n_long"] > 0]
    long_days_b = reallocated[reallocated["n_long"] > 0]
    assert not long_days_a.empty and not long_days_b.empty
    assert np.allclose(long_days_a["exposure"], 0.8)  # 0.4 Tech + 0.2 Energy + 0.2 Health
    assert np.allclose(long_days_b["exposure"], 1.0)  # freed Tech weight reallocated


def test_portfolio_summary_records_reallocated_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _three_identical_tech_names(monkeypatch)
    result = portfolio_summary(
        params=TrendParams(fast=10, slow=50), max_sector_weight=0.5, reallocate=True
    )
    assert result.reallocated is True


def test_defaults_are_15pct_reallocated_sector_cap() -> None:
    assert DEFAULT_MAX_SECTOR_WEIGHT == 0.15
    assert DEFAULT_REALLOCATE is True


def test_portfolio_summary_applies_default_cap_and_reallocation_when_unspecified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 5 names, 3 sectors (Tech dominant at 3/5 = 60% raw share) - calling with
    # no explicit max_sector_weight/reallocate should behave exactly like the
    # explicit 15%-capped, reallocated call, and differently from uncapped.
    df = _uptrend("2023-01-01", 400)
    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["A", "B", "C", "D", "E"])
    monkeypatch.setattr(backtest_module, "load_price_history", lambda symbol: df)
    monkeypatch.setattr(
        portfolio_module,
        "_symbol_sectors",
        lambda symbols: {"A": "Tech", "B": "Tech", "C": "Tech", "D": "Energy", "E": "Health"},
    )

    default_result = portfolio_summary(params=TrendParams(fast=10, slow=50))
    explicit_result = portfolio_summary(
        params=TrendParams(fast=10, slow=50), max_sector_weight=0.15, reallocate=True
    )
    uncapped_result = portfolio_summary(
        params=TrendParams(fast=10, slow=50), max_sector_weight=None
    )

    assert default_result.avg_exposure == pytest.approx(explicit_result.avg_exposure)
    assert default_result.avg_exposure != pytest.approx(uncapped_result.avg_exposure)
    assert default_result.max_sector_weight == 0.15
    assert default_result.reallocated is True


def test_vol_targeting_is_off_by_default() -> None:
    assert DEFAULT_VOL_TARGET is None


def test_vol_target_leverage_matches_target_over_realized_ratio() -> None:
    # Alternating +-1% returns has an exact population std of 0.01, so the
    # annualized trailing vol is deterministic: 0.01 * sqrt(252).
    returns = pd.Series([0.01, -0.01] * 30)
    realized_annual_vol = 0.01 * np.sqrt(252)
    leverage = _vol_target_leverage(
        returns, target_vol=realized_annual_vol, lookback=20, max_leverage=5.0
    )
    # Skip the lookback warm-up plus the one-day shift.
    assert np.allclose(leverage.iloc[25:], 1.0, atol=1e-6)


def test_vol_target_leverage_caps_at_max_leverage_in_a_low_vol_regime() -> None:
    returns = pd.Series([0.001, -0.001] * 30)  # low realized vol
    leverage = _vol_target_leverage(returns, target_vol=0.20, lookback=20, max_leverage=1.5)
    assert np.allclose(leverage.iloc[25:], 1.5, atol=1e-6)


def test_vol_target_leverage_defaults_to_one_during_warmup() -> None:
    returns = pd.Series([0.01, -0.01] * 5)  # only 10 rows, less than lookback=20
    leverage = _vol_target_leverage(returns, target_vol=0.10, lookback=20, max_leverage=1.5)
    assert (leverage == 1.0).all()


def test_vol_target_leverage_never_negative_when_vol_is_zero() -> None:
    returns = pd.Series([0.0] * 60)  # zero realized vol -> target/0 is inf
    leverage = _vol_target_leverage(returns, target_vol=0.10, lookback=20, max_leverage=1.5)
    assert (leverage >= 0).all()
    assert not leverage.isna().any()


def test_daily_book_returns_leverage_column_is_one_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    df = _uptrend("2023-01-01", 400)
    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["ONLYNAME"])
    monkeypatch.setattr(backtest_module, "load_price_history", lambda symbol: df)

    daily = daily_book_returns(
        params=TrendParams(fast=10, slow=50), max_sector_weight=None, vol_target=None
    )
    assert (daily["leverage"] == 1.0).all()


def test_portfolio_summary_records_vol_target_and_scales_leverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    df = _uptrend("2023-01-01", 500)
    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["ONLYNAME"])
    monkeypatch.setattr(backtest_module, "load_price_history", lambda symbol: df)

    no_target = portfolio_summary(
        params=TrendParams(fast=10, slow=50), max_sector_weight=None, vol_target=None
    )
    with_target = portfolio_summary(
        params=TrendParams(fast=10, slow=50), max_sector_weight=None, vol_target=0.10
    )
    assert no_target.vol_target is None
    assert no_target.avg_leverage == pytest.approx(1.0)
    assert with_target.vol_target == 0.10
    assert with_target.avg_leverage != pytest.approx(1.0)


def test_name_cap_is_off_by_default() -> None:
    assert DEFAULT_MAX_NAME_WEIGHT is None


def test_apply_name_cap_returns_unchanged_when_disabled() -> None:
    long_days = pd.DataFrame({"date": ["2024-01-01"] * 2, "symbol": ["A", "B"]})
    weight = pd.Series([0.5, 0.5])
    result = _apply_name_cap(weight, long_days, max_name_weight=None, reallocate=False)
    assert (result == weight).all()


def test_apply_name_cap_clips_without_reallocating() -> None:
    long_days = pd.DataFrame({"date": ["2024-01-01"] * 3, "symbol": ["A", "B", "C"]})
    weight = pd.Series([0.5, 0.3, 0.2])
    result = _apply_name_cap(weight, long_days, max_name_weight=0.3, reallocate=False)
    assert list(result) == [pytest.approx(0.3), pytest.approx(0.3), pytest.approx(0.2)]
    assert result.sum() == pytest.approx(0.8)  # excess dropped, not reallocated


def test_apply_name_cap_reallocates_via_water_fill() -> None:
    # 0.5/0.3/0.2 summing to 1.0, cap 0.3: name A (0.5) is pinned first: the
    # remaining 0.7 re-proposed between B/C (0.3/0.2 raw) gives B=0.42, which
    # is also over cap and gets pinned at 0.3; the last 0.4 all goes to C,
    # also over cap, pinned at 0.3. All three end up at the cap - 3*0.3=0.9,
    # not the full 1.0, since three names can't fit above a 0.3 cap each.
    long_days = pd.DataFrame({"date": ["2024-01-01"] * 3, "symbol": ["A", "B", "C"]})
    weight = pd.Series([0.5, 0.3, 0.2])
    result = _apply_name_cap(
        long_days=long_days, weight=weight, max_name_weight=0.3, reallocate=True
    )
    assert list(result) == [pytest.approx(0.3), pytest.approx(0.3), pytest.approx(0.3)]
    assert result.sum() == pytest.approx(0.9)


def test_name_cap_binds_on_a_low_breadth_day(monkeypatch: pytest.MonkeyPatch) -> None:
    # Only 2 names in the universe -> equal weight is 0.5 each, well above a
    # 30% per-name cap, and there's no sector cap in play (max_sector_weight
    # is None) so the name cap is the only thing doing anything here.
    df = _uptrend("2023-01-01", 400)
    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["A", "B"])
    monkeypatch.setattr(backtest_module, "load_price_history", lambda symbol: df)

    daily = daily_book_returns(
        params=TrendParams(fast=10, slow=50), max_sector_weight=None, max_name_weight=0.3
    )
    long_days = daily[daily["n_long"] > 0]
    assert not long_days.empty
    assert np.allclose(long_days["exposure"], 0.6)  # 0.3 cap x 2 names, not reallocated


def test_portfolio_summary_records_max_name_weight(monkeypatch: pytest.MonkeyPatch) -> None:
    df = _uptrend("2023-01-01", 400)
    monkeypatch.setattr(backtest_module, "full_universe", lambda: ["A", "B"])
    monkeypatch.setattr(backtest_module, "load_price_history", lambda symbol: df)

    result = portfolio_summary(
        params=TrendParams(fast=10, slow=50), max_sector_weight=None, max_name_weight=0.3
    )
    assert result.max_name_weight == 0.3
