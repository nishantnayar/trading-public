"""Upsert out-of-fold scores, target weights, and a single model-run snapshot."""

from __future__ import annotations

import json
import math

import pandas as pd
from loguru import logger
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from quantis.db.engine import session_scope
from quantis.db.models import ModelRun, Position, Prediction


def _clean(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def upsert_predictions(df: pd.DataFrame, source: str) -> int:
    """Replace the predictions table with this frame (symbol, date, pred, label)."""
    if df.empty:
        return 0
    records = []
    for row in df.itertuples(index=False):
        records.append(
            {
                "symbol": row.symbol,
                "date": pd.Timestamp(row.date).date(),
                "pred": float(row.pred),
                "label": _clean(getattr(row, "label", None)),
                "source": source,
            }
        )
    written = 0
    with session_scope() as session:
        session.execute(delete(Prediction))
        for i in range(0, len(records), 1000):
            chunk = records[i : i + 1000]
            session.execute(insert(Prediction).values(chunk))
            written += len(chunk)
    logger.info("wrote {} prediction rows from {}", written, source)
    return written


def upsert_positions(weights: pd.DataFrame, construction: str) -> int:
    """Replace positions with the non-zero cells of a date x symbol weight matrix."""
    long = weights.stack()
    long = long[long.abs() > 1e-12]
    if long.empty:
        return 0
    records = [
        {
            "symbol": symbol,
            "date": pd.Timestamp(date).date(),
            "weight": float(weight),
            "construction": construction,
        }
        for (date, symbol), weight in long.items()
    ]
    written = 0
    with session_scope() as session:
        session.execute(delete(Position))
        for i in range(0, len(records), 1000):
            chunk = records[i : i + 1000]
            session.execute(insert(Position).values(chunk))
            written += len(chunk)
    logger.info("wrote {} position rows ({})", written, construction)
    return written


def replace_model_run(payload: dict) -> None:
    """Keep a single published snapshot — the dashboard only ever shows the latest."""
    with session_scope() as session:
        session.execute(delete(ModelRun))
        session.add(
            ModelRun(
                oof_source=payload["oof_source"],
                construction=payload["construction"],
                as_of=payload.get("as_of"),
                n_dates=payload.get("n_dates"),
                n_symbols=payload.get("n_symbols"),
                rank_ic=payload.get("rank_ic"),
                icir=payload.get("icir"),
                ic_hit_rate=payload.get("ic_hit_rate"),
                q_spread=payload.get("q_spread"),
                sharpe_10bps=payload.get("sharpe_10bps"),
                turnover=payload.get("turnover"),
                break_even_bps=payload.get("break_even_bps"),
                shap_json=json.dumps(payload.get("shap") or []),
                params_json=json.dumps(payload.get("params") or {}),
            )
        )
