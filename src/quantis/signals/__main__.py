"""Print the current trend signal, backtest it, or compare debounce variants.

uv run python -m quantis.signals
uv run python -m quantis.signals --backtest
uv run python -m quantis.signals --backtest --cost-bps 5
uv run python -m quantis.signals --compare
uv run python -m quantis.signals --compare --detail
uv run python -m quantis.signals --persist
"""

from __future__ import annotations

import argparse
import math

from quantis.signals.backtest import BacktestResult, compare_variants, run_watchlist
from quantis.signals.engine import latest_signals, persist_latest_signals

_ROW = (
    "{symbol:<8}{strategy:>10.1%} {net:>10.1%} {buy_hold:>11.1%} "
    "{sharpe:>7.2f} {net_sharpe:>7.2f} {be:>8} {trades:>7} {in_mkt:>7.0%}"
)
_HEADER = (
    f"{'symbol':<8}{'gross':>11}{'net':>11}{'buy_hold':>12}"
    f"{'sharpe':>8}{'net_shrp':>8}{'be_bps':>9}{'trades':>8}{'in_mkt':>8}"
)


def _fmt_be(bps: float) -> str:
    return "inf" if math.isinf(bps) else f"{bps:.1f}"


def _print_signals() -> None:
    for row in latest_signals():
        print(row)


def _print_backtest(cost_bps: float) -> None:
    print(f"cost model: {cost_bps:.1f} bps per side\n")
    print(_HEADER)
    for result in run_watchlist(cost_bps_per_side=cost_bps):
        print(
            _ROW.format(
                symbol=result.symbol,
                strategy=result.strategy_return,
                net=result.net_return,
                buy_hold=result.buy_hold_return,
                sharpe=result.sharpe,
                net_sharpe=result.net_sharpe,
                be=_fmt_be(result.break_even_bps),
                trades=result.n_trades,
                in_mkt=result.time_in_market,
            )
        )


def _print_compare(detail: bool = False, cost_bps: float = 10.0) -> None:
    results = compare_variants(cost_bps_per_side=cost_bps)
    print(f"period: {results[0].start} .. {results[0].end}  ({len(results)} rows)")
    print(f"cost model: {cost_bps:.1f} bps per side\n")

    by_variant: dict[str, list] = {}
    for result in results:
        by_variant.setdefault(result.variant, []).append(result)

    # Which variant has the best net_return for each symbol.
    by_symbol: dict[str, dict[str, BacktestResult]] = {}
    for result in results:
        by_symbol.setdefault(result.symbol, {})[result.variant] = result
    best_variant_per_symbol = [
        max(variants.items(), key=lambda kv: kv[1].net_return)[0] for variants in by_symbol.values()
    ]

    print(
        f"{'variant':<16}{'median gross':>14}{'median net':>14}{'median sharpe':>15}"
        f"{'net wins':>10}{'median trades':>15}"
    )
    for variant, rows in by_variant.items():
        wins = best_variant_per_symbol.count(variant)
        print(
            f"{variant:<16}"
            f"{_median([r.strategy_return for r in rows]):>13.1%} "
            f"{_median([r.net_return for r in rows]):>13.1%} "
            f"{_median([r.net_sharpe for r in rows]):>14.2f} "
            f"{wins:>9} "
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
                        net=result.net_return,
                        buy_hold=result.buy_hold_return,
                        sharpe=result.sharpe,
                        net_sharpe=result.net_sharpe,
                        be=_fmt_be(result.break_even_bps),
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
    parser.add_argument(
        "--persist", action="store_true", help="write latest signals to the signals table"
    )
    parser.add_argument(
        "--cost-bps",
        type=float,
        default=10.0,
        help="flat bps per side charged on every entry/exit (default: 10)",
    )
    args = parser.parse_args()

    if args.compare:
        _print_compare(detail=args.detail, cost_bps=args.cost_bps)
    elif args.backtest:
        _print_backtest(cost_bps=args.cost_bps)
    elif args.persist:
        n = persist_latest_signals()
        print(f"wrote {n} signal rows")
    else:
        _print_signals()
