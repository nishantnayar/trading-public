"""Investable universe: load S&P 500 constituents from the committed CSV into `symbols`.

Point-in-time membership is a documented limitation of the starter setup — this seeds the
CURRENT S&P 500 list (survivorship bias noted in the README).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy.dialects.postgresql import insert

from quantis.db.engine import session_scope
from quantis.db.models import Symbol

UNIVERSE_CSV = Path(__file__).resolve().parents[3] / "data" / "universe" / "sp500.csv"


def load_universe_csv(path: Path = UNIVERSE_CSV) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    missing = {"symbol", "name", "sector"} - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    return df[["symbol", "name", "sector"]]


def seed_symbols(path: Path = UNIVERSE_CSV) -> int:
    """Upsert the universe into `symbols`. Returns number of rows upserted."""
    df = load_universe_csv(path)
    rows = df.to_dict("records")
    for r in rows:
        r["active"] = True

    with session_scope() as session:
        stmt = insert(Symbol).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Symbol.symbol],
            set_={
                "name": stmt.excluded.name,
                "sector": stmt.excluded.sector,
                "active": stmt.excluded.active,
            },
        )
        session.execute(stmt)
    logger.info("seeded {} symbols from {}", len(rows), path.name)
    return len(rows)


def active_symbols() -> list[str]:
    """Return the list of active tickers, sorted."""
    with session_scope() as session:
        rows = (
            session.query(Symbol.symbol)
            .filter(Symbol.active.is_(True))
            .order_by(Symbol.symbol)
            .all()
        )
    return [r[0] for r in rows]
