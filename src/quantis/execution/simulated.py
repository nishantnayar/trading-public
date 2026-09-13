"""A fake broker: an in-database cash + position ledger, rebalanced toward
`quantis.signals.portfolio.target_weights` by simulated fills. No real order
is ever submitted anywhere in this module - see docs/LIMITATIONS.md for
everything this simplification skips (slippage dispersion, borrow, market
impact, financing).

Fill price is each symbol's latest close (`daily_bars`) - the same bar the
target weights were computed from, not the next session's open. That means
no information leaks into the fill (the close was already public when the
signal used it), but it is a simplification: a real order submitted after
that close would fill somewhere else. Documented, not hidden.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from quantis.db.engine import session_scope
from quantis.db.models import BrokerAccount, BrokerFill, BrokerPosition, DailyBar
from quantis.signals.portfolio import target_weights

DEFAULT_BROKER = "simulated"
STARTING_CASH = 100_000.0
MIN_TRADE_NOTIONAL = 10.0  # skip trades this small - rounding dust, not a real rebalance


def _latest_prices(symbols: list[str]) -> dict[str, float]:
    """Each symbol's most recent *valid* (`close > 0`) close in `daily_bars` -
    not necessarily the same calendar date for every symbol (one may have
    lagged an ingest run, or gone stale), and not necessarily today: this
    deliberately has no recency cutoff, so a symbol that stopped getting
    fresh bars still marks at its last known good price rather than
    disappearing. A symbol absent from the result has *never* had a valid
    bar - that's the case `_plan_rebalance` treats as genuinely unpriced.
    """
    if not symbols:
        return {}
    with session_scope() as session:
        latest_date = (
            select(DailyBar.symbol, func.max(DailyBar.date).label("max_date"))
            .where(DailyBar.symbol.in_(symbols), DailyBar.close > 0)
            .group_by(DailyBar.symbol)
            .subquery()
        )
        rows = session.execute(
            select(DailyBar.symbol, DailyBar.close).join(
                latest_date,
                (DailyBar.symbol == latest_date.c.symbol)
                & (DailyBar.date == latest_date.c.max_date),
            )
        ).all()
    return {row.symbol: float(row.close) for row in rows}


@dataclass(frozen=True)
class RebalanceResult:
    broker: str
    equity: float
    cash: float
    n_fills: int
    n_positions: int
    unpriced_symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlannedFill:
    symbol: str
    side: str  # "buy" or "sell"
    qty: float
    price: float


@dataclass(frozen=True)
class RebalancePlan:
    equity: float
    cash: float
    positions: dict[str, float]  # symbol -> new qty (0 entries mean "close")
    fills: list[PlannedFill]
    unpriced_symbols: tuple[str, ...] = ()


def _plan_rebalance(
    weights: dict[str, float],
    current_qty: dict[str, float],
    prices: dict[str, float],
    cash: float,
    min_trade_notional: float = MIN_TRADE_NOTIONAL,
) -> RebalancePlan:
    """Pure sizing logic, no I/O: given today's target weights, current
    holdings, prices, and cash, decide what to trade.

    A symbol in `prices` (see `_latest_prices` - already a *valid*, if
    possibly stale, close) is priced normally. A symbol with **no** entry in
    `prices` at all - never had a valid bar - is `unpriced`: its held
    quantity is left exactly as-is (neither traded nor treated as dust to
    drop), it is excluded from the equity calculation entirely (not valued
    at 0, which would silently understate equity and under-size every other
    target trade), and it is reported back via `unpriced_symbols` so the
    caller can surface it rather than the gap being invisible.

    Equity = cash + mark-to-market of *priced* current positions only.
    Target dollars per symbol = equity * weight; target shares = that /
    price. The trade is the delta between target and current shares,
    skipped if its notional is under `min_trade_notional`. A symbol held but
    absent from `weights` targets 0 (full sell).
    """
    # Defensive: treat a non-positive price exactly like a missing one, even
    # though `_latest_prices` shouldn't produce one - this function is also
    # called directly (tests, or a future caller) without going through it.
    valid_prices = {s: p for s, p in prices.items() if p > 0}
    unpriced = tuple(sorted(s for s in current_qty if s not in valid_prices))
    equity = cash + sum(
        qty * valid_prices[s] for s, qty in current_qty.items() if s in valid_prices
    )

    new_positions = dict(current_qty)
    fills: list[PlannedFill] = []
    symbols = sorted(s for s in (set(weights) | set(current_qty)) if s in valid_prices)

    for symbol in symbols:
        price = valid_prices[symbol]
        target_qty = (equity * weights.get(symbol, 0.0)) / price
        delta_qty = target_qty - current_qty.get(symbol, 0.0)
        notional = abs(delta_qty) * price
        if notional < min_trade_notional:
            continue

        cash -= delta_qty * price
        new_positions[symbol] = target_qty
        fills.append(
            PlannedFill(
                symbol=symbol,
                side="buy" if delta_qty > 0 else "sell",
                qty=abs(delta_qty),
                price=price,
            )
        )

    # A position traded down to ~0 (dropped from the target book, or capped
    # out) is dead weight going forward - drop it rather than carry a
    # 1e-14-share position indefinitely. Unpriced positions are exempt: an
    # untouched quantity should never be mistaken for dust.
    new_positions = {s: q for s, q in new_positions.items() if s in unpriced or abs(q) >= 1e-9}

    return RebalancePlan(
        equity=equity,
        cash=cash,
        positions=new_positions,
        fills=fills,
        unpriced_symbols=unpriced,
    )


def rebalance(
    broker: str = DEFAULT_BROKER, weights: dict[str, float] | None = None
) -> RebalanceResult:
    """Move `broker`'s simulated ledger toward `weights` (default:
    `target_weights()`, today's construction) - see `_plan_rebalance` for the
    sizing logic and module docstring for what this deliberately doesn't
    model. Fractional shares are allowed; this is a simulation, not a real
    brokerage.
    """
    weights = weights if weights is not None else target_weights()

    with session_scope() as session:
        account = session.get(BrokerAccount, broker)
        if account is None:
            account = BrokerAccount(broker=broker, cash=STARTING_CASH)
            session.add(account)
            session.flush()

        positions = {
            p.symbol: p
            for p in session.query(BrokerPosition).filter(BrokerPosition.broker == broker)
        }
        prices = _latest_prices(sorted(set(weights) | set(positions)))
        current_qty = {symbol: float(p.qty) for symbol, p in positions.items()}

        plan = _plan_rebalance(weights, current_qty, prices, float(account.cash))

        for fill in plan.fills:
            session.add(BrokerFill(broker=broker, **fill.__dict__))

        for symbol, qty in plan.positions.items():
            if symbol in positions:
                positions[symbol].qty = qty
            else:
                session.add(BrokerPosition(broker=broker, symbol=symbol, qty=qty))
        for symbol in set(positions) - set(plan.positions):
            session.delete(positions[symbol])

        account.cash = plan.cash

    return RebalanceResult(
        broker=broker,
        equity=plan.equity,
        cash=plan.cash,
        n_fills=len(plan.fills),
        n_positions=len(plan.positions),
        unpriced_symbols=plan.unpriced_symbols,
    )


def account_state(broker: str = DEFAULT_BROKER) -> dict | None:
    """Current cash, mark-to-market equity, positions, and recent fills for
    `broker` - read-only, no trading. Returns `None` if the account has
    never been rebalanced.

    A position with no valid price (never had one - see `_latest_prices`) is
    marked `"stale": True` and excluded from `equity`, same treatment as in
    `_plan_rebalance` - not silently valued at 0.
    """
    with session_scope() as session:
        account = session.get(BrokerAccount, broker)
        if account is None:
            return None

        positions = list(session.query(BrokerPosition).filter(BrokerPosition.broker == broker))
        prices = _latest_prices([p.symbol for p in positions])
        equity = float(account.cash) + sum(
            float(p.qty) * prices[p.symbol] for p in positions if p.symbol in prices
        )
        unpriced_symbols = sorted(p.symbol for p in positions if p.symbol not in prices)

        recent_fills = list(
            session.query(BrokerFill)
            .filter(BrokerFill.broker == broker)
            .order_by(BrokerFill.submitted_at.desc())
            .limit(50)
        )

        return {
            "broker": broker,
            "cash": float(account.cash),
            "equity": equity,
            "updated_at": account.updated_at.isoformat() if account.updated_at else None,
            "unpriced_symbols": unpriced_symbols,
            "positions": [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "price": prices.get(p.symbol),
                    "market_value": float(p.qty) * prices[p.symbol] if p.symbol in prices else None,
                    "stale": p.symbol not in prices,
                }
                for p in sorted(positions, key=lambda p: p.symbol)
            ],
            "recent_fills": [
                {
                    "symbol": f.symbol,
                    "side": f.side,
                    "qty": float(f.qty),
                    "price": float(f.price),
                    "submitted_at": f.submitted_at.isoformat() if f.submitted_at else None,
                }
                for f in recent_fills
            ],
        }
