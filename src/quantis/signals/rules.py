"""Trend-following rule: SMA crossover, confirmed by 12-1 momentum.

Entry (flat -> long) requires all three on the same bar:
  - fast SMA above slow SMA (golden-cross regime)
  - 12-1 momentum positive (confirms the trend isn't directionless chop)
  - close above the fast SMA

Exit (long -> flat) requires `exit_confirm_days` *consecutive* closes below
the fast SMA. A single-bar stop whipsawed constantly on noisy names (dozens
of round trips with a large majority of trend-days spent flat) - debouncing
it means one bad close doesn't kick out an otherwise intact trend, at the
cost of giving back a bit more on a real reversal before exiting.

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
    for entry, below in zip(entry_ok, below_stop, strict=True):
        if is_long:
            consecutive_below = consecutive_below + 1 if below else 0
            if consecutive_below >= params.exit_confirm_days:
                is_long = False
                consecutive_below = 0
        elif entry:
            is_long = True
        signals.append("long" if is_long else "flat")

    out["signal"] = signals
    return out
