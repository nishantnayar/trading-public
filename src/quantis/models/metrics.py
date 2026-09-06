"""Cross-sectional model metrics.

RMSE on a z-scored label is close to meaningless for a ranking strategy — the portfolio
only cares about the *order* of predictions within each date. So the headline metric is
the **rank information coefficient**: the Spearman correlation between prediction and
realised label, computed per date and then summarised across dates.

    IC_t   = spearman( pred_t , label_t )        for each date t
    IC     = mean_t(IC_t)
    ICIR   = IC / std_t(IC_t)                    an information ratio for the signal
    t-stat = IC / (std_t(IC_t) / sqrt(n_dates))  is the mean IC distinguishable from 0?

Typical equity cross-sectional models live around IC 0.02-0.06. Anything far above that
on free daily data is a bug, not alpha.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_NAMES_FOR_IC = 20


def rank_ic_by_date(
    frame: pd.DataFrame,
    pred_column: str = "pred",
    label_column: str = "label",
    date_column: str = "date",
    min_names: int = MIN_NAMES_FOR_IC,
) -> pd.Series:
    """Spearman rank correlation between prediction and label, per date."""

    def one_date(group: pd.DataFrame) -> float:
        if len(group) < min_names:
            return np.nan
        return group[pred_column].corr(group[label_column], method="spearman")

    # Select columns before grouping so the grouping key is never passed into `apply`.
    columns = [pred_column, label_column]
    return frame.groupby(date_column, sort=True)[columns].apply(one_date).dropna()


def quantile_spread(
    frame: pd.DataFrame,
    pred_column: str = "pred",
    label_column: str = "label",
    date_column: str = "date",
    quantiles: int = 5,
    min_names: int = MIN_NAMES_FOR_IC,
) -> float:
    """Mean label of the top predicted quantile minus the bottom.

    This is the metric closest to what the strategy actually harvests: go long Q5, short
    Q1, and the spread is the gross edge before costs and sizing.
    """

    def one_date(group: pd.DataFrame) -> float:
        if len(group) < max(min_names, quantiles * 2):
            return np.nan
        buckets = pd.qcut(group[pred_column].rank(method="first"), quantiles, labels=False)
        top = group.loc[buckets == quantiles - 1, label_column].mean()
        bottom = group.loc[buckets == 0, label_column].mean()
        return top - bottom

    columns = [pred_column, label_column]
    spreads = frame.groupby(date_column, sort=True)[columns].apply(one_date).dropna()
    return float(spreads.mean()) if len(spreads) else float("nan")


def summarise(
    frame: pd.DataFrame,
    pred_column: str = "pred",
    label_column: str = "label",
    date_column: str = "date",
    quantiles: int = 5,
) -> dict[str, float]:
    """Headline metrics for one validation block."""
    ics = rank_ic_by_date(frame, pred_column, label_column, date_column)
    n = len(ics)
    if n == 0:
        return {"n_dates": 0, "rank_ic": float("nan")}

    mean_ic = float(ics.mean())
    std_ic = float(ics.std(ddof=1)) if n > 1 else float("nan")
    icir = mean_ic / std_ic if std_ic and not np.isnan(std_ic) else float("nan")

    return {
        "n_dates": int(n),
        "rank_ic": mean_ic,
        "ic_std": std_ic,
        "icir": icir,
        "ic_t_stat": icir * np.sqrt(n) if not np.isnan(icir) else float("nan"),
        # Share of dates where the signal pointed the right way at all.
        "ic_hit_rate": float((ics > 0).mean()),
        "q_spread": quantile_spread(frame, pred_column, label_column, date_column, quantiles),
    }
