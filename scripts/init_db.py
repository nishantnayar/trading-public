"""Create all quantis tables (idempotent).

Run: uv run python scripts/init_db.py
"""

from __future__ import annotations

from quantis.db.engine import get_engine
from quantis.db.models import Base


def main() -> int:
    engine = get_engine()
    Base.metadata.create_all(engine)
    tables = ", ".join(sorted(Base.metadata.tables))
    print(f"Created/verified tables: {tables}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
