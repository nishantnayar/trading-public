"""Print the current trend signal, backtest it, or compare debounce variants.

uv run python -m quantis.signals
uv run python -m quantis.signals --backtest
uv run python -m quantis.signals --compare
"""

from __future__ import annotations

import argparse

from quantis.signals.backtest import compare_variants, run_watchlist
from quantis.signals.engine import latest_signals

_ROW = "{symbol:<8}{strategy:>11.1%} {buy_hold:>11.1%} {sharpe:>8.2f} {trades:>7} {in_mkt:>7.0%}"
_HEADER = f"{'symbol':<8}{'strategy':>12}{'buy_hold':>12}{'sharpe':>9}{'trades':>8}{'in_mkt':>8}"


def _print_signals() -> None:
    for row in latest_signals():
        print(row)


def _print_backtest() -> None:
    print(_HEADER)
    for result in run_watchlist():
        print(
            _ROW.format(
                symbol=result.symbol,
                strategy=result.strategy_return,
                buy_hold=result.buy_hold_return,
                sharpe=result.sharpe,
                trades=result.n_trades,
                in_mkt=result.time_in_market,
            )
        )


def _print_compare() -> None:
    results = compare_variants()
    print(f"period: {results[0].start} .. {results[0].end}\n")
    by_variant: dict[str, list] = {}
    for result in results:
        by_variant.setdefault(result.variant, []).append(result)

    for variant, rows in by_variant.items():
        print(f"-- {variant} --")
        print(_HEADER)
        for result in rows:
            print(
                _ROW.format(
                    symbol=result.symbol,
                    strategy=result.strategy_return,
                    buy_hold=result.buy_hold_return,
                    sharpe=result.sharpe,
                    trades=result.n_trades,
                    in_mkt=result.time_in_market,
                )
            )
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quantis trend signal (v1)")
    parser.add_argument("--backtest", action="store_true", help="run the historical backtest")
    parser.add_argument(
        "--compare", action="store_true", help="compare debounce variants side by side"
    )
    args = parser.parse_args()

    if args.compare:
        _print_compare()
    elif args.backtest:
        _print_backtest()
    else:
        _print_signals()
