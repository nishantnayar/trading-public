"""Print the current trend signal for each watchlist symbol.

uv run python -m quantis.signals
"""

from __future__ import annotations

from quantis.signals.engine import latest_signals

if __name__ == "__main__":
    for row in latest_signals():
        print(row)
