"""Vectorized long/flat backtest of the trend rule, with a flat-bps cost model.
A sanity check on the rule, not a replacement for the old backtest engine:
position is taken the day *after* a signal (no look-ahead), held flat
otherwise, and compared to buy-and-hold.

Cost model: `cost_bps_per_side` charged on every position *change* (entry or
exit), same convention as the deleted `quantis.backtest` engine
(`cost = |w(t) - w(t-1)| * bps_per_side`) but for a binary 0/1 position
instead of a portfolio weight. A full round trip (entry then exit) costs
`2 * cost_bps_per_side`. No market impact, no slippage dispersion, no
borrow — see docs/LIMITATIONS.md.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from quantis.db.engine import session_scope
from quantis.db.models import Symbol
from quantis.signals.engine import load_price_history
from quantis.signals.rules import TrendParams, compute_signal
from quantis.signals.universe import full_universe

DEFAULT_COST_BPS_PER_SIDE = 10.0


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    strategy_return: float
    buy_hold_return: float
    sharpe: float
    n_trades: int
    time_in_market: float
    net_return: float = 0.0
    net_sharpe: float = 0.0
    break_even_bps: float = 0.0
    cost_bps_per_side: float = 0.0
    variant: str = ""
    start: str = ""
    end: str = ""


def _daily_returns(
    df: pd.DataFrame,
    params: TrendParams | None,
    cost_bps_per_side: float,
) -> pd.DataFrame:
    """Per-day gross/net return, position, and trade flag for one symbol.

    Position is the day *after* a signal (no look-ahead). Shared by
    `backtest_symbol` (aggregate stats) and the sector/regime breakdowns
    (need the day-by-day series, not just a total).
    """
    signals = compute_signal(df, params)
    daily_return = signals["close"].pct_change()
    is_long = signals["signal"] == "long"
    position = is_long.shift(1, fill_value=False)
    strategy_return = daily_return * position

    position_int = position.astype(int)
    trade_flag = (position_int - position_int.shift(1, fill_value=0)).abs()
    net_return = strategy_return - trade_flag * (cost_bps_per_side / 10_000)

    return pd.DataFrame(
        {
            "date": signals["date"],
            "gross_return": strategy_return,
            "net_return": net_return,
            "position": position,
            "trade_flag": trade_flag,
        }
    )


def backtest_symbol(
    df: pd.DataFrame,
    params: TrendParams | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
) -> BacktestResult:
    """df must have `date` and `close` columns, ascending. Returns summary stats."""
    daily = _daily_returns(df, params, cost_bps_per_side)
    daily_return = df["close"].pct_change()

    n_trades = int(daily["trade_flag"].sum())
    time_in_market = float(daily["position"].mean())

    strategy_total = float((1 + daily["gross_return"].fillna(0)).prod() - 1)
    net_total = float((1 + daily["net_return"].fillna(0)).prod() - 1)
    buy_hold_total = float((1 + daily_return.fillna(0)).prod() - 1)
    sharpe = _annualized_sharpe(daily["gross_return"])
    net_sharpe = _annualized_sharpe(daily["net_return"])
    break_even = _break_even_bps(daily["gross_return"], daily["trade_flag"])

    return BacktestResult(
        symbol="",
        strategy_return=strategy_total,
        buy_hold_return=buy_hold_total,
        sharpe=sharpe,
        n_trades=n_trades,
        time_in_market=time_in_market,
        net_return=net_total,
        net_sharpe=net_sharpe,
        break_even_bps=break_even,
        cost_bps_per_side=cost_bps_per_side,
        start=str(daily["date"].iloc[0]),
        end=str(daily["date"].iloc[-1]),
    )


def run_watchlist(
    symbols: list[str] | None = None,
    params: TrendParams | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
) -> list[BacktestResult]:
    """Backtest each symbol in `symbols` (default: the full active universe)
    over its full stored history."""
    symbols = symbols if symbols is not None else full_universe()
    results = []
    for symbol in symbols:
        history = load_price_history(symbol)
        if history.empty:
            continue
        result = backtest_symbol(history, params, cost_bps_per_side)
        results.append(dataclasses.replace(result, symbol=symbol))
    return results


def _symbol_sectors(symbols: list[str]) -> dict[str, str]:
    with session_scope() as session:
        rows = session.query(Symbol.symbol, Symbol.sector).filter(Symbol.symbol.in_(symbols)).all()
    return {symbol: (sector or "Unknown") for symbol, sector in rows}


@dataclass(frozen=True)
class SectorResult:
    sector: str
    n_symbols: int
    median_net_return: float
    median_gross_return: float
    median_sharpe: float
    net_win_rate: float  # share of symbols with net_return > 0


def sector_breakdown(
    symbols: list[str] | None = None,
    params: TrendParams | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
) -> list[SectorResult]:
    """Same backtest, grouped by GICS sector — where is the net loss concentrated?"""
    results = run_watchlist(symbols, params, cost_bps_per_side)
    sectors = _symbol_sectors([r.symbol for r in results])

    by_sector: dict[str, list[BacktestResult]] = {}
    for result in results:
        sector = sectors.get(result.symbol, "Unknown")
        by_sector.setdefault(sector, []).append(result)

    out = []
    for sector, rows in by_sector.items():
        net_returns = [r.net_return for r in rows]
        out.append(
            SectorResult(
                sector=sector,
                n_symbols=len(rows),
                median_net_return=_median(net_returns),
                median_gross_return=_median([r.strategy_return for r in rows]),
                median_sharpe=_median([r.sharpe for r in rows]),
                net_win_rate=sum(1 for x in net_returns if x > 0) / len(net_returns),
            )
        )
    return sorted(out, key=lambda s: s.median_net_return, reverse=True)


@dataclass(frozen=True)
class RegimeResult:
    year: int
    return_pct: float
    avg_names_long: float
    trading_days: int


def regime_breakdown(
    symbols: list[str] | None = None,
    params: TrendParams | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
) -> list[RegimeResult]:
    """Year-by-year return of an equal-weighted book of whatever names are
    currently long each day — not per-symbol totals, so it shows *when* the
    rule made or lost money across the universe, not just which names.
    """
    symbols = symbols if symbols is not None else full_universe()
    frames = []
    for symbol in symbols:
        history = load_price_history(symbol)
        if history.empty:
            continue
        frames.append(_daily_returns(history, params, cost_bps_per_side))
    if not frames:
        return []

    all_days = pd.concat(frames, ignore_index=True)
    all_days["date"] = pd.to_datetime(all_days["date"])
    long_days = all_days[all_days["position"]]

    daily_book_return = long_days.groupby("date")["net_return"].mean()
    daily_breadth = long_days.groupby("date")["net_return"].size()

    full_index = pd.Index(sorted(all_days["date"].unique()))
    daily_book_return = daily_book_return.reindex(full_index, fill_value=0.0)
    daily_breadth = daily_breadth.reindex(full_index, fill_value=0)

    out = []
    for year, year_returns in daily_book_return.groupby(daily_book_return.index.year):
        year_breadth = daily_breadth.loc[year_returns.index]
        out.append(
            RegimeResult(
                year=int(year),
                return_pct=float((1 + year_returns).prod() - 1),
                avg_names_long=float(year_breadth.mean()),
                trading_days=len(year_returns),
            )
        )
    return out


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2


# Named parameter sets for side-by-side comparison, not just the current default.
VARIANTS: dict[str, TrendParams] = {
    "no_debounce": TrendParams(entry_confirm_days=1, exit_confirm_days=1),
    "exit_only": TrendParams(entry_confirm_days=1, exit_confirm_days=3),
    "entry_and_exit": TrendParams(entry_confirm_days=3, exit_confirm_days=3),
}


def compare_variants(
    symbols: list[str] | None = None,
    variants: dict[str, TrendParams] | None = None,
    cost_bps_per_side: float = DEFAULT_COST_BPS_PER_SIDE,
) -> list[BacktestResult]:
    """Every symbol (default: the full active universe) backtested under every
    named variant, over its full history."""
    symbols = symbols if symbols is not None else full_universe()
    variants = variants or VARIANTS
    results = []
    for name, params in variants.items():
        for result in run_watchlist(symbols, params, cost_bps_per_side):
            results.append(dataclasses.replace(result, variant=name))
    return results


def _annualized_sharpe(returns: pd.Series, trading_days: int = 252) -> float:
    returns = returns.dropna()
    if returns.std(ddof=0) == 0 or returns.empty:
        return 0.0
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(trading_days))


def _net_total_at_bps(strategy_return: pd.Series, trade_flag: pd.Series, bps: float) -> float:
    net = strategy_return - trade_flag * (bps / 10_000)
    return float((1 + net.fillna(0)).prod() - 1)


_BREAK_EVEN_SEARCH_CAP_BPS = 1_000.0  # 10% per side — already far past any realistic cost


def _break_even_bps(strategy_return: pd.Series, trade_flag: pd.Series) -> float:
    """Flat bps-per-side at which compounded net return is exactly zero.

    `inf` if the rule never trades (costs can never bite); 0 if it is already
    unprofitable gross; `_BREAK_EVEN_SEARCH_CAP_BPS` if it survives even that
    (a floor, not the true break-even). Otherwise bisected.

    The search is capped well below 10,000 bps (100% per trade) on purpose:
    past that a single trade's cost exceeds the position's full value, so
    `1 + net_return` on that day goes negative, and a compounded product of
    several negative daily terms can land back on a spuriously *positive*
    total — breaking the monotonicity bisection depends on. No real cost
    figure is anywhere near that range, so the cap costs nothing in practice.
    """
    if trade_flag.sum() == 0:
        return math.inf
    if _net_total_at_bps(strategy_return, trade_flag, 0.0) <= 0:
        return 0.0
    lo, hi = 0.0, _BREAK_EVEN_SEARCH_CAP_BPS
    for _ in range(60):
        mid = (lo + hi) / 2
        if _net_total_at_bps(strategy_return, trade_flag, mid) > 0:
            lo = mid
        else:
            hi = mid
    return lo
