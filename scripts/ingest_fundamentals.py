"""Ingest quarterly fundamentals from yfinance.

PILOT SCOPE — defaults to 5 symbols. yfinance has no batch fundamentals endpoint, so a
full 502-name backfill is ~502 sequential HTTP calls and is rate-limit prone. See
docs/LIMITATIONS.md ("Fundamentals coverage") before scaling this up.

Run:  uv run python scripts/ingest_fundamentals.py                 # 5 pilot names
      uv run python scripts/ingest_fundamentals.py AAPL MSFT       # explicit names
      uv run python scripts/ingest_fundamentals.py --all           # full universe (slow)
"""

from __future__ import annotations

import sys
import time

from loguru import logger

from quantis.data.fundamentals import YFinanceFundamentals
from quantis.data.store import fundamental_coverage, upsert_fundamentals
from quantis.data.universe import active_symbols

PILOT_SYMBOLS = ["AAPL", "MSFT", "JPM", "XOM", "LLY"]

# Seconds between symbols — polite pacing so yfinance does not throttle a long backfill.
THROTTLE_SECONDS = 1.0


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    use_all = "--all" in argv

    if use_all:
        symbols = active_symbols()
        logger.warning(
            "full backfill of {} symbols — sequential yfinance calls, expect ~{:.0f} min",
            len(symbols),
            len(symbols) * (THROTTLE_SECONDS + 1.5) / 60,
        )
    else:
        symbols = [s.upper() for s in args] or PILOT_SYMBOLS
        logger.info("pilot run: {}", symbols)

    source = YFinanceFundamentals()
    total = 0
    for symbol in symbols:
        df = source.get_quarterly([symbol])
        total += upsert_fundamentals(df, source=source.name)
        time.sleep(THROTTLE_SECONDS)

    logger.info("rows written: {}", total)
    print(f"coverage: {fundamental_coverage()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
