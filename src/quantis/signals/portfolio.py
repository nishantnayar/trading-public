"""Equal-weight portfolio construction: turn per-symbol long/flat calls into
one book and backtest *that*, instead of only ever looking at per-symbol
totals.

Motivation (see docs/LIMITATIONS.md "Signal (v1)"): the per-symbol median net
return across the full universe is negative, but the day-by-day return of an
equal-weighted book of whatever names are currently long is net-positive most
years. Those aren't contradictory — diversification across many concurrently
long names smooths the whipsaw/cost drag that dominates any single
undiversified symbol. This module is the book-level backtest that number
implies but `regime_breakdown` (year-by-year only) didn't compute in full:
one continuous equity curve, Sharpe, max drawdown, and an annualized turnover
estimate over the whole period.

Construction: equal weight across every name currently signaled long,
rebalanced daily (a name added/dropped from the long book that day
enters/exits at 1/N of whatever N is that day), with a default 15% GICS
sector cap whose freed weight is reallocated to under-cap sectors
(`DEFAULT_MAX_SECTOR_WEIGHT`, `DEFAULT_REALLOCATE`) rather than left
uninvested. Chosen after comparing cap levels and reallocation on/off against
the live universe: at 15% (where multiple sectors bind at once) reallocation
meaningfully improves CAGR/Sharpe/exposure over leaving the freed weight
idle; at a looser 25% cap it barely matters, since few sectors bind that
hard. See docs/LIMITATIONS.md and docs/PROGRESS.md (Phases 16-17) for the
comparison. Pass `max_sector_weight=None` for pure equal-weight, or
`reallocate=False` for the single-pass (no-reallocation) cap. No per-name
cap, no vol targeting — see docs/LIMITATIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantis.db.engine import session_scope
from quantis.db.models import PortfolioSnapshot
from quantis.signals.backtest import (
    DEFAULT_COST_BPS_PER_SIDE,
    _annualized_sharpe,
    _symbol_sectors,
    universe_daily_frame,
)
from quantis.signals.rules import TrendParams

DEFAULT_MAX_SECTOR_WEIGHT = 0.15
DEFAULT_REALLOCATE = True


@dataclass(frozen=True)
class PortfolioResult:
    start: str
    end: str
    total_return: float
    cagr: float
    ann_vol: float
    sharpe: float
    max_drawdown: float
    avg_names_long: float
    avg_exposure: float
    annualized_turnover: float
    trading_days: int
    max_sector_weight: float | None = None
    reallocated: bool = False


def _water_fill_sector_weights(counts: pd.Series, cap: float) -> pd.Series:
    """One day's final sector weights: proportional to each sector's share of
    names, capped, with freed weight reallocated proportionally among
    still-under-cap sectors until nothing is left over cap.

    `counts` is sector -> number of long names in that sector (one day).
    Standard iterative proportional capping ("water-filling"): propose
    weights proportional to `counts` summing to whatever total remains
    unallocated (1.0 initially); any sector over `cap` is pinned there and
    removed from the pool; the remaining total is re-proposed among what's
    left. Converges in at most `len(counts)` passes since each pass pins at
    least one more sector. If every present sector is pinned at the cap
    before the total is fully allocated (e.g. more sectors present than
    `1/cap` can hold at cap - overlapping ties aside), the leftover is
    genuinely un-investable under the constraint and stays as cash, not an
    error.
    """
    raw_share = counts / counts.sum()
    remaining = set(counts.index)
    weights: dict[str, float] = {}
    total_to_allocate = 1.0
    while remaining:
        share_sum = raw_share.loc[list(remaining)].sum()
        proposed = {s: total_to_allocate * raw_share[s] / share_sum for s in remaining}
        over_cap = [s for s in remaining if proposed[s] > cap + 1e-12]
        if not over_cap:
            weights.update(proposed)
            break
        for s in over_cap:
            weights[s] = cap
            total_to_allocate -= cap
            remaining.discard(s)
    return pd.Series(weights)


def _capped_weights(
    all_days: pd.DataFrame,
    long_days: pd.DataFrame,
    max_sector_weight: float | None,
    reallocate: bool = False,
) -> pd.Series:
    """Per-(date, symbol) portfolio weight, equal-weighted within the day's
    long names and capped by GICS sector.

    Uncapped: weight = 1 / (names long that day).

    Capped, `reallocate=False` (the default): any sector whose uncapped total
    would exceed `max_sector_weight` is scaled down to exactly the cap; its
    names split that fixed share equally among themselves. The freed weight
    is *not* reallocated to other sectors - a capped day is a smaller,
    less-than-fully-invested book, not a fully-invested one with different
    proportions.

    Capped, `reallocate=True`: freed weight from over-cap sectors is instead
    redistributed proportionally among still-under-cap sectors, iterating
    until no sector exceeds the cap (`_water_fill_sector_weights`) - a real
    allocator's likely behavior, at the cost of needing that iterative pass
    per day instead of one vectorized scale-down. See docs/LIMITATIONS.md.
    """
    equal_weight = 1.0 / long_days.groupby("date")["symbol"].transform("size")
    if max_sector_weight is None:
        return equal_weight

    sectors = _symbol_sectors(list(all_days["symbol"].unique()))
    sector = long_days["symbol"].map(sectors).fillna("Unknown")

    if not reallocate:
        sector_total = equal_weight.groupby([long_days["date"], sector]).transform("sum")
        scale = np.where(sector_total > max_sector_weight, max_sector_weight / sector_total, 1.0)
        return equal_weight * scale

    counts = long_days.assign(sector=sector).groupby(["date", "sector"]).size()
    sector_weight_by_day: dict[object, float] = {}
    for date, day_counts in counts.groupby(level=0):
        day_counts = day_counts.droplevel(0)
        for s, w in _water_fill_sector_weights(day_counts, max_sector_weight).items():
            sector_weight_by_day[(date, s)] = w / day_counts[s]

    keys = list(zip(long_days["date"], sector, strict=True))
    return pd.Series([sector_weight_by_day[k] for k in keys], index=long_days.index)


def daily_book_returns(
    symbols: list[str] | None = None,
    params: TrendParams | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
    max_sector_weight: float | None = DEFAULT_MAX_SECTOR_WEIGHT,
    reallocate: bool = DEFAULT_REALLOCATE,
) -> pd.DataFrame:
    """One row per trading day: weighted net/gross return of every
    currently-long name that day (equal-weight, or sector-capped if
    `max_sector_weight` is set — see `_capped_weights`), breadth (`n_long`),
    invested exposure that day (`exposure`, 1.0 unless sector-capped without
    reallocation), and how many names changed position (`n_trades`). A flat
    day (nothing long) earns 0, not NaN.
    """
    all_days = universe_daily_frame(symbols, params, cost_bps_per_side)
    if all_days.empty:
        return pd.DataFrame(
            columns=["date", "net_return", "gross_return", "n_long", "exposure", "n_trades"]
        )

    long_days = all_days[all_days["position"]].copy()
    full_index = pd.Index(sorted(all_days["date"].unique()))

    weight = _capped_weights(all_days, long_days, max_sector_weight, reallocate)
    weighted_net = (weight * long_days["net_return"]).groupby(long_days["date"]).sum()
    weighted_gross = (weight * long_days["gross_return"]).groupby(long_days["date"]).sum()
    exposure = weight.groupby(long_days["date"]).sum()

    net_return = weighted_net.reindex(full_index, fill_value=0.0)
    gross_return = weighted_gross.reindex(full_index, fill_value=0.0)
    exposure = exposure.reindex(full_index, fill_value=0.0)
    n_long = long_days.groupby("date").size().reindex(full_index, fill_value=0)
    n_trades = all_days.groupby("date")["trade_flag"].sum().reindex(full_index, fill_value=0)

    return pd.DataFrame(
        {
            "date": full_index,
            "net_return": net_return.to_numpy(),
            "gross_return": gross_return.to_numpy(),
            "n_long": n_long.to_numpy(),
            "exposure": exposure.to_numpy(),
            "n_trades": n_trades.to_numpy(),
        }
    )


def portfolio_summary(
    symbols: list[str] | None = None,
    params: TrendParams | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
    max_sector_weight: float | None = DEFAULT_MAX_SECTOR_WEIGHT,
    reallocate: bool = DEFAULT_REALLOCATE,
) -> PortfolioResult:
    """Full-period backtest of the book (see module docstring for the default
    construction). Pass `max_sector_weight=None` for pure equal-weight, or
    `reallocate=False` to leave a capped sector's freed weight uninvested
    instead of redistributing it - see `_capped_weights`."""
    daily = daily_book_returns(symbols, params, cost_bps_per_side, max_sector_weight, reallocate)
    net_return = daily["net_return"]
    n_days = len(daily)
    n_years = n_days / 252

    equity = (1 + net_return).cumprod()
    total_return = float(equity.iloc[-1] - 1) if n_days else 0.0
    cagr = float(equity.iloc[-1] ** (1 / n_years) - 1) if n_days and n_years > 0 else 0.0
    ann_vol = float(net_return.std(ddof=0) * np.sqrt(252)) if n_days else 0.0
    sharpe = _annualized_sharpe(net_return) if n_days else 0.0
    drawdown = equity / equity.cummax() - 1 if n_days else pd.Series([0.0])
    max_drawdown = float(drawdown.min()) if n_days else 0.0
    avg_names_long = float(daily["n_long"].mean()) if n_days else 0.0
    avg_exposure = float(daily["exposure"].mean()) if n_days else 0.0

    # Total position-change events across the universe, expressed as a
    # multiple of the book's average size, annualized. A name that enters and
    # exits once a year (2 events), held as 1 of `avg_names_long` names,
    # contributes ~1x/year of turnover under this convention.
    total_trades = float(daily["n_trades"].sum())
    annualized_turnover = (
        (total_trades / (2 * avg_names_long)) / n_years
        if n_days and avg_names_long > 0 and n_years > 0
        else 0.0
    )

    return PortfolioResult(
        start=str(daily["date"].iloc[0]) if n_days else "",
        end=str(daily["date"].iloc[-1]) if n_days else "",
        total_return=total_return,
        cagr=cagr,
        ann_vol=ann_vol,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        avg_names_long=avg_names_long,
        avg_exposure=avg_exposure,
        annualized_turnover=annualized_turnover,
        trading_days=n_days,
        max_sector_weight=max_sector_weight,
        reallocated=reallocate,
    )


def _parse_date(value: str) -> object | None:
    return pd.to_datetime(value).date() if value else None


def persist_portfolio_summary(result: PortfolioResult | None = None) -> None:
    """Replace the single `portfolio_snapshots` row with `result` (or a fresh
    `portfolio_summary()` using the defaults - see module docstring).

    One row, not history: each call overwrites the prior snapshot, same
    convention as `quantis.signals.engine.persist_latest_signals` uses for
    `signals`.
    """
    result = result or portfolio_summary()
    with session_scope() as session:
        session.query(PortfolioSnapshot).delete()
        session.add(
            PortfolioSnapshot(
                period_start=_parse_date(result.start),
                period_end=_parse_date(result.end),
                trading_days=result.trading_days,
                total_return=result.total_return,
                cagr=result.cagr,
                ann_vol=result.ann_vol,
                sharpe=result.sharpe,
                max_drawdown=result.max_drawdown,
                avg_names_long=result.avg_names_long,
                avg_exposure=result.avg_exposure,
                annualized_turnover=result.annualized_turnover,
                max_sector_weight=result.max_sector_weight,
                reallocated=result.reallocated,
            )
        )
