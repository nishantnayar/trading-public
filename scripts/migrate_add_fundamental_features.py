"""One-off migration: add the value/quality columns to an existing `features` table.

No Alembic is wired up yet (see docs/LIMITATIONS.md, "No Alembic migrations"), and
`Base.metadata.create_all()` only creates missing TABLES, not new columns on an
existing one. This adds the 4 nullable columns `build_fundamental.py` writes into,
safely (`IF NOT EXISTS`) and without touching the 754k existing price-feature rows.

Run:  uv run python scripts/migrate_add_fundamental_features.py
"""

from __future__ import annotations

from sqlalchemy import text

from quantis.db.engine import get_engine

COLUMNS = ["gross_margin", "roe_ttm", "accruals_ttm", "book_to_market"]


def main() -> int:
    engine = get_engine()
    with engine.begin() as conn:
        for column in COLUMNS:
            conn.execute(
                text(f"ALTER TABLE features ADD COLUMN IF NOT EXISTS {column} NUMERIC(18, 8)")
            )
            print(f"ensured column: {column}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
