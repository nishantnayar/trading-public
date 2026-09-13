"""Trend-following rule: SMA crossover, confirmed by 12-1 momentum.

Entry (flat -> long) requires `entry_confirm_days` *consecutive* bars where:
  - fast SMA above slow SMA (golden-cross regime)
  - 12-1 momentum positive (confirms the trend isn't directionless chop)

Exit (long -> flat) requires `exit_confirm_days` *consecutive* closes below
the fast SMA.

Defaults are the "exit_only" variant from backtest.VARIANTS: single-bar
entry (entry_confirm_days=1), 3-day debounced exit (exit_confirm_days=3).
An initial 22-name curated comparison favored it clearly (median return
26.7% vs 10.4%/19.9% for the other two variants). Re-run over the full
~503-name active universe at a 10 bps/side cost model, the picture is more
sobering: median *net* return is negative for all three variants
(no_debounce -19.0%, exit_only -4.7%, entry_and_exit -6.1%), but exit_only
is still the clear best of the three — most wins (251/503), least-negative
median net return, and the only one with a (barely) positive median Sharpe
(0.04). See `uv run python -m quantis.signals --compare`. Read this as "the
least-bad of three simple options tested," not "a proven edge" — a rule
this simple having a negative median net return across the broad market is
the expected, honest result, not a bug.

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
