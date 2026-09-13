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
    """Each symbol's most recent close in `daily_bars` (not necessarily the
    same calendar date for every symbol, if one lagged an ingest run)."""
    if not symbols:
        return {}
    with session_scope() as session:
        latest_date = (
            select(DailyBar.symbol, func.max(DailyBar.date).label("max_date"))
            .where(DailyBar.symbol.in_(symbols))
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


def _plan_rebalance(
    weights: dict[str, float],
    current_qty: dict[str, float],
    prices: dict[str, float],
    cash: float,
    min_trade_notional: float = MIN_TRADE_NOTIONAL,
) -> RebalancePlan:
    """Pure sizing logic, no I/O: given today's target weights, current
    holdings, prices, and cash, decide what to trade.

    Equity = cash + mark-to-market of current positions (symbols with no
    price available are valued at 0 - see `rebalance`'s docstring on stale
    data). Target dollars per symbol = equity * weight; target shares = that
    / price. The trade is the delta between target and current shares,
    skipped if its notional is under `min_trade_notional`. A symbol held but
    absent from `weights` targets 0 (full sell).
    """
    equity = cash + sum(qty * prices.get(symbol, 0.0) for symbol, qty in current_qty.items())

    new_positions = dict(current_qty)
    fills: list[PlannedFill] = []
    symbols = sorted(set(weights) | set(current_qty))

    for symbol in symbols:
        price = prices.get(symbol)
        if price is None or price <= 0:
            continue

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
    # 1e-14-share position indefinitely.
    new_positions = {s: q for s, q in new_positions.items() if abs(q) >= 1e-9}

    return RebalancePlan(equity=equity, cash=cash, positions=new_positions, fills=fills)


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
    )


def account_state(broker: str = DEFAULT_BROKER) -> dict | None:
    """Current cash, mark-to-market equity, positions, and recent fills for
    `broker` - read-only, no trading. Returns `None` if the account has
    never been rebalanced."""
    with session_scope() as session:
        account = session.get(BrokerAccount, broker)
        if account is None:
            return None

        positions = list(session.query(BrokerPosition).filter(BrokerPosition.broker == broker))
        prices = _latest_prices([p.symbol for p in positions])
        equity = float(account.cash) + sum(
            float(p.qty) * prices.get(p.symbol, 0.0) for p in positions
        )

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
            "positions": [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "price": prices.get(p.symbol),
                    "market_value": float(p.qty) * prices.get(p.symbol, 0.0),
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
