"""Small, hand-picked watchlist for the v1 signal layer.

Deliberately not `data.universe`'s full investable universe — the point of
starting here is to validate indicators/rules/engine end-to-end on a handful
of liquid, well-known names before scaling out.
"""

from __future__ import annotations

WATCHLIST: list[str] = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
