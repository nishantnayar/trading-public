"""Turn cross-sectional predictions into a dollar-neutral long/short weight matrix.

Construction, per the Phase 5 decisions:

- **Weekly rebalance** (every 5th session), matching the 5-day label horizon, so a
  position is held for exactly as long as the forecast it is based on applies.
- **Top quintile long, bottom quintile short, equal-weight** within each leg. This is
  the portfolio the `q_spread` metric describes, so backtest and model diagnostics stay
  directly comparable.
- **Dollar-neutral**: each leg carries half the gross, so weights sum to 0 and absolute
  weights sum to 1.
- **Phase 6 levers** (off by default, so Phase 5 results stay reproducible):
  - `buffer`: extra quantile-widths an incumbent may occupy before it is evicted.
  - `sectors`: build the same book *inside* each GICS sector, then rescale to unit gross.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_QUANTILES = 5
REBALANCE_EVERY = 5
GROSS_EXPOSURE = 1.0

# Below this, quintiles are too thin to diversify: a "quintile" of three names is a
# concentrated bet, not a cross-sectional portfolio.
MIN_NAMES = 20


def rebalance_dates(dates: pd.Index, every: int = REBALANCE_EVERY) -> pd.Index:
    """Every `every`-th session, starting from the first available date."""
    if every < 1:
        raise ValueError(f"every must be >= 1, got {every}")
    ordered = pd.Index(sorted(pd.unique(dates)))
    return ordered[::every]


def leg_weights(
    scores: pd.Series,
    quantiles: int = DEFAULT_QUANTILES,
    gross: float = GROSS_EXPOSURE,
    min_names: int = MIN_NAMES,
) -> pd.Series:
    """Weights for one date: +gross/2 spread over the top quantile, -gross/2 the bottom.

    Ties are broken by `rank(method="first")` so exactly `n/quantiles` names land in each
    bucket; ranking rather than thresholding also makes the construction invariant to the
    prediction's scale, which matters because model output is not calibrated.
    """
    available = scores.dropna()
    if len(available) < max(min_names, quantiles * 2):
        return pd.Series(0.0, index=scores.index)

    buckets = pd.qcut(available.rank(method="first"), quantiles, labels=False)
    longs = available.index[buckets == quantiles - 1]
    shorts = available.index[buckets == 0]

    weights = pd.Series(0.0, index=scores.index)
    weights[longs] = (gross / 2) / len(longs)
    weights[shorts] = -(gross / 2) / len(shorts)
    return weights


def _equal_legs(index: pd.Index, longs: list, shorts: list, gross: float) -> pd.Series:
    """Equal-weight a chosen long and short list onto `index`."""
    weights = pd.Series(0.0, index=index)
    if longs:
        weights[longs] = (gross / 2) / len(longs)
    if shorts:
        weights[shorts] = -(gross / 2) / len(shorts)
    return weights


def buffered_legs(
    scores: pd.Series,
    previous: pd.Series | None = None,
    quantiles: int = DEFAULT_QUANTILES,
    buffer: int = 0,
    gross: float = GROSS_EXPOSURE,
    min_names: int = MIN_NAMES,
) -> pd.Series:
    """Quintile legs with a no-trade band around the cutoff.

    `buffer=0` is the Phase 5 book: top/bottom quantile, no memory. `buffer=1` lets a
    name stay long while it remains in the top *two* quantiles (and stay short in the
    bottom two). Slots freed by evictions are filled from the current extreme; incumbents
    still inside the band are never sold just because a new name ranked one place higher.

    Book size stays fixed at `n // quantiles` per leg — the buffer changes *who* occupies
    the slots, not how many slots there are.
    """
    if buffer < 0:
        raise ValueError(f"buffer must be >= 0, got {buffer}")

    available = scores.dropna()
    if len(available) < max(min_names, quantiles * 2):
        return pd.Series(0.0, index=scores.index)

    n_leg = len(available) // quantiles
    ranks = available.rank(method="first")
    long_floor = len(available) - n_leg * (1 + buffer)
    short_ceiling = n_leg * (1 + buffer)
    in_long_band = set(ranks.index[ranks > long_floor])
    in_short_band = set(ranks.index[ranks <= short_ceiling])

    prev_long: set[str] = set()
    prev_short: set[str] = set()
    if previous is not None:
        aligned = previous.reindex(available.index).fillna(0.0)
        prev_long = set(aligned.index[aligned > 0])
        prev_short = set(aligned.index[aligned < 0])

    keep_long = [s for s in prev_long if s in in_long_band]
    keep_short = [s for s in prev_short if s in in_short_band]

    taken = set(keep_long) | set(keep_short)
    for symbol in ranks.sort_values(ascending=False).index:
        if len(keep_long) >= n_leg:
            break
        if symbol not in taken:
            keep_long.append(symbol)
            taken.add(symbol)
    for symbol in ranks.sort_values(ascending=True).index:
        if len(keep_short) >= n_leg:
            break
        if symbol not in taken:
            keep_short.append(symbol)
            taken.add(symbol)

    return _equal_legs(scores.index, keep_long[:n_leg], keep_short[:n_leg], gross)


def sector_neutral_weights(
    scores: pd.Series,
    sectors: pd.Series,
    previous: pd.Series | None = None,
    quantiles: int = DEFAULT_QUANTILES,
    buffer: int = 0,
    gross: float = GROSS_EXPOSURE,
    min_names: int = 10,
) -> pd.Series:
    """Dollar-neutral *inside each sector*, then rescale so total gross is `gross`.

    A sector with fewer than `min_names` scored members is left flat rather than turned
    into a two- or three-name concentrated bet. Sectors are combined with equal gross
    *per name remaining*, so a 70-name sector still carries more weight than a 15-name
    one — we neutralize the *tilt*, not the sector's share of the universe.
    """
    aligned = sectors.reindex(scores.index)
    parts: list[pd.Series] = []
    for sector in aligned.dropna().unique():
        members = aligned.index[aligned == sector]
        sector_scores = scores.loc[members]
        sector_prev = previous.reindex(members) if previous is not None else None
        part = buffered_legs(
            sector_scores,
            previous=sector_prev,
            quantiles=quantiles,
            buffer=buffer,
            gross=1.0,
            min_names=min_names,
        )
        if part.abs().sum() > 0:
            parts.append(part)

    combined = pd.Series(0.0, index=scores.index)
    if not parts:
        return combined
    stacked = pd.concat(parts)
    combined.loc[stacked.index] = stacked
    scale = combined.abs().sum()
    if scale > 0:
        combined *= gross / scale
    return combined


def target_weights(
    predictions: pd.DataFrame,
    quantiles: int = DEFAULT_QUANTILES,
    every: int = REBALANCE_EVERY,
    gross: float = GROSS_EXPOSURE,
    min_names: int = MIN_NAMES,
    pred_column: str = "pred",
    buffer: int = 0,
    sectors: pd.Series | None = None,
) -> pd.DataFrame:
    """Long predictions -> daily weight matrix (date x symbol).

    Weights are set on rebalance dates and **held** (forward-filled) in between, which is
    what makes turnover — and therefore cost — a function of the rebalance schedule
    rather than of daily prediction noise.

    `buffer=0` and `sectors=None` is the Phase 5 constructor (no memory, no
    neutralization). Either lever switches to a sequential pass so yesterday's book can
    inform today's.
    """
    wide = predictions.pivot(index="date", columns="symbol", values=pred_column)
    wide = wide.sort_index()
    schedule = rebalance_dates(wide.index, every)

    if buffer == 0 and sectors is None:
        rows = {date: leg_weights(wide.loc[date], quantiles, gross, min_names) for date in schedule}
    else:
        rows = {}
        previous: pd.Series | None = None
        for date in schedule:
            scores = wide.loc[date]
            if sectors is None:
                previous = buffered_legs(scores, previous, quantiles, buffer, gross, min_names)
            else:
                previous = sector_neutral_weights(
                    scores, sectors, previous, quantiles, buffer, gross
                )
            rows[date] = previous

    sparse = pd.DataFrame(rows).T.reindex(columns=wide.columns)
    held = sparse.reindex(wide.index).ffill().fillna(0.0)
    held.index.name = "date"
    return held


def exposure_report(weights: pd.DataFrame, sectors: pd.Series | None = None) -> pd.DataFrame:
    """Per-date gross/net exposure, name counts, and optional sector tilt.

    Net exposure should sit at ~0 by construction; this exists so that claim is checked
    against the actual matrix rather than assumed.
    """
    report = pd.DataFrame(
        {
            "gross": weights.abs().sum(axis=1),
            "net": weights.sum(axis=1),
            "n_long": (weights > 0).sum(axis=1),
            "n_short": (weights < 0).sum(axis=1),
        }
    )
    if sectors is not None:
        aligned = sectors.reindex(weights.columns)
        for sector in sorted(aligned.dropna().unique()):
            members = aligned.index[aligned == sector]
            report[f"net_{sector}"] = weights[members].sum(axis=1)
    return report


def turnover(weights: pd.DataFrame) -> pd.Series:
    """One-sided traded notional per date: sum |w(t) - w(t-1)|.

    The first date counts as a full entry from flat, which is correct — that trade really
    does happen and really does cost.
    """
    previous = weights.shift(1).fillna(0.0)
    return (weights - previous).abs().sum(axis=1)


def annualised_turnover(weights: pd.DataFrame, sessions_per_year: int = 252) -> float:
    """Average one-sided turnover per year, as a multiple of gross exposure."""
    daily = turnover(weights)
    return float(np.nan if daily.empty else daily.mean() * sessions_per_year)
