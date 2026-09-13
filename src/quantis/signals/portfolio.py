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
`reallocate=False` for the single-pass (no-reallocation) cap.

A per-name cap (`max_name_weight`, off by default - see `_apply_name_cap`) can
also be applied, on top of the sector cap. Tried at a couple of levels against
the live universe: it made every metric fractionally worse, never better, for
the same reason `vol_target` did below - kept off by default rather than
shipped just to say the knob exists. See docs/LIMITATIONS.md and
docs/PROGRESS.md (Phase 21).

Optional volatility targeting (`vol_target`, off by default - see
`_vol_target_leverage`) scales the whole book's daily return by
`target / trailing realized vol`, capped at `max_leverage`, using only
information available the prior day. This is a leverage overlay on top of
the construction above, not a replacement for it - no margin, financing, or
execution is modeled, so treat it as "what a levered version of this book
would have returned," not an investable instruction. See docs/LIMITATIONS.md
(Phase 20).
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
from quantis.signals.engine import latest_signals
from quantis.signals.rules import TrendParams

DEFAULT_MAX_SECTOR_WEIGHT = 0.15
DEFAULT_REALLOCATE = True
DEFAULT_MAX_NAME_WEIGHT: float | None = None  # off by default - see module docstring
DEFAULT_VOL_TARGET: float | None = None  # off by default - see module docstring
DEFAULT_VOL_LOOKBACK_DAYS = 20
DEFAULT_MAX_LEVERAGE = 1.5


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
    max_name_weight: float | None = None
    vol_target: float | None = None
    avg_leverage: float = 1.0


def _water_fill(shares: pd.Series, cap: float, total: float = 1.0) -> pd.Series:
    """Distribute `total` proportional to `shares`, capping each entry at
    `cap`, with anything freed by a capped entry reallocated proportionally
    among the still-under-cap entries ("water-filling").

    `shares` need not be normalized or represent counts specifically - any
    positive numbers proportional to what each entry should get before
    capping (raw name counts for the sector cap, or each name's own current
    weight for the per-name cap). Standard iterative proportional capping:
    propose amounts proportional to `shares` summing to whatever total
    remains unallocated (`total` initially); anything over `cap` is pinned
    there and removed from the pool; the remaining total is re-proposed among
    what's left. Converges in at most `len(shares)` passes since each pass
    pins at least one more entry. If every entry ends up pinned at the cap
    before `total` is fully allocated, the leftover is genuinely
    un-investable under the constraint and stays as cash, not an error.
    """
    raw_share = shares / shares.sum()
    remaining = set(shares.index)
    weights: dict[object, float] = {}
    total_to_allocate = total
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


def _water_fill_sector_weights(counts: pd.Series, cap: float) -> pd.Series:
    """`_water_fill` specialized to the sector cap: `counts` is sector ->
    number of long names in that sector (one day), starting from the full
    1.0 of book weight. Kept as a thin wrapper for readability at call sites.
    """
    return _water_fill(counts, cap, total=1.0)


def _apply_name_cap(
    weight: pd.Series,
    long_days: pd.DataFrame,
    max_name_weight: float | None,
    reallocate: bool,
) -> pd.Series:
    """Cap each individual name's weight at `max_name_weight`, applied *after*
    the sector cap (so it only binds on top of whatever the sector logic
    already produced - a name near a sector's cap can still end up capped
    again here if it's a large share of a small sector, or of a low-breadth
    day where equal-weight itself exceeds `max_name_weight`).

    `reallocate=False`: a straight clip - excess is dropped, not reallocated.
    `reallocate=True`: excess from over-cap names is redistributed to
    under-cap names that same day via `_water_fill`, using each name's
    current weight as its share and the day's *actual* current total (which
    may be < 1.0 if the sector cap already left some of the book uninvested)
    rather than assuming a full 1.0 to allocate.
    """
    if max_name_weight is None:
        return weight
    if not reallocate:
        return weight.clip(upper=max_name_weight)

    df = pd.DataFrame(
        {
            "date": long_days["date"].to_numpy(),
            "symbol": long_days["symbol"].to_numpy(),
            "weight": weight.to_numpy(),
        }
    )
    result_by_key: dict[tuple, float] = {}
    for date, group in df.groupby("date"):
        total = float(group["weight"].sum())
        if total <= 0:
            continue
        shares = group.set_index("symbol")["weight"]
        for symbol, w in _water_fill(shares, cap=max_name_weight, total=total).items():
            result_by_key[(date, symbol)] = w

    keys = list(zip(long_days["date"], long_days["symbol"], strict=True))
    return pd.Series([result_by_key[k] for k in keys], index=weight.index)


def _capped_weights(
    all_days: pd.DataFrame,
    long_days: pd.DataFrame,
    max_sector_weight: float | None,
    reallocate: bool = False,
    max_name_weight: float | None = None,
) -> pd.Series:
    """Per-(date, symbol) portfolio weight, equal-weighted within the day's
    long names, capped by GICS sector, then capped per individual name.

    Uncapped: weight = 1 / (names long that day).

    Sector-capped, `reallocate=False` (the default): any sector whose
    uncapped total would exceed `max_sector_weight` is scaled down to exactly
    the cap; its names split that fixed share equally among themselves. The
    freed weight is *not* reallocated to other sectors - a capped day is a
    smaller, less-than-fully-invested book, not a fully-invested one with
    different proportions.

    Sector-capped, `reallocate=True`: freed weight from over-cap sectors is
    instead redistributed proportionally among still-under-cap sectors,
    iterating until no sector exceeds the cap (`_water_fill_sector_weights`)
    - a real allocator's likely behavior, at the cost of needing that
    iterative pass per day instead of one vectorized scale-down.

    `max_name_weight`, if set, is then applied on top via `_apply_name_cap`
    - see docs/LIMITATIONS.md for why sector-then-name (rather than a single
    joint optimization) is a deliberate simplification, not an oversight.
    """
    equal_weight = 1.0 / long_days.groupby("date")["symbol"].transform("size")
    if max_sector_weight is None:
        weight = equal_weight
    else:
        sectors = _symbol_sectors(list(all_days["symbol"].unique()))
        sector = long_days["symbol"].map(sectors).fillna("Unknown")

        if not reallocate:
            sector_total = equal_weight.groupby([long_days["date"], sector]).transform("sum")
            scale = np.where(
                sector_total > max_sector_weight, max_sector_weight / sector_total, 1.0
            )
            weight = equal_weight * scale
        else:
            counts = long_days.assign(sector=sector).groupby(["date", "sector"]).size()
            sector_weight_by_day: dict[object, float] = {}
            for date, day_counts in counts.groupby(level=0):
                day_counts = day_counts.droplevel(0)
                for s, w in _water_fill_sector_weights(day_counts, max_sector_weight).items():
                    sector_weight_by_day[(date, s)] = w / day_counts[s]
            keys = list(zip(long_days["date"], sector, strict=True))
            weight = pd.Series([sector_weight_by_day[k] for k in keys], index=long_days.index)

    return _apply_name_cap(weight, long_days, max_name_weight, reallocate)


def _vol_target_leverage(
    net_return: pd.Series,
    target_vol: float,
    lookback: int,
    max_leverage: float,
) -> pd.Series:
    """Daily leverage multiplier: `target_vol / trailing realized vol`, capped
    at `max_leverage` and floored at 0 (never short the book to hit a vol
    target).

    Trailing vol is the rolling `lookback`-day std of `net_return` as of
    *yesterday* (`.shift(1)`) so today's scale never uses today's own return -
    no look-ahead. Before enough history exists (first `lookback` days) or
    whenever trailing vol is exactly 0 (nothing was long), leverage defaults
    to 1.0 - unscaled, not "no position."
    """
    trailing_vol = net_return.rolling(lookback).std(ddof=0) * np.sqrt(252)
    trailing_vol = trailing_vol.shift(1)
    leverage = target_vol / trailing_vol
    leverage = leverage.replace([np.inf, -np.inf], np.nan)
    return leverage.clip(lower=0.0, upper=max_leverage).fillna(1.0)


def daily_book_returns(
    symbols: list[str] | None = None,
    params: TrendParams | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
    max_sector_weight: float | None = DEFAULT_MAX_SECTOR_WEIGHT,
    reallocate: bool = DEFAULT_REALLOCATE,
    max_name_weight: float | None = DEFAULT_MAX_NAME_WEIGHT,
    vol_target: float | None = DEFAULT_VOL_TARGET,
    vol_lookback_days: int = DEFAULT_VOL_LOOKBACK_DAYS,
    max_leverage: float = DEFAULT_MAX_LEVERAGE,
) -> pd.DataFrame:
    """One row per trading day: weighted net/gross return of every
    currently-long name that day (equal-weight, sector-capped if
    `max_sector_weight` is set, then name-capped if `max_name_weight` is set
    — see `_capped_weights`), breadth (`n_long`), invested exposure that day
    (`exposure`, 1.0 unless a cap left the book less than fully invested),
    the day's leverage multiplier (`leverage`, 1.0 unless `vol_target` is set
    — see `_vol_target_leverage`), and how many names changed position
    (`n_trades`). A flat day (nothing long) earns 0, not NaN.

    Vol targeting is applied on top of the (already sector/name-capped)
    return series — it rescales the whole book's exposure by trailing
    realized vol, it doesn't touch the per-name weights within a day.
    """
    all_days = universe_daily_frame(symbols, params, cost_bps_per_side)
    if all_days.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "net_return",
                "gross_return",
                "n_long",
                "exposure",
                "leverage",
                "n_trades",
            ]
        )

    long_days = all_days[all_days["position"]].copy()
    full_index = pd.Index(sorted(all_days["date"].unique()))

    weight = _capped_weights(all_days, long_days, max_sector_weight, reallocate, max_name_weight)
    weighted_net = (weight * long_days["net_return"]).groupby(long_days["date"]).sum()
    weighted_gross = (weight * long_days["gross_return"]).groupby(long_days["date"]).sum()
    exposure = weight.groupby(long_days["date"]).sum()

    net_return = weighted_net.reindex(full_index, fill_value=0.0)
    gross_return = weighted_gross.reindex(full_index, fill_value=0.0)
    exposure = exposure.reindex(full_index, fill_value=0.0)
    n_long = long_days.groupby("date").size().reindex(full_index, fill_value=0)
    n_trades = all_days.groupby("date")["trade_flag"].sum().reindex(full_index, fill_value=0)

    if vol_target is not None:
        leverage = _vol_target_leverage(net_return, vol_target, vol_lookback_days, max_leverage)
        net_return = net_return * leverage
        gross_return = gross_return * leverage
        exposure = exposure * leverage
    else:
        leverage = pd.Series(1.0, index=full_index)

    return pd.DataFrame(
        {
            "date": full_index,
            "net_return": net_return.to_numpy(),
            "gross_return": gross_return.to_numpy(),
            "n_long": n_long.to_numpy(),
            "exposure": exposure.to_numpy(),
            "leverage": leverage.to_numpy(),
            "n_trades": n_trades.to_numpy(),
        }
    )


def portfolio_summary(
    symbols: list[str] | None = None,
    params: TrendParams | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
    max_sector_weight: float | None = DEFAULT_MAX_SECTOR_WEIGHT,
    reallocate: bool = DEFAULT_REALLOCATE,
    max_name_weight: float | None = DEFAULT_MAX_NAME_WEIGHT,
    vol_target: float | None = DEFAULT_VOL_TARGET,
    vol_lookback_days: int = DEFAULT_VOL_LOOKBACK_DAYS,
    max_leverage: float = DEFAULT_MAX_LEVERAGE,
) -> PortfolioResult:
    """Full-period backtest of the book (see module docstring for the default
    construction). Pass `max_sector_weight=None` for pure equal-weight, or
    `reallocate=False` to leave a capped sector's freed weight uninvested
    instead of redistributing it - see `_capped_weights`. Pass
    `max_name_weight` (e.g. 0.05) to also cap any single name's weight,
    applied after the sector cap. Pass `vol_target` (e.g. 0.10 for 10%
    annualized) to scale the whole book by trailing realized vol - see
    `_vol_target_leverage`."""
    daily = daily_book_returns(
        symbols,
        params,
        cost_bps_per_side,
        max_sector_weight,
        reallocate,
        max_name_weight,
        vol_target,
        vol_lookback_days,
        max_leverage,
    )
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
    avg_leverage = float(daily["leverage"].mean()) if n_days else 1.0

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
        max_name_weight=max_name_weight,
        vol_target=vol_target,
        avg_leverage=avg_leverage,
    )


def target_weights(
    rows: list[dict] | None = None,
    max_sector_weight: float | None = DEFAULT_MAX_SECTOR_WEIGHT,
    reallocate: bool = DEFAULT_REALLOCATE,
    max_name_weight: float | None = DEFAULT_MAX_NAME_WEIGHT,
) -> dict[str, float]:
    """Today's target weight per symbol - the same construction as the
    backtest (equal-weight, sector-capped/reallocated, optionally
    name-capped), computed for a single day instead of a full history.

    `rows` defaults to `latest_signals()` (today's long/flat call per
    symbol); pass a caller-supplied equivalent to avoid re-querying. Returns
    `{}` if nothing is currently long. Used by `quantis.execution` to know
    what the simulated broker should be rebalancing toward.
    """
    rows = rows if rows is not None else latest_signals()
    long_symbols = [r["symbol"] for r in rows if r.get("signal") == "long"]
    if not long_symbols:
        return {}

    weight = dict.fromkeys(long_symbols, 1.0 / len(long_symbols))

    if max_sector_weight is not None:
        sectors = _symbol_sectors(long_symbols)
        counts = pd.Series([sectors.get(s, "Unknown") for s in long_symbols]).value_counts()
        if reallocate:
            sector_weight = _water_fill(counts, max_sector_weight, total=1.0)
        else:
            sector_share = counts / counts.sum()
            sector_weight = sector_share.clip(upper=max_sector_weight)
        weight = {
            s: float(sector_weight[sectors.get(s, "Unknown")] / counts[sectors.get(s, "Unknown")])
            for s in long_symbols
        }

    if max_name_weight is not None:
        shares = pd.Series(weight)
        total = float(shares.sum())
        if reallocate:
            weight = _water_fill(shares, max_name_weight, total=total).to_dict()
        else:
            weight = {s: min(w, max_name_weight) for s, w in weight.items()}

    return weight


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
                max_name_weight=result.max_name_weight,
                vol_target=result.vol_target,
                avg_leverage=result.avg_leverage,
            )
        )
