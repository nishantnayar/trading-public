"""Backtest mechanics: trade timing, dollar neutrality, and cost accounting.

The critical test is `test_same_day_return_is_not_earned`. If weights are not lagged, the
portfolio earns the return of the bar used to select it, and the equity curve becomes
fiction. Everything else here is arithmetic that should be pinned so a refactor cannot
quietly change the P&L definition.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantis.backtest import portfolio as pf
from quantis.backtest.engine import (
    BPS,
    break_even_cost,
    daily_returns,
    performance,
    run_backtest,
)


@pytest.fixture
def predictions() -> pd.DataFrame:
    """40 symbols x 30 dates; `pred` ranks symbols consistently by index."""
    dates = pd.bdate_range("2024-01-01", periods=30)
    symbols = [f"S{i:02d}" for i in range(40)]
    rows = [
        {"date": date, "symbol": symbol, "pred": float(i)}
        for date in dates
        for i, symbol in enumerate(symbols)
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def weights(predictions: pd.DataFrame) -> pd.DataFrame:
    return pf.target_weights(predictions)


# --- construction ---------------------------------------------------------------


def test_portfolio_is_dollar_neutral(weights: pd.DataFrame) -> None:
    assert weights.sum(axis=1).abs().max() < 1e-12


def test_gross_exposure_is_one(weights: pd.DataFrame) -> None:
    assert weights.abs().sum(axis=1).max() == pytest.approx(1.0)


def test_quintile_legs_have_expected_membership(weights: pd.DataFrame) -> None:
    """40 names / 5 quantiles = 8 long and 8 short."""
    first = weights.iloc[0]
    assert (first > 0).sum() == 8
    assert (first < 0).sum() == 8


def test_highest_scores_are_long_and_lowest_short(weights: pd.DataFrame) -> None:
    first = weights.iloc[0]
    assert first["S39"] > 0  # top-ranked
    assert first["S00"] < 0  # bottom-ranked


def test_weights_only_change_on_rebalance_dates(weights: pd.DataFrame) -> None:
    """With a 5-day schedule, weights must be constant within each 5-day block."""
    changed = (weights.diff().abs().sum(axis=1) > 1e-12).to_numpy()
    changed[0] = False  # initial entry from flat
    assert not changed[1:5].any()
    assert not changed[6:10].any()


def test_thin_cross_section_yields_no_position() -> None:
    """Fewer than MIN_NAMES scores must produce a flat book, not a concentrated bet."""
    scores = pd.Series({f"S{i}": float(i) for i in range(6)})
    assert pf.leg_weights(scores).abs().sum() == 0.0


def test_construction_ignores_prediction_scale() -> None:
    """Ranking, not thresholding: scaling predictions must not change the portfolio."""
    dates = pd.bdate_range("2024-01-01", periods=10)
    base = pd.DataFrame(
        [{"date": d, "symbol": f"S{i:02d}", "pred": float(i)} for d in dates for i in range(30)]
    )
    scaled = base.assign(pred=base["pred"] * 1000.0 + 7.0)
    pd.testing.assert_frame_equal(pf.target_weights(base), pf.target_weights(scaled))


def test_exposure_report_confirms_neutrality(weights: pd.DataFrame) -> None:
    report = pf.exposure_report(weights)
    assert report["net"].abs().max() < 1e-12
    assert report["gross"].max() == pytest.approx(1.0)
    assert (report["n_long"] == 8).all()


def test_rebalance_dates_are_spaced(predictions: pd.DataFrame) -> None:
    dates = pd.Index(sorted(predictions["date"].unique()))
    schedule = pf.rebalance_dates(dates, every=5)
    assert len(schedule) == 6
    assert schedule[0] == dates[0]
    assert schedule[1] == dates[5]


# --- trade timing ---------------------------------------------------------------


def test_same_day_return_is_not_earned() -> None:
    """THE leakage test: a position must not earn the return of its own selection bar.

    Weights are non-zero only on date t; the only non-zero return is also on date t. A
    correctly lagged engine earns nothing, because on date t the *held* position is still
    yesterday's (flat).
    """
    dates = pd.bdate_range("2024-01-01", periods=4)
    symbols = ["A", "B"]

    w = pd.DataFrame(0.0, index=dates, columns=symbols)
    w.loc[dates[1]] = [0.5, -0.5]

    r = pd.DataFrame(0.0, index=dates, columns=symbols)
    r.loc[dates[1]] = [0.10, -0.10]  # a big move on the selection bar

    result = run_backtest(w, r, cost_bps_per_side=0.0)
    assert result.gross_returns.loc[dates[1]] == pytest.approx(0.0)
    assert result.gross_returns.abs().sum() == pytest.approx(0.0)


def test_position_earns_the_following_day_return() -> None:
    dates = pd.bdate_range("2024-01-01", periods=4)
    symbols = ["A", "B"]

    w = pd.DataFrame(0.0, index=dates, columns=symbols)
    w.loc[dates[1]] = [0.5, -0.5]
    w.loc[dates[2]] = [0.5, -0.5]  # still held

    r = pd.DataFrame(0.0, index=dates, columns=symbols)
    r.loc[dates[2]] = [0.10, -0.04]

    result = run_backtest(w, r, cost_bps_per_side=0.0)
    # 0.5 * 0.10 + (-0.5) * (-0.04)
    assert result.gross_returns.loc[dates[2]] == pytest.approx(0.07)


def test_shifting_predictions_forward_destroys_performance() -> None:
    """A signal that is one day stale should not beat the correctly timed one.

    This is a weaker but broader check that performance depends on timing at all.
    """
    dates = pd.bdate_range("2024-01-01", periods=60)
    symbols = [f"S{i:02d}" for i in range(30)]
    rng = np.random.default_rng(0)

    rets = pd.DataFrame(
        rng.normal(scale=0.01, size=(len(dates), len(symbols))),
        index=dates,
        columns=symbols,
    )
    # A perfect forecast of the NEXT day's return.
    perfect = rets.shift(-1)
    preds = perfect.stack(future_stack=True).rename("pred").reset_index()
    preds.columns = ["date", "symbol", "pred"]
    preds = preds.dropna()

    good = run_backtest(pf.target_weights(preds, every=1), rets, 0.0)
    stale = run_backtest(pf.target_weights(preds, every=1).shift(1).fillna(0.0), rets, 0.0)

    assert good.returns.sum() > stale.returns.sum()


# --- costs ----------------------------------------------------------------------


def test_entry_from_flat_costs_full_gross() -> None:
    """Going flat -> gross 1.0 trades 1.0 of notional, so cost = 1.0 * bps."""
    dates = pd.bdate_range("2024-01-01", periods=3)
    w = pd.DataFrame(0.0, index=dates, columns=["A", "B"])
    w.loc[dates[0]] = [0.5, -0.5]
    w.loc[dates[1]] = [0.5, -0.5]
    r = pd.DataFrame(0.0, index=dates, columns=["A", "B"])

    result = run_backtest(w, r, cost_bps_per_side=10.0)
    assert result.turnover.iloc[0] == pytest.approx(1.0)
    assert result.costs.iloc[0] == pytest.approx(10.0 * BPS)
    assert result.costs.iloc[1] == pytest.approx(0.0)  # held, no trade


def test_full_reversal_trades_twice_the_gross() -> None:
    dates = pd.bdate_range("2024-01-01", periods=2)
    w = pd.DataFrame(index=dates, columns=["A", "B"], dtype=float)
    w.loc[dates[0]] = [0.5, -0.5]
    w.loc[dates[1]] = [-0.5, 0.5]
    r = pd.DataFrame(0.0, index=dates, columns=["A", "B"])

    result = run_backtest(w, r, cost_bps_per_side=10.0)
    assert result.turnover.iloc[1] == pytest.approx(2.0)


def test_higher_costs_monotonically_reduce_returns(
    weights: pd.DataFrame, predictions: pd.DataFrame
) -> None:
    dates = weights.index
    rng = np.random.default_rng(1)
    r = pd.DataFrame(
        rng.normal(scale=0.01, size=(len(dates), len(weights.columns))),
        index=dates,
        columns=weights.columns,
    )

    totals = [run_backtest(weights, r, bps).returns.sum() for bps in (0.0, 5.0, 10.0, 20.0)]
    assert totals == sorted(totals, reverse=True)


def test_zero_cost_matches_gross(weights: pd.DataFrame) -> None:
    r = pd.DataFrame(0.01, index=weights.index, columns=weights.columns)
    result = run_backtest(weights, r, cost_bps_per_side=0.0)
    pd.testing.assert_series_equal(result.returns, result.gross_returns)


def test_negative_cost_is_rejected(weights: pd.DataFrame) -> None:
    r = pd.DataFrame(0.0, index=weights.index, columns=weights.columns)
    with pytest.raises(ValueError, match="cost must be >= 0"):
        run_backtest(weights, r, cost_bps_per_side=-1.0)


def test_break_even_cost_zeroes_the_strategy() -> None:
    """Running at the break-even rate must leave total gross P&L at ~0."""
    dates = pd.bdate_range("2024-01-01", periods=40)
    symbols = [f"S{i:02d}" for i in range(30)]
    rng = np.random.default_rng(3)

    rets = pd.DataFrame(
        rng.normal(scale=0.01, size=(len(dates), len(symbols))),
        index=dates,
        columns=symbols,
    )
    preds = rets.shift(-1).stack(future_stack=True).rename("pred").reset_index()
    preds.columns = ["date", "symbol", "pred"]
    w = pf.target_weights(preds.dropna(), every=5)

    bps = break_even_cost(w, rets)
    assert bps > 0
    at_break_even = run_backtest(w, rets, cost_bps_per_side=bps)
    assert abs(at_break_even.returns.sum()) < 1e-9


def test_non_overlapping_inputs_are_rejected() -> None:
    w = pd.DataFrame(0.0, index=pd.bdate_range("2024-01-01", periods=3), columns=["A"])
    r = pd.DataFrame(0.0, index=pd.bdate_range("2025-01-01", periods=3), columns=["B"])
    with pytest.raises(ValueError, match="do not overlap"):
        run_backtest(w, r)


# --- metrics --------------------------------------------------------------------


def test_daily_returns_from_adjusted_closes() -> None:
    close = pd.DataFrame({"A": [100.0, 110.0, 99.0]}, index=pd.bdate_range("2024-01-01", periods=3))
    out = daily_returns(close)
    assert np.isnan(out["A"].iloc[0])
    assert out["A"].iloc[1] == pytest.approx(0.10)
    assert out["A"].iloc[2] == pytest.approx(-0.10)


def test_performance_on_a_known_series() -> None:
    returns = pd.Series([0.01] * 252)
    stats = performance(returns)

    assert stats["n_days"] == 252
    assert stats["hit_rate"] == pytest.approx(1.0)
    assert stats["max_drawdown"] == pytest.approx(0.0)
    assert stats["cagr"] == pytest.approx((1.01**252) - 1, rel=1e-6)


def test_max_drawdown_is_measured_peak_to_trough() -> None:
    returns = pd.Series([0.5, -0.5, 0.0])  # 1.5 then 0.75 -> -50%
    assert performance(returns)["max_drawdown"] == pytest.approx(-0.5)


def test_sharpe_is_zero_for_flat_returns() -> None:
    assert np.isnan(performance(pd.Series([0.0] * 30))["sharpe"])


def test_performance_handles_empty_series() -> None:
    assert performance(pd.Series(dtype=float))["n_days"] == 0
