"""Pick a broker and turn the published target book into orders."""

from __future__ import annotations

from loguru import logger
from sqlalchemy import func, select

from quantis.config import get_settings
from quantis.db.engine import get_engine, session_scope
from quantis.db.models import Base, DailyBar, Position
from quantis.execution.rebalance import orders_for_targets
from quantis.execution.simulated import SimulatedBroker
from quantis.execution.types import ExecutionClient, Fill


def make_broker(kind: str | None = None, persist: bool = True) -> ExecutionClient:
    settings = get_settings()
    name = (kind or settings.quantis_broker).strip().lower()
    if name in {"simulated", "sim"}:
        Base.metadata.create_all(get_engine())
        return SimulatedBroker(persist=persist)
    if name in {"alpaca-paper", "alpaca_paper", "paper"}:
        from quantis.execution.alpaca import AlpacaPaperClient

        return AlpacaPaperClient()
    raise ValueError(f"unknown broker {name!r} — use 'simulated' or 'alpaca-paper'")


def latest_target_weights() -> tuple[dict[str, float], object]:
    with session_scope() as session:
        as_of = session.scalar(select(func.max(Position.date)))
        if as_of is None:
            return {}, None
        rows = session.execute(
            select(Position.symbol, Position.weight).where(Position.date == as_of)
        ).all()
    return {row.symbol: float(row.weight) for row in rows}, as_of


def latest_closes(symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {}
    with session_scope() as session:
        latest = (
            select(DailyBar.symbol, func.max(DailyBar.date).label("d"))
            .where(DailyBar.symbol.in_(symbols))
            .group_by(DailyBar.symbol)
            .subquery()
        )
        rows = session.execute(
            select(DailyBar.symbol, DailyBar.close).join(
                latest,
                (DailyBar.symbol == latest.c.symbol) & (DailyBar.date == latest.c.d),
            )
        ).all()
    return {row.symbol: float(row.close) for row in rows}


def rebalance(kind: str | None = None, persist: bool = True) -> dict:
    """Generate and submit orders that move the broker toward published weights."""
    targets, as_of = latest_target_weights()
    if not targets:
        raise RuntimeError("no published positions — run quantis.backtest.publish first")

    broker = make_broker(kind, persist=persist)
    prices = latest_closes(list(targets) + list(broker.positions()))
    account = broker.account(prices)
    orders = orders_for_targets(targets, broker.positions(), prices, account.equity)
    logger.info(
        "{}: {} target names, {} orders, equity={:.0f}, as_of={}",
        broker.name,
        len(targets),
        len(orders),
        account.equity,
        as_of,
    )
    fills = broker.submit(orders, prices) if orders else []
    filled = sum(1 for f in fills if f.status not in {"rejected", "canceled"})
    post = broker.account(prices)
    return {
        "broker": broker.name,
        "as_of": str(as_of),
        "n_orders": len(orders),
        "n_filled": filled,
        "n_rejected": len(fills) - filled,
        "equity": post.equity,
        "cash": post.cash,
        "fills": [_fill_dict(f) for f in fills],
    }


def _fill_dict(fill: Fill) -> dict:
    return {
        "symbol": fill.symbol,
        "side": fill.side,
        "qty": fill.qty,
        "price": fill.price,
        "status": fill.status,
        "detail": fill.detail,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI: uv run python -m quantis.execution.broker [--broker simulated|alpaca-paper]."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Rebalance the paper book to published weights.")
    parser.add_argument(
        "--broker",
        default=None,
        help="simulated (default) or alpaca-paper. alpaca-paper is refused if ALPACA_PAPER=false.",
    )
    args = parser.parse_args(argv)
    result = rebalance(kind=args.broker)
    print(json.dumps({k: v for k, v in result.items() if k != "fills"}, indent=2, default=str))
    print(f"fills: {result['n_filled']} filled, {result['n_rejected']} rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
