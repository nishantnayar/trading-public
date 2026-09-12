"""Print the current trend signal, or backtest it, for the watchlist.

uv run python -m quantis.signals
uv run python -m quantis.signals --backtest
"""

from __future__ import annotations

import argparse

from quantis.signals.backtest import run_watchlist
from quantis.signals.engine import latest_signals


def _print_signals() -> None:
    for row in latest_signals():
        print(row)


def _print_backtest() -> None:
    header = f"{'symbol':<8}{'strategy':>12}{'buy_hold':>12}{'sharpe':>9}{'trades':>8}{'in_mkt':>8}"
    print(header)
    for result in run_watchlist():
        print(
            f"{result.symbol:<8}"
            f"{result.strategy_return:>11.1%} "
            f"{result.buy_hold_return:>11.1%} "
            f"{result.sharpe:>8.2f} "
            f"{result.n_trades:>7} "
            f"{result.time_in_market:>7.0%}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quantis trend signal (v1)")
    parser.add_argument("--backtest", action="store_true", help="run the historical backtest")
    args = parser.parse_args()

    if args.backtest:
        _print_backtest()
    else:
        _print_signals()
