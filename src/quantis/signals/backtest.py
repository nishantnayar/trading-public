"""Vectorized long/flat backtest of the trend rule — no execution model, no
costs. A sanity check on the rule, not a replacement for the old backtest
engine: position is taken the day *after* a signal (no look-ahead), held
flat otherwise, and compared to buy-and-hold.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantis.signals.engine import load_price_history
from quantis.signals.rules import TrendParams, compute_signal
from quantis.signals.universe import WATCHLIST


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    strategy_return: float
    buy_hold_return: float
    sharpe: float
    n_trades: int
    time_in_market: float
    variant: str = ""
    start: str = ""
    end: str = ""


def backtest_symbol(
    df: pd.DataFrame,
    params: TrendParams | None = None,
) -> BacktestResult:
    """df must have `date` and `close` columns, ascending. Returns summary stats."""
    signals = compute_signal(df, params)
    daily_return = signals["close"].pct_change()
    is_long = signals["signal"] == "long"
    position = is_long.shift(1, fill_value=False)
    strategy_return = daily_return * position

    n_trades = int((position != position.shift(1, fill_value=False)).sum())
    time_in_market = float(position.mean())

    strategy_total = float((1 + strategy_return.fillna(0)).prod() - 1)
    buy_hold_total = float((1 + daily_return.fillna(0)).prod() - 1)
    sharpe = _annualized_sharpe(strategy_return)

    return BacktestResult(
        symbol="",
        strategy_return=strategy_total,
        buy_hold_return=buy_hold_total,
        sharpe=sharpe,
        n_trades=n_trades,
        time_in_market=time_in_market,
        start=str(signals["date"].iloc[0]),
        end=str(signals["date"].iloc[-1]),
    )


def run_watchlist(
    symbols: list[str] = WATCHLIST,
    params: TrendParams | None = None,
) -> list[BacktestResult]:
    """Backtest each symbol in `symbols` over its full stored history."""
    results = []
    for symbol in symbols:
        history = load_price_history(symbol)
        if history.empty:
            continue
        result = backtest_symbol(history, params)
        results.append(dataclasses.replace(result, symbol=symbol))
    return results


# Named parameter sets for side-by-side comparison, not just the current default.
VARIANTS: dict[str, TrendParams] = {
    "no_debounce": TrendParams(entry_confirm_days=1, exit_confirm_days=1),
    "exit_only": TrendParams(entry_confirm_days=1, exit_confirm_days=3),
    "entry_and_exit": TrendParams(entry_confirm_days=3, exit_confirm_days=3),
}


def compare_variants(
    symbols: list[str] = WATCHLIST,
    variants: dict[str, TrendParams] | None = None,
) -> list[BacktestResult]:
    """Every symbol backtested under every named variant, over its full history."""
    variants = variants or VARIANTS
    results = []
    for name, params in variants.items():
        for result in run_watchlist(symbols, params):
            results.append(dataclasses.replace(result, variant=name))
    return results


def _annualized_sharpe(returns: pd.Series, trading_days: int = 252) -> float:
    returns = returns.dropna()
    if returns.std(ddof=0) == 0 or returns.empty:
        return 0.0
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(trading_days))
