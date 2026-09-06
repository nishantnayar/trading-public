"""Cross-sectional forward-return labels.

The target is the **forward** return z-scored **within each date**:

    label(symbol, t) = z_t( close(t + horizon) / close(t) - 1 )

Two deliberate choices:

1. **Forward-looking by design.** Unlike `features/definitions.py` — where any forward
   reference is a bug — a label *must* peek ahead; that is what supervision means. The
   danger is not computing it, it is (a) leaking it into a feature, or (b) letting
   overlapping label windows straddle a CV split. `models/cv.py` handles (b) by purging.

2. **Per-date z-score, not raw return.** De-meaning across the cross-section on each date
   strips out the market move, so the model learns *relative* strength instead of
   predicting market direction. This is what makes the long/short construction coherent:
   a stock's label answers "did it beat its peers this week", not "did it go up".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_HORIZON = 5  # trading days ~ one week, matching the weekly rebalance

# A z-score over a handful of names is noise. The universe is only populated from 2020
# (see docs/LIMITATIONS.md), so early dates are dropped rather than silently scored.
MIN_NAMES_PER_DATE = 20


def forward_return(close: pd.DataFrame, horizon: int = DEFAULT_HORIZON) -> pd.DataFrame:
    """Simple return from `t` to `t + horizon`, on a wide (date x symbol) frame.

    The trailing `horizon` rows are NaN — their future is not observed yet. That is
    correct and must not be filled: those dates are unlabelled, not zero-return.
    """
    if horizon < 1:
        raise ValueError(f"horizon must be >= 1, got {horizon}")
    return close.shift(-horizon) / close - 1.0


def cross_sectional_zscore(
    frame: pd.DataFrame,
    min_names: int = MIN_NAMES_PER_DATE,
    clip: float | None = 5.0,
) -> pd.DataFrame:
    """Z-score each row (date) across symbols.

    `clip` bounds the result in standard deviations; a single halted or acquired name can
    otherwise produce a 40-sigma label that dominates the gradient. Dates with fewer than
    `min_names` observations are returned as all-NaN.
    """
    counts = frame.notna().sum(axis=1)
    mean = frame.mean(axis=1)
    # ddof=0: this is the population spread of the observed cross-section, not a sample
    # estimate of a wider one.
    std = frame.std(axis=1, ddof=0)

    scored = frame.sub(mean, axis=0).div(std.replace(0.0, np.nan), axis=0)
    scored = scored.where(counts >= min_names)
    if clip is not None:
        scored = scored.clip(-clip, clip)
    return scored


def make_labels(
    close: pd.DataFrame,
    horizon: int = DEFAULT_HORIZON,
    min_names: int = MIN_NAMES_PER_DATE,
    clip: float | None = 5.0,
) -> pd.DataFrame:
    """Wide frame of per-date z-scored forward returns."""
    return cross_sectional_zscore(
        forward_return(close, horizon), min_names=min_names, clip=clip
    )


def to_long(labels: pd.DataFrame, name: str = "label") -> pd.DataFrame:
    """Wide labels -> long (symbol, date, label), dropping unlabelled rows."""
    long = (
        labels.stack(future_stack=True)
        .rename(name)
        .reset_index()
        .rename(columns={"level_0": "date", "level_1": "symbol"})
    )
    return long.dropna(subset=[name]).reset_index(drop=True)
