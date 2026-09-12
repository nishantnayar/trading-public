"""Print the current trend signal, backtest it, or compare debounce variants.

uv run python -m quantis.signals
uv run python -m quantis.signals --backtest
uv run python -m quantis.signals --compare
uv run python -m quantis.signals --compare --detail
"""

from __future__ import annotations

import argparse

from quantis.signals.backtest import BacktestResult, compare_variants, run_watchlist
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


def _print_compare(detail: bool = False) -> None:
    results = compare_variants()
    print(f"period: {results[0].start} .. {results[0].end}  ({len(results)} rows)\n")

    by_variant: dict[str, list] = {}
    for result in results:
        by_variant.setdefault(result.variant, []).append(result)

    # Which variant has the best strategy_return for each symbol.
    by_symbol: dict[str, dict[str, BacktestResult]] = {}
    for result in results:
        by_symbol.setdefault(result.symbol, {})[result.variant] = result
    best_variant_per_symbol = [
        max(variants.items(), key=lambda kv: kv[1].strategy_return)[0]
        for variants in by_symbol.values()
    ]

    print(
        f"{'variant':<16}{'median strategy':>16}{'median sharpe':>15}"
        f"{'wins':>7}{'median trades':>15}"
    )
    for variant, rows in by_variant.items():
        wins = best_variant_per_symbol.count(variant)
        print(
            f"{variant:<16}"
            f"{_median([r.strategy_return for r in rows]):>15.1%} "
            f"{_median([r.sharpe for r in rows]):>14.2f} "
            f"{wins:>6} "
            f"{_median([r.n_trades for r in rows]):>14.0f}"
        )
    print()

    if detail:
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


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quantis trend signal (v1)")
    parser.add_argument("--backtest", action="store_true", help="run the historical backtest")
    parser.add_argument(
        "--compare", action="store_true", help="compare debounce variants side by side"
    )
    parser.add_argument(
        "--detail", action="store_true", help="with --compare, also print per-symbol rows"
    )
    args = parser.parse_args()

    if args.compare:
        _print_compare(detail=args.detail)
    elif args.backtest:
        _print_backtest()
    else:
        _print_signals()
