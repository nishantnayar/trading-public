"""Assemble the training panel: features from Postgres joined to forward-return labels."""

from __future__ import annotations

import datetime as dt

import pandas as pd
from loguru import logger
from sqlalchemy import select

from quantis.db.engine import get_engine, session_scope
from quantis.db.models import DailyBar, Feature
from quantis.features.definitions import FEATURE_NAMES
from quantis.features.fundamental_build import FUND_FEATURE_NAMES
from quantis.models.labels import DEFAULT_HORIZON, make_labels, to_long

# The cross-section is effectively empty before 2020 (see docs/LIMITATIONS.md): 2018-19
# holds ~270 rows across <=10 symbols, which cannot support a quintile spread.
DEFAULT_START = dt.date(2020, 1, 1)

# Price features (11) are required complete — see `load_features`. Fundamental
# features (4, value/quality) are appended but stay OPTIONAL: coverage depends on the
# EDGAR backfill and LightGBM handles the resulting NaNs natively, so they must never
# be included in a `dropna` requirement the way price features are.
ALL_FEATURE_NAMES = FEATURE_NAMES + FUND_FEATURE_NAMES


def load_features(start: dt.date | None = DEFAULT_START) -> pd.DataFrame:
    """Long feature rows: the 11 price features REQUIRED complete, plus the 4
    fundamental (value/quality) features left as-is (may be NaN).

    Price rows are dropped rather than imputed when incomplete: `mom_12_1` needs 252
    sessions, so early rows are missing it, and imputing a fabricated momentum value
    would inject signal that never existed. All 11 price features are fully populated
    from 2024 onward. Fundamental features are sparser by nature (quarterly filings,
    EDGAR backfill still growing coverage) and are NOT required — see
    `quantis/features/fundamental_build.py`.
    """
    columns = [Feature.symbol, Feature.date, *[getattr(Feature, n) for n in ALL_FEATURE_NAMES]]
    query = select(*columns)
    if start is not None:
        query = query.where(Feature.date >= start)

    with session_scope() as session:
        rows = session.execute(query.order_by(Feature.date)).all()

    df = pd.DataFrame(rows, columns=["symbol", "date", *ALL_FEATURE_NAMES])
    if df.empty:
        return df

    for name in ALL_FEATURE_NAMES:
        df[name] = df[name].astype(float)

    before = len(df)
    df = df.dropna(subset=FEATURE_NAMES).reset_index(drop=True)
    fund_coverage = int(df[FUND_FEATURE_NAMES].notna().any(axis=1).sum()) if len(df) else 0
    logger.info(
        "features: kept {}/{} complete-price rows ({} also have fundamental data)",
        len(df),
        before,
        fund_coverage,
    )
    return df


def load_close_wide(start: dt.date | None = None) -> pd.DataFrame:
    """Wide close prices (date x symbol) for label construction."""
    query = select(DailyBar.symbol, DailyBar.date, DailyBar.close)
    if start is not None:
        query = query.where(DailyBar.date >= start)

    with session_scope() as session:
        rows = session.execute(query.order_by(DailyBar.date)).all()

    bars = pd.DataFrame(rows, columns=["symbol", "date", "close"])
    bars["close"] = bars["close"].astype(float)
    return bars.pivot(index="date", columns="symbol", values="close").sort_index()


def build_panel(
    start: dt.date | None = DEFAULT_START,
    horizon: int = DEFAULT_HORIZON,
) -> pd.DataFrame:
    """Features joined to labels: (symbol, date, <features>, label).

    Labels are built from the FULL price history so the forward window at the panel's
    start date is available, then inner-joined onto the feature rows.
    """
    features = load_features(start)
    if features.empty:
        logger.warning("no complete feature rows found")
        return features

    close = load_close_wide()
    labels = to_long(make_labels(close, horizon=horizon))

    panel = features.merge(labels, on=["symbol", "date"], how="inner")
    panel = panel.sort_values(["date", "symbol"]).reset_index(drop=True)
    logger.info(
        "panel: {} rows, {} symbols, {} -> {}",
        len(panel),
        panel["symbol"].nunique(),
        panel["date"].min(),
        panel["date"].max(),
    )
    return panel


def panel_summary(panel: pd.DataFrame) -> dict:
    """Shape facts worth logging next to any metric."""
    if panel.empty:
        return {"rows": 0}
    per_date = panel.groupby("date").size()
    fund_present = [c for c in FUND_FEATURE_NAMES if c in panel.columns]
    fund_coverage_rows = int(panel[fund_present].notna().any(axis=1).sum()) if fund_present else 0
    return {
        "rows": len(panel),
        "symbols": int(panel["symbol"].nunique()),
        "dates": int(panel["date"].nunique()),
        "start": str(panel["date"].min()),
        "end": str(panel["date"].max()),
        "median_names_per_date": int(per_date.median()),
        "min_names_per_date": int(per_date.min()),
        "fundamental_coverage_rows": fund_coverage_rows,
        "fundamental_coverage_pct": (
            round(100.0 * fund_coverage_rows / len(panel), 2) if len(panel) else 0.0
        ),
    }


def engine_ping() -> bool:
    """Cheap check used by scripts before a long training run."""
    try:
        with get_engine().connect():
            return True
    except Exception:  # noqa: BLE001
        return False
