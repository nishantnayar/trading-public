"""Weight-matrix backtest with explicit trade timing and turnover costs.

## Trade timing (the part that quietly invalidates backtests)

Weights for date `t` are formed from a prediction that uses data through `t`, so the
trade can only execute at `t`'s close. The position therefore earns the return from `t`
to `t+1`:

    pnl(t)  = w(t-1) . r(t)          <- yesterday's position, today's return
    cost(t) = |w(t) - w(t-1)| * bps  <- today's rebalance, charged today
    net(t)  = pnl(t) - cost(t)

The `shift(1)` on weights is the whole ballgame. Without it the portfolio earns the
return of the very bar used to pick it, which reliably manufactures a spectacular and
entirely fake equity curve. `tests/test_backtest.py` pins this behaviour.

Costs are charged as a one-sided rate on traded notional, covering commission plus half
the bid-ask spread. Market impact is **not** modelled — see docs/LIMITATIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantis.backtest.portfolio import turnover

BPS = 1e-4
SESSIONS_PER_YEAR = 252


@dataclass
class BacktestResult:
    """Daily series plus the summary metrics derived from them."""

    returns: pd.Series
    gross_returns: pd.Series
    costs: pd.Series
    equity: pd.Series
    turnover: pd.Series
    cost_bps_per_side: float

    def summary(self) -> dict[str, float]:
        return {"cost_bps_per_side": self.cost_bps_per_side, **performance(self.returns)}


def daily_returns(close: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns from adjusted closes (Alpaca `Adjustment.ALL`).

    Because the bars are split- and dividend-adjusted, this is a total return; no
    separate dividend series is needed.
    """
    return close.sort_index().pct_change(fill_method=None)


def run_backtest(
    weights: pd.DataFrame,
    returns: pd.DataFrame,
    cost_bps_per_side: float = 10.0,
) -> BacktestResult:
    """Apply a weight matrix to a return matrix, netting turnover costs."""
    if cost_bps_per_side < 0:
        raise ValueError(f"cost must be >= 0, got {cost_bps_per_side}")

    dates = weights.index.intersection(returns.index)
    symbols = weights.columns.intersection(returns.columns)
    if len(dates) == 0 or len(symbols) == 0:
        raise ValueError("weights and returns do not overlap")

    aligned_weights = weights.loc[dates, symbols].fillna(0.0)
    aligned_returns = returns.loc[dates, symbols].fillna(0.0)

    # Held position earns today's return; see module docstring on why this shift matters.
    held = aligned_weights.shift(1).fillna(0.0)
    gross = (held * aligned_returns).sum(axis=1)

    traded = turnover(aligned_weights)
    costs = traded * cost_bps_per_side * BPS
    net = gross - costs

    return BacktestResult(
        returns=net,
        gross_returns=gross,
        costs=costs,
        equity=(1.0 + net).cumprod(),
        turnover=traded,
        cost_bps_per_side=cost_bps_per_side,
    )


def performance(returns: pd.Series, sessions_per_year: int = SESSIONS_PER_YEAR) -> dict:
    """Standard risk/return statistics for a daily return series.

    Sharpe is excess-of-zero: with a dollar-neutral book the cash leg roughly funds
    itself, so subtracting a risk-free rate would double-count the financing benefit.
    """
    clean = returns.dropna()
    if clean.empty:
        return {"n_days": 0}

    equity = (1.0 + clean).cumprod()
    total = float(equity.iloc[-1] - 1.0)
    years = len(clean) / sessions_per_year
    vol = float(clean.std(ddof=1))
    downside = clean[clean < 0]

    drawdown = equity / equity.cummax() - 1.0
    annual_vol = vol * np.sqrt(sessions_per_year)

    return {
        "n_days": int(len(clean)),
        "total_return": total,
        "cagr": float((1.0 + total) ** (1.0 / years) - 1.0) if years > 0 and total > -1 else np.nan,
        "ann_vol": float(annual_vol),
        "sharpe": float(clean.mean() / vol * np.sqrt(sessions_per_year)) if vol > 0 else np.nan,
        "sortino": (
            float(clean.mean() / downside.std(ddof=1) * np.sqrt(sessions_per_year))
            if len(downside) > 1 and downside.std(ddof=1) > 0
            else np.nan
        ),
        "max_drawdown": float(drawdown.min()),
        "hit_rate": float((clean > 0).mean()),
        "best_day": float(clean.max()),
        "worst_day": float(clean.min()),
    }


def break_even_cost(
    weights: pd.DataFrame,
    returns: pd.DataFrame,
    max_bps: float = 100.0,
) -> float:
    """Cost per side (bps) at which the strategy's total return reaches zero.

    Solved directly rather than searched: gross P&L and traded notional are both fixed,
    so break-even = sum(gross) / sum(turnover), expressed in bps.
    """
    result = run_backtest(weights, returns, cost_bps_per_side=0.0)
    traded = result.turnover.sum()
    if traded <= 0:
        return np.nan
    return float(min(result.gross_returns.sum() / traded / BPS, max_bps))
