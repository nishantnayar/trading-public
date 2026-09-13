"""Vectorized long/flat backtest of the trend rule, with a flat-bps cost model.
A sanity check on the rule, not a replacement for the old backtest engine:
position is taken the day *after* a signal (no look-ahead), held flat
otherwise, and compared to buy-and-hold.

Cost model: `cost_bps_per_side` charged on every position *change* (entry or
exit), same convention as the deleted `quantis.backtest` engine
(`cost = |w(t) - w(t-1)| * bps_per_side`) but for a binary 0/1 position
instead of a portfolio weight. A full round trip (entry then exit) costs
`2 * cost_bps_per_side`. No market impact, no slippage dispersion, no
borrow — see docs/LIMITATIONS.md.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantis.signals.engine import load_price_history
from quantis.signals.rules import TrendParams, compute_signal
from quantis.signals.universe import full_universe

DEFAULT_COST_BPS_PER_SIDE = 10.0


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    strategy_return: float
    buy_hold_return: float
    sharpe: float
    n_trades: int
    time_in_market: float
    net_return: float = 0.0
    net_sharpe: float = 0.0
    break_even_bps: float = 0.0
    cost_bps_per_side: float = 0.0
    variant: str = ""
    start: str = ""
    end: str = ""


def backtest_symbol(
    df: pd.DataFrame,
    params: TrendParams | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
) -> BacktestResult:
    """df must have `date` and `close` columns, ascending. Returns summary stats."""
    signals = compute_signal(df, params)
    daily_return = signals["close"].pct_change()
    is_long = signals["signal"] == "long"
    position = is_long.shift(1, fill_value=False)
    strategy_return = daily_return * position

    position_int = position.astype(int)
    trade_flag = (position_int - position_int.shift(1, fill_value=0)).abs()
    n_trades = int(trade_flag.sum())
    time_in_market = float(position.mean())

    net_return = strategy_return - trade_flag * (cost_bps_per_side / 10_000)

    strategy_total = float((1 + strategy_return.fillna(0)).prod() - 1)
    net_total = float((1 + net_return.fillna(0)).prod() - 1)
    buy_hold_total = float((1 + daily_return.fillna(0)).prod() - 1)
    sharpe = _annualized_sharpe(strategy_return)
    net_sharpe = _annualized_sharpe(net_return)
    break_even = _break_even_bps(strategy_return, trade_flag)

    return BacktestResult(
        symbol="",
        strategy_return=strategy_total,
        buy_hold_return=buy_hold_total,
        sharpe=sharpe,
        n_trades=n_trades,
        time_in_market=time_in_market,
        net_return=net_total,
        net_sharpe=net_sharpe,
        break_even_bps=break_even,
        cost_bps_per_side=cost_bps_per_side,
        start=str(signals["date"].iloc[0]),
        end=str(signals["date"].iloc[-1]),
    )


def run_watchlist(
    symbols: list[str] | None = None,
    params: TrendParams | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
) -> list[BacktestResult]:
    """Backtest each symbol in `symbols` (default: the full active universe)
    over its full stored history."""
    symbols = symbols if symbols is not None else full_universe()
    results = []
    for symbol in symbols:
        history = load_price_history(symbol)
        if history.empty:
            continue
        result = backtest_symbol(history, params, cost_bps_per_side)
        results.append(dataclasses.replace(result, symbol=symbol))
    return results


# Named parameter sets for side-by-side comparison, not just the current default.
VARIANTS: dict[str, TrendParams] = {
    "no_debounce": TrendParams(entry_confirm_days=1, exit_confirm_days=1),
    "exit_only": TrendParams(entry_confirm_days=1, exit_confirm_days=3),
    "entry_and_exit": TrendParams(entry_confirm_days=3, exit_confirm_days=3),
}


def compare_variants(
    symbols: list[str] | None = None,
    variants: dict[str, TrendParams] | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
) -> list[BacktestResult]:
    """Every symbol (default: the full active universe) backtested under every
    named variant, over its full history."""
    symbols = symbols if symbols is not None else full_universe()
    variants = variants or VARIANTS
    results = []
    for name, params in variants.items():
        for result in run_watchlist(symbols, params, cost_bps_per_side):
            results.append(dataclasses.replace(result, variant=name))
    return results


def _annualized_sharpe(returns: pd.Series, trading_days: int = 252) -> float:
    returns = returns.dropna()
    if returns.std(ddof=0) == 0 or returns.empty:
        return 0.0
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(trading_days))


def _net_total_at_bps(strategy_return: pd.Series, trade_flag: pd.Series, bps: float) -> float:
    net = strategy_return - trade_flag * (bps / 10_000)
    return float((1 + net.fillna(0)).prod() - 1)


_BREAK_EVEN_SEARCH_CAP_BPS = 1_000.0  # 10% per side — already far past any realistic cost


def _break_even_bps(strategy_return: pd.Series, trade_flag: pd.Series) -> float:
    """Flat bps-per-side at which compounded net return is exactly zero.

    `inf` if the rule never trades (costs can never bite); 0 if it is already
    unprofitable gross; `_BREAK_EVEN_SEARCH_CAP_BPS` if it survives even that
    (a floor, not the true break-even). Otherwise bisected.

    The search is capped well below 10,000 bps (100% per trade) on purpose:
    past that a single trade's cost exceeds the position's full value, so
    `1 + net_return` on that day goes negative, and a compounded product of
    several negative daily terms can land back on a spuriously *positive*
    total — breaking the monotonicity bisection depends on. No real cost
    figure is anywhere near that range, so the cap costs nothing in practice.
    """
    if trade_flag.sum() == 0:
        return math.inf
    if _net_total_at_bps(strategy_return, trade_flag, 0.0) <= 0:
        return 0.0
    lo, hi = 0.0, _BREAK_EVEN_SEARCH_CAP_BPS
    for _ in range(60):
        mid = (lo + hi) / 2
        if _net_total_at_bps(strategy_return, trade_flag, mid) > 0:
            lo = mid
        else:
            hi = mid
    return lo
