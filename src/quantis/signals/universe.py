"""Hand-picked watchlist for the v1 signal layer.

Deliberately not `data.universe`'s full 500+-name investable universe — the
point of starting here is to validate indicators/rules/engine on a bounded,
diversified set of liquid names before scaling out. Widened from the initial
5 mega-caps (all Tech/Comm. Services) to span sectors, so debounce-parameter
comparisons aren't just curve-fit to one narrow, strongly-trending cohort.
Every symbol here has bars back to 2020-07-27 in `daily_bars`.
"""

from __future__ import annotations

WATCHLIST: list[str] = [
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
