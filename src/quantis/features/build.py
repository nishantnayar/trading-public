"""Build the point-in-time feature store from `daily_bars`.

Loads bars wide (date x symbol), computes every feature in `definitions.py`, then writes
long rows to the `features` table via an idempotent upsert.

Run:  uv run python -m quantis.features.build
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from quantis.db.engine import session_scope
from quantis.db.models import DailyBar, Feature
from quantis.features.definitions import FEATURE_NAMES, YEAR, compute_all

# Longest lookback is 12-1 momentum / 52w high (252 sessions) and the 200d MA. Loading
# extra history before `start` is what lets the first requested date have real values.
WARMUP_DAYS = YEAR + 60


def load_bars(start: dt.date | None = None, end: dt.date | None = None) -> pd.DataFrame:
    """Long bars frame (symbol, date, close, volume), sorted by date."""
    with session_scope() as session:
        query = select(DailyBar.symbol, DailyBar.date, DailyBar.close, DailyBar.volume)
        if start is not None:
            query = query.where(DailyBar.date >= start)
        if end is not None:
            query = query.where(DailyBar.date <= end)
        rows = session.execute(query.order_by(DailyBar.date)).all()

    df = pd.DataFrame(rows, columns=["symbol", "date", "close", "volume"])
    if df.empty:
        return df
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)
    return df


def to_wide(bars: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pivot long bars into (close, volume) wide frames indexed by date."""
    close = bars.pivot(index="date", columns="symbol", values="close").sort_index()
    volume = bars.pivot(index="date", columns="symbol", values="volume").sort_index()
    return close, volume


def build_features(close: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    """Compute all features and return them long: (symbol, date, <features>)."""
    computed = compute_all(close, volume)

    frames = []
    for name, wide in computed.items():
        long = wide.stack(future_stack=True).rename(name)
        frames.append(long)

    out = pd.concat(frames, axis=1).reset_index()
    out = out.rename(columns={"level_0": "date", "level_1": "symbol"})
    # A row with no computable feature carries no information — drop it.
    return out.dropna(subset=FEATURE_NAMES, how="all")


def upsert_features(df: pd.DataFrame) -> int:
    """Idempotent upsert into `features`. Returns rows written."""
    if df.empty:
        return 0

    records = df.where(pd.notna(df), None).to_dict("records")
    written = 0
    with session_scope() as session:
        for i in range(0, len(records), 1000):
            chunk = records[i : i + 1000]
            stmt = insert(Feature).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Feature.symbol, Feature.date],
                set_={name: getattr(stmt.excluded, name) for name in FEATURE_NAMES},
            )
            session.execute(stmt)
            written += len(chunk)
    return written


def feature_coverage() -> dict:
    """Quick summary of what's in `features`."""
    with session_scope() as session:
        n = session.scalar(select(func.count()).select_from(Feature))
        nsym = session.scalar(select(func.count(func.distinct(Feature.symbol))))
        dmin = session.scalar(select(func.min(Feature.date)))
        dmax = session.scalar(select(func.max(Feature.date)))
    return {"rows": n, "symbols": nsym, "start": dmin, "end": dmax}


def run(start: dt.date | None = None, end: dt.date | None = None) -> dict:
    """Load bars, compute features, persist. `start` bounds the OUTPUT, not the input."""
    load_from = start - dt.timedelta(days=WARMUP_DAYS) if start else None
    bars = load_bars(load_from, end)
    if bars.empty:
        logger.warning("no bars found — nothing to build")
        return {"rows": 0}

    logger.info("loaded {} bars for {} symbols", len(bars), bars["symbol"].nunique())
    close, volume = to_wide(bars)
    features = build_features(close, volume)

    if start is not None:
        features = features[features["date"] >= start]

    written = upsert_features(features)
    logger.info("wrote {} feature rows", written)
    return feature_coverage()


if __name__ == "__main__":
    print(run())
