"""Feature correctness: hand-computed values against the vectorised implementations."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantis.features import definitions as fd


@pytest.fixture
def close() -> pd.DataFrame:
    """Two symbols, 300 sessions. AAA compounds steadily; BBB is flat then steps."""
    dates = pd.bdate_range("2024-01-01", periods=300)
    aaa = pd.Series(100.0 * (1.01 ** np.arange(300)), index=dates)
    bbb = pd.Series([50.0] * 150 + [75.0] * 150, index=dates)
    return pd.DataFrame({"AAA": aaa, "BBB": bbb})


@pytest.fixture
def volume(close: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(1_000_000.0, index=close.index, columns=close.columns)


def test_pct_change_matches_manual_ratio(close: pd.DataFrame) -> None:
    out = fd.pct_change_over(close, fd.MONTH)
    expected = close["AAA"].iloc[100] / close["AAA"].iloc[100 - fd.MONTH] - 1
    assert out["AAA"].iloc[100] == pytest.approx(expected)
    # 1% daily compounding over 21 sessions.
    assert out["AAA"].iloc[100] == pytest.approx(1.01**fd.MONTH - 1)


def test_momentum_12_1_skips_the_recent_month(close: pd.DataFrame) -> None:
    """The window must end one month back, not at t."""
    out = fd.momentum_12_1(close)
    i = 280
    expected = close["AAA"].iloc[i - fd.MONTH] / close["AAA"].iloc[i - fd.YEAR] - 1
    assert out["AAA"].iloc[i] == pytest.approx(expected)
    # Spans 252-21 = 231 sessions of 1% compounding.
    assert out["AAA"].iloc[i] == pytest.approx(1.01 ** (fd.YEAR - fd.MONTH) - 1)


def test_realised_vol_is_zero_for_constant_price(close: pd.DataFrame) -> None:
    """BBB is flat for its first 150 sessions, so trailing vol there is exactly 0."""
    out = fd.realised_vol(close, 20)
    assert out["BBB"].iloc[100] == pytest.approx(0.0)
    # Steady compounding is also zero-variance in log space.
    assert out["AAA"].iloc[100] == pytest.approx(0.0, abs=1e-9)


def test_realised_vol_annualises() -> None:
    dates = pd.bdate_range("2024-01-01", periods=60)
    rng = np.random.default_rng(0)
    prices = pd.DataFrame({"AAA": 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 60)))}, index=dates)

    out = fd.realised_vol(prices, 20)
    daily = np.log(prices / prices.shift(1)).rolling(20).std().iloc[-1, 0]
    assert out.iloc[-1, 0] == pytest.approx(daily * np.sqrt(fd.TRADING_DAYS))


def test_rsi_is_100_when_price_only_rises(close: pd.DataFrame) -> None:
    """No down days in the window means avg_loss is 0 and RSI saturates at 100."""
    out = fd.rsi(close, 14)
    assert out["AAA"].iloc[50] == pytest.approx(100.0)


def test_rsi_is_50_for_alternating_equal_moves() -> None:
    dates = pd.bdate_range("2024-01-01", periods=40)
    values = [100.0]
    for i in range(39):
        values.append(values[-1] + (1.0 if i % 2 == 0 else -1.0))
    frame = pd.DataFrame({"AAA": values}, index=dates)

    out = fd.rsi(frame, 14)
    assert out["AAA"].iloc[-1] == pytest.approx(50.0, abs=1e-6)


def test_rsi_stays_in_bounds(close: pd.DataFrame) -> None:
    out = fd.rsi(close, 14).stack()
    assert out.between(0.0, 100.0).all()


def test_distance_from_high_is_zero_at_a_new_high(close: pd.DataFrame) -> None:
    """AAA rises every day, so it is always at its own trailing high."""
    out = fd.distance_from_high(close)
    assert out["AAA"].iloc[-1] == pytest.approx(0.0)
    assert (out.stack() <= 1e-12).all()


def test_distance_from_high_is_negative_after_a_drawdown() -> None:
    dates = pd.bdate_range("2024-01-01", periods=300)
    values = list(np.linspace(100, 200, 150)) + list(np.linspace(200, 150, 150))
    frame = pd.DataFrame({"AAA": values}, index=dates)

    out = fd.distance_from_high(frame)
    assert out["AAA"].iloc[-1] == pytest.approx(150.0 / 200.0 - 1)


def test_ma_ratio_sign_tracks_trend(close: pd.DataFrame) -> None:
    out = fd.ma_ratio(close, 50, 200)
    assert out["AAA"].iloc[-1] > 0  # persistent uptrend
    assert out["BBB"].iloc[205] > 0  # just after the step up


def test_log_dollar_volume_matches_manual(close: pd.DataFrame, volume: pd.DataFrame) -> None:
    out = fd.log_dollar_volume(close, volume, 20)
    manual = (close["BBB"] * volume["BBB"]).rolling(20).mean().iloc[100]
    assert out["BBB"].iloc[100] == pytest.approx(np.log1p(manual))


def test_compute_all_returns_every_named_feature(
    close: pd.DataFrame, volume: pd.DataFrame
) -> None:
    computed = fd.compute_all(close, volume)
    assert set(computed) == set(fd.FEATURE_NAMES)
    for name, frame in computed.items():
        assert frame.shape == close.shape, name
        assert list(frame.columns) == list(close.columns), name


def test_warmup_rows_are_nan_not_zero(close: pd.DataFrame, volume: pd.DataFrame) -> None:
    """Before a window fills, features must be NaN — never a silently wrong 0."""
    computed = fd.compute_all(close, volume)
    assert computed["mom_12_1"]["AAA"].iloc[: fd.YEAR].isna().all()
    assert computed["vol_20d"]["AAA"].iloc[:19].isna().all()
    assert computed["ma_ratio_50_200"]["AAA"].iloc[:198].isna().all()
