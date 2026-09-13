"""Universe used by quantis.signals.

Widened from an initial hand-picked 22-name, 9-sector watchlist to the full
active investable universe (~503 names, whatever `quantis.data.universe` has
seeded and ingested bars for) — the 22-name set was still a curated subset,
and tuning the entry/exit debounce parameters against it carried a real risk
of overfitting to that specific cohort rather than a property of the rule
that generalizes. See docs/LIMITATIONS.md. The old list is kept below,
unused by default, for quick small-sample manual runs.
"""

from __future__ import annotations

from quantis.data.universe import active_symbols

CURATED_WATCHLIST: list[str] = [
    # Information Technology
    "AAPL",
    "MSFT",
    "NVDA",
    "AMD",
    "CSCO",
    # Consumer Discretionary
    "AMZN",
    "TSLA",
    "ULTA",
    # Communication Services
    "GOOGL",
    "TMUS",
    "CMCSA",
    # Health Care
    "VRTX",
    "AMGN",
    "ALGN",
    # Financials
    "IBKR",
    "TROW",
    "WTW",
    # Industrials
    "CTAS",
    "UAL",
    # Energy / Staples / Utilities
    "APA",
    "MDLZ",
    "XEL",
]


def full_universe() -> list[str]:
    """All active symbols in `symbols` (whatever has been seeded), sorted.

    Not every one necessarily has ingested bar history — callers already
    skip symbols with no data (`load_price_history` returns an empty frame).
    """
    return active_symbols()
