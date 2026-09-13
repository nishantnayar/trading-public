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

Construction is deliberately the simplest possible: equal weight across every
name currently signaled long, rebalanced daily (a name added/dropped from the
long book that day enters/exits at 1/N of whatever N is that day). No
per-name cap, no sector cap, no vol targeting — see docs/LIMITATIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantis.signals.backtest import (
    DEFAULT_COST_BPS_PER_SIDE,
    _annualized_sharpe,
    universe_daily_frame,
)
from quantis.signals.rules import TrendParams


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
    annualized_turnover: float
    trading_days: int


def daily_book_returns(
    symbols: list[str] | None = None,
    params: TrendParams | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
) -> pd.DataFrame:
    """One row per trading day: equal-weighted net/gross return of every
    currently-long name that day, breadth (`n_long`), and how many names
    changed position that day (`n_trades`). A flat day (nothing long) earns
    0, not NaN.
    """
    all_days = universe_daily_frame(symbols, params, cost_bps_per_side)
    if all_days.empty:
        return pd.DataFrame(columns=["date", "net_return", "gross_return", "n_long", "n_trades"])

    long_days = all_days[all_days["position"]]
    full_index = pd.Index(sorted(all_days["date"].unique()))

    net_return = long_days.groupby("date")["net_return"].mean().reindex(full_index, fill_value=0.0)
    gross_return = (
        long_days.groupby("date")["gross_return"].mean().reindex(full_index, fill_value=0.0)
    )
    n_long = long_days.groupby("date").size().reindex(full_index, fill_value=0)
    n_trades = all_days.groupby("date")["trade_flag"].sum().reindex(full_index, fill_value=0)

    return pd.DataFrame(
        {
            "date": full_index,
            "net_return": net_return.to_numpy(),
            "gross_return": gross_return.to_numpy(),
            "n_long": n_long.to_numpy(),
            "n_trades": n_trades.to_numpy(),
        }
    )


def portfolio_summary(
    symbols: list[str] | None = None,
    params: TrendParams | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
) -> PortfolioResult:
    """Full-period backtest of the equal-weighted book (see module docstring)."""
    daily = daily_book_returns(symbols, params, cost_bps_per_side)
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
        annualized_turnover=annualized_turnover,
        trading_days=n_days,
    )
