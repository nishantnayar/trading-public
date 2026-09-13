"""Trend-following rule: SMA crossover, confirmed by 12-1 momentum.

Entry (flat -> long) requires `entry_confirm_days` *consecutive* bars where:
  - fast SMA above slow SMA (golden-cross regime)
  - 12-1 momentum positive (confirms the trend isn't directionless chop)

Exit (long -> flat) requires `exit_confirm_days` *consecutive* closes below
the fast SMA.

Defaults are the "exit_only" variant from backtest.VARIANTS: single-bar
entry (entry_confirm_days=1), 3-day debounced exit (exit_confirm_days=3).
Backtested across 22 names / 9 sectors (2020-07-27 .. 2026-09-10), it beat
both a fully single-bar rule and a symmetric 3-day-debounced-entry-and-exit
rule on median return (26.7% vs 10.4% vs 19.9%) at the same median Sharpe
as the latter (0.29) - see `uv run python -m quantis.signals --compare`.
Debouncing only the exit avoids the single-bar rule's whipsaw without
delaying entry into real trends the way a debounced entry does.

This is intentionally not a full backtest engine - it labels each bar so the
caller (engine.py, backtest.py) can read off signals over time. The state
machine (are we long, how many consecutive stop-days) is inherently
sequential, so this loops once over the series rather than vectorizing.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quantis.signals import indicators


@dataclass(frozen=True)
class TrendParams:
    fast: int = 50
    slow: int = 200
    momentum_months: int = 12
    momentum_skip_months: int = 1
    entry_confirm_days: int = 1
    exit_confirm_days: int = 3


def compute_signal(df: pd.DataFrame, params: TrendParams | None = None) -> pd.DataFrame:
    """df must have a `close` column, ascending by date. Returns df + indicator/signal columns."""
    params = params or TrendParams()
    out = df.copy()
    out["sma_fast"] = indicators.sma(out["close"], params.fast)
    out["sma_slow"] = indicators.sma(out["close"], params.slow)
    out["mom_12_1"] = indicators.momentum(
        out["close"], params.momentum_months, params.momentum_skip_months
    )

    entry_ok = ((out["sma_fast"] > out["sma_slow"]) & (out["mom_12_1"] > 0)).fillna(False)
    below_stop = (out["close"] < out["sma_fast"]).fillna(False)

    signals: list[str] = []
    is_long = False
    consecutive_below = 0
    consecutive_entry = 0
    for entry, below in zip(entry_ok, below_stop, strict=True):
        if is_long:
            consecutive_below = consecutive_below + 1 if below else 0
            if consecutive_below >= params.exit_confirm_days:
                is_long = False
                consecutive_below = 0
            consecutive_entry = 0
        else:
            consecutive_entry = consecutive_entry + 1 if entry else 0
            if consecutive_entry >= params.entry_confirm_days:
                is_long = True
                consecutive_entry = 0
        signals.append("long" if is_long else "flat")

    out["signal"] = signals
    return out
