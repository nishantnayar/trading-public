"""Dashboard reads for published scores, target weights, and model diagnostics."""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError

from quantis.db.engine import session_scope
from quantis.db.models import (
    BrokerAccount,
    BrokerFill,
    BrokerPosition,
    ModelRun,
    Position,
    Prediction,
    Symbol,
)

FEATURE_FAMILY = {
    "mom_1m": "momentum",
    "mom_3m": "momentum",
    "mom_6m": "momentum",
    "mom_12_1": "momentum",
    "ret_5d": "reversal",
    "vol_20d": "volatility",
    "vol_60d": "volatility",
    "rsi_14": "technical",
    "dist_52w_high": "technical",
    "ma_ratio_50_200": "technical",
    "dollar_vol_20d": "liquidity",
    "gross_margin": "quality",
    "roe_ttm": "quality",
    "accruals_ttm": "quality",
    "book_to_market": "value",
}


def _as_of_predictions() -> dt.date | None:
    with session_scope() as session:
        value = session.scalar(select(func.max(Prediction.date)))
        return value if isinstance(value, dt.date) else None


def _as_of_positions() -> dt.date | None:
    with session_scope() as session:
        value = session.scalar(select(func.max(Position.date)))
        return value if isinstance(value, dt.date) else None


def signals_snapshot(head: int = 7, tail: int = 7) -> dict:
    """Latest cross-section: top/bottom scores joined to target weight and sector."""
    as_of = _as_of_predictions()
    if as_of is None:
        return {"as_of": None, "rows": [], "meta": {}}

    with session_scope() as session:
        query = (
            select(
                Prediction.symbol,
                Prediction.pred,
                Prediction.label,
                Symbol.sector,
                Position.weight,
                Position.construction,
            )
            .join(Symbol, Symbol.symbol == Prediction.symbol)
            .outerjoin(
                Position,
                (Position.symbol == Prediction.symbol) & (Position.date == Prediction.date),
            )
            .where(Prediction.date == as_of)
            .order_by(Prediction.pred.desc())
        )
        rows = session.execute(query).all()

    ranked = []
    n = len(rows)
    for i, row in enumerate(rows, start=1):
        weight = float(row.weight) if row.weight is not None else 0.0
        ranked.append(
            {
                "rank": i,
                "symbol": row.symbol,
                "sector": row.sector or "Unknown",
                "score": float(row.pred),
                "pctl": round(100.0 * (1.0 - (i - 1) / max(n - 1, 1)), 1),
                "weight": weight,
                "side": "L" if weight > 0 else "S" if weight < 0 else "",
            }
        )

    ladder = ranked[:head]
    if n > head + tail:
        ladder.append({"gap": True, "label": f"{n - head - tail} names not shown"})
    if n > head:
        ladder.extend(ranked[-tail:])

    longs = sum(1 for r in ranked if r["side"] == "L")
    shorts = sum(1 for r in ranked if r["side"] == "S")
    construction = next((r.construction for r in rows if r.construction), "")
    return {
        "as_of": as_of.isoformat(),
        "rows": ladder,
        "meta": {
            "horizon": "5d forward (OOF)",
            "scored": n,
            "longs": longs,
            "shorts": shorts,
            "construction": construction,
        },
    }


def quintile_labels() -> list[dict]:
    """Mean OOF *label* by predicted quintile — dimensionless z, not percent."""
    as_of = _as_of_predictions()
    if as_of is None:
        return []
    with session_scope() as session:
        rows = session.execute(
            select(Prediction.pred, Prediction.label).where(
                Prediction.date == as_of, Prediction.label.is_not(None)
            )
        ).all()
    if len(rows) < 20:
        return []
    frame = pd.DataFrame(rows, columns=["pred", "label"]).astype(float)
    frame["q"] = pd.qcut(frame["pred"].rank(method="first"), 5, labels=False)
    means = frame.groupby("q")["label"].mean()
    return [{"label": f"Q{q + 1}", "v": float(means.get(q, 0.0))} for q in range(4, -1, -1)]


def positions_snapshot() -> dict:
    as_of = _as_of_positions()
    if as_of is None:
        return {"as_of": None, "holdings": [], "constraints": [], "rebalance": {}}

    with session_scope() as session:
        recent_dates = session.scalars(
            select(Position.date).distinct().order_by(Position.date.desc()).limit(40)
        ).all()
        latest = session.execute(
            select(Position.symbol, Position.weight, Position.construction, Symbol.sector)
            .join(Symbol, Symbol.symbol == Position.symbol)
            .where(Position.date == as_of)
            .order_by(func.abs(Position.weight).desc())
        ).all()
        history = session.execute(
            select(Position.symbol, Position.date, Position.weight).where(
                Position.date.in_(recent_dates)
            )
        ).all()

    holdings = [
        {
            "symbol": row.symbol,
            "sector": row.sector or "Unknown",
            "weight": float(row.weight),
            "side": "L" if float(row.weight) > 0 else "S",
        }
        for row in latest
    ]
    holdings.sort(key=lambda h: (0 if h["side"] == "L" else 1, -abs(h["weight"]), h["symbol"]))
    weights = {h["symbol"]: h["weight"] for h in holdings}
    gross = sum(abs(w) for w in weights.values())
    net = sum(weights.values())
    max_name = max((abs(w) for w in weights.values()), default=0.0)
    by_sector: dict[str, float] = {}
    for h in holdings:
        by_sector[h["sector"]] = by_sector.get(h["sector"], 0.0) + h["weight"]
    max_sector = max((abs(v) for v in by_sector.values()), default=0.0)

    hist = pd.DataFrame(history, columns=["symbol", "date", "weight"])
    prior_date = None
    buys = sells = 0
    traded = 0.0
    if not hist.empty:
        hist["weight"] = hist["weight"].astype(float)
        wide = (
            hist.pivot(index="date", columns="symbol", values="weight")
            .fillna(0.0)
            .astype(float)
            .sort_index()
        )
        current = wide.iloc[-1]
        for date, row in reversed(list(wide.iloc[:-1].iterrows())):
            if (row - current).abs().sum() > 1e-9:
                prior_date = date
                delta = current.subtract(row, fill_value=0.0)
                traded = float(delta.abs().sum())
                buys = int(((current != 0) & (row == 0)).sum())
                sells = int(((current == 0) & (row != 0)).sum())
                break

    construction = latest[0].construction if latest else ""
    return {
        "as_of": as_of.isoformat(),
        "construction": construction,
        "holdings": holdings[:40],
        "n_holdings": len(holdings),
        "constraints": [
            {
                "label": "GROSS",
                "value": f"{gross:.2f}",
                "limit": "/ 1.00 target",
                "used": min(100, int(gross * 100)),
            },
            {
                "label": "NET",
                "value": f"{net:+.2e}",
                "limit": "/ 0 dollar-neutral",
                "used": min(100, int(abs(net) * 1e4)),
            },
            {
                "label": "MAX NAME WT",
                "value": f"{max_name:.1%}",
                "limit": "observed, no cap",
                "used": min(100, int(max_name * 100 / 0.03)),
            },
            {
                "label": "MAX |SECTOR|",
                "value": f"{max_sector:.1%}",
                "limit": "IT tilt is the edge",
                "used": min(100, int(max_sector * 100 / 0.10)),
            },
        ],
        "rebalance": {
            "buys": buys,
            "sells": sells,
            "turnover": traded,
            "prior": None if prior_date is None else pd.Timestamp(prior_date).date().isoformat(),
        },
    }


def model_snapshot() -> dict:
    with session_scope() as session:
        row = session.scalar(select(ModelRun).order_by(ModelRun.published_at.desc()).limit(1))
    if row is None:
        return {}
    shap = json.loads(row.shap_json or "[]")
    for item in shap:
        item["family"] = FEATURE_FAMILY.get(item.get("feature", ""), "other")
    params = json.loads(row.params_json or "{}")
    return {
        "as_of": row.as_of.isoformat() if row.as_of else None,
        "oof_source": row.oof_source,
        "construction": row.construction,
        "n_dates": row.n_dates,
        "n_symbols": row.n_symbols,
        "rank_ic": float(row.rank_ic) if row.rank_ic is not None else None,
        "icir": float(row.icir) if row.icir is not None else None,
        "ic_hit_rate": float(row.ic_hit_rate) if row.ic_hit_rate is not None else None,
        "q_spread": float(row.q_spread) if row.q_spread is not None else None,
        "sharpe_10bps": float(row.sharpe_10bps) if row.sharpe_10bps is not None else None,
        "turnover": float(row.turnover) if row.turnover is not None else None,
        "break_even_bps": float(row.break_even_bps) if row.break_even_bps is not None else None,
        "shap": shap,
        "params": params,
    }


def broker_snapshot(limit: int = 20) -> dict:
    """Simulated (or last persisted) paper ledger — not target weights."""
    empty: dict = {
        "broker": "simulated",
        "cash": None,
        "n_positions": 0,
        "positions": [],
        "fills": [],
    }
    try:
        with session_scope() as session:
            acct = session.get(BrokerAccount, "simulated")
            positions = (
                session.execute(select(BrokerPosition).where(BrokerPosition.broker == "simulated"))
                .scalars()
                .all()
            )
            fills = session.scalars(
                select(BrokerFill)
                .where(BrokerFill.broker == "simulated")
                .order_by(BrokerFill.submitted_at.desc())
                .limit(limit)
            ).all()
    except ProgrammingError:
        return empty
    return {
        "broker": "simulated",
        "cash": float(acct.cash) if acct else None,
        "n_positions": len(positions),
        "positions": [
            {"symbol": p.symbol, "qty": float(p.qty)} for p in positions if abs(float(p.qty)) > 1e-9
        ][:40],
        "fills": [
            {
                "broker": f.broker,
                "symbol": f.symbol,
                "side": f.side,
                "qty": float(f.qty),
                "price": float(f.price) if f.price is not None else None,
                "status": f.status,
                "submitted_at": f.submitted_at.isoformat() if f.submitted_at else None,
            }
            for f in fills
        ],
    }
