"""Turn target weights into share orders against a current book."""

from __future__ import annotations

from quantis.execution.types import Order, Side

# Skip dust: a 0.5% name on a $100k book is $500; $10 is well below any real fill.
MIN_NOTIONAL = 10.0


def orders_for_targets(
    target_weights: dict[str, float],
    current_qty: dict[str, float],
    prices: dict[str, float],
    equity: float,
) -> list[Order]:
    """Delta the current book toward `equity * weight / price` shares.

    Names with no price are skipped (logged by the caller). Tiny notionals are
    dropped so a 0.01-share remainder does not become an order.
    """
    if equity <= 0:
        raise ValueError(f"equity must be > 0, got {equity}")

    symbols = set(target_weights) | set(current_qty)
    orders: list[Order] = []
    for symbol in sorted(symbols):
        price = prices.get(symbol)
        if price is None or price <= 0:
            continue
        target_qty = (target_weights.get(symbol, 0.0) * equity) / price
        delta = target_qty - current_qty.get(symbol, 0.0)
        notional = abs(delta) * price
        if notional < MIN_NOTIONAL:
            continue
        side: Side = "buy" if delta > 0 else "sell"
        orders.append(Order(symbol=symbol, side=side, qty=abs(delta)))
    return orders
