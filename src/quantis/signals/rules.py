"""Trend-following rule: SMA crossover, confirmed by 12-1 momentum.

`long` requires all three conditions on the same bar:
  - fast SMA above slow SMA (golden-cross regime)
  - 12-1 momentum positive (confirms the trend isn't directionless chop)
  - close above the fast SMA (acts as the trailing-stop / death-cross exit —
    a name drops out the moment price breaks the fast SMA, without needing a
    separate stateful backtest loop)

Everything else is `flat`. This is intentionally not a full backtest engine —
it labels each bar so the caller (engine.py) can read off the latest signal.
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


def compute_signal(df: pd.DataFrame, params: TrendParams | None = None) -> pd.DataFrame:
    """df must have a `close` column, ascending by date. Returns df + indicator/signal columns."""
    params = params or TrendParams()
    out = df.copy()
    out["sma_fast"] = indicators.sma(out["close"], params.fast)
    out["sma_slow"] = indicators.sma(out["close"], params.slow)
    out["mom_12_1"] = indicators.momentum(
        out["close"], params.momentum_months, params.momentum_skip_months
    )

    trend_up = out["sma_fast"] > out["sma_slow"]
    momentum_ok = out["mom_12_1"] > 0
    above_stop = out["close"] > out["sma_fast"]
    is_long = trend_up & momentum_ok & above_stop

    out["signal"] = "flat"
    out.loc[is_long.fillna(False), "signal"] = "long"
    return out
