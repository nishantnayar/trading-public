"""Point-in-time feature formulas.

Every function takes **wide** frames (index = date, columns = symbol) and returns a wide
frame of the same shape. Wide layout means one vectorised pandas call covers the whole
cross-section, and rolling windows can never bleed across symbols.

## The point-in-time contract

A feature dated `t` may use bars up to and including `t` — nothing after. Trading is
assumed at the next session, so `t`'s close is information available before the `t+1`
order. Two rules keep this true:

1. **No negative shifts.** `shift(-n)` looks into the future; only `shift(+n)` is allowed.
2. **No centred windows.** `rolling(..., center=True)` peeks forward; windows are
   trailing by default.

`tests/test_leakage.py` enforces both by construction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252

# Window lengths in trading days.
MONTH = 21
QUARTER = 63
HALF_YEAR = 126
YEAR = 252

FEATURE_NAMES = [
    "mom_1m",
    "mom_3m",
    "mom_6m",
    "mom_12_1",
    "ret_5d",
    "vol_20d",
    "vol_60d",
    "rsi_14",
    "dist_52w_high",
    "ma_ratio_50_200",
    "dollar_vol_20d",
]


def pct_change_over(close: pd.DataFrame, window: int) -> pd.DataFrame:
    """Simple return over `window` trailing sessions."""
    return close / close.shift(window) - 1.0


def momentum_12_1(close: pd.DataFrame) -> pd.DataFrame:
    """Classic 12-month momentum skipping the most recent month.

    Skipping the last month avoids contaminating the signal with short-term reversal,
    which is a distinct (and opposite-signed) effect.
    """
    return close.shift(MONTH) / close.shift(YEAR) - 1.0


def log_returns(close: pd.DataFrame) -> pd.DataFrame:
    return np.log(close / close.shift(1))


def realised_vol(close: pd.DataFrame, window: int) -> pd.DataFrame:
    """Annualised standard deviation of trailing daily log returns."""
    return log_returns(close).rolling(window).std() * np.sqrt(TRADING_DAYS)


def rsi(close: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """Relative Strength Index over a trailing simple-average window (0-100)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()
    # avg_loss == 0 -> RS is infinite -> RSI 100, which is the correct limit.
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    return out.where(avg_loss != 0.0, 100.0).where(avg_gain.notna())


def distance_from_high(close: pd.DataFrame, window: int = YEAR) -> pd.DataFrame:
    """Close relative to its trailing 52-week high; <= 0, with 0 meaning at the high."""
    return close / close.rolling(window).max() - 1.0


def ma_ratio(close: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.DataFrame:
    """Fast/slow moving-average ratio — a trend-regime proxy centred on 0."""
    return close.rolling(fast).mean() / close.rolling(slow).mean() - 1.0


def log_dollar_volume(close: pd.DataFrame, volume: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Log of average trailing dollar volume.

    NOTE: the free Alpaca IEX feed reports IEX-only volume, so the level is understated.
    It is understated consistently across names, so the cross-sectional ranking this
    model relies on stays meaningful. See docs/LIMITATIONS.md.
    """
    return np.log1p((close * volume).rolling(window).mean())


def compute_all(close: pd.DataFrame, volume: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Every feature as {name: wide frame}, keyed by FEATURE_NAMES."""
    return {
        "mom_1m": pct_change_over(close, MONTH),
        "mom_3m": pct_change_over(close, QUARTER),
        "mom_6m": pct_change_over(close, HALF_YEAR),
        "mom_12_1": momentum_12_1(close),
        "ret_5d": pct_change_over(close, 5),
        "vol_20d": realised_vol(close, 20),
        "vol_60d": realised_vol(close, 60),
        "rsi_14": rsi(close, 14),
        "dist_52w_high": distance_from_high(close),
        "ma_ratio_50_200": ma_ratio(close),
        "dollar_vol_20d": log_dollar_volume(close, volume),
    }
