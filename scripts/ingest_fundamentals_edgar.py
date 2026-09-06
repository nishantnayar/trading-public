"""Ingest quarterly fundamentals from SEC EDGAR (companyfacts XBRL API).

One companyfacts call returns a filer's ENTIRE XBRL history (often 10+ years), unlike
yfinance's ~5-quarter cap — so a full-universe backfill is feasible in minutes, not the
~20 min a yfinance run would need for a single year of data. `as_of` is the SEC's own
`filed` date per fact, a genuine point-in-time anchor. See docs/LIMITATIONS.md.

Run:
    uv run python scripts/ingest_fundamentals_edgar.py            # full active universe
    uv run python scripts/ingest_fundamentals_edgar.py AAPL MSFT  # subset
"""

from __future__ import annotations

import sys

from loguru import logger

from quantis.data.fundamentals import EdgarFundamentals
from quantis.data.store import fundamental_coverage, upsert_fundamentals
from quantis.data.universe import active_symbols

BATCH_SIZE = 25


def main(argv: list[str]) -> int:
    symbols = [s.upper() for s in argv] or active_symbols()
    logger.info("EDGAR fundamentals backfill: {} symbols", len(symbols))

    source = EdgarFundamentals()
    total = 0
    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i : i + BATCH_SIZE]
        df = source.get_quarterly(batch)
        written = upsert_fundamentals(df, source=source.name)
        total += written
        logger.info(
            "batch {}-{}/{}: {} rows written (running total {})",
            i,
            i + len(batch),
            len(symbols),
            written,
            total,
        )

    logger.info("rows written: {}", total)
    print(f"coverage: {fundamental_coverage()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
