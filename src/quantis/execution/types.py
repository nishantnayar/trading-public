"""Shared execution types. Qty is signed: buy > 0, sell/short < 0 in Fill.qty
after the fact; Order.qty is always positive and Order.side names the direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

Side = Literal["buy", "sell"]


@dataclass(frozen=True)
class Order:
    symbol: str
    side: Side
    qty: float  # always > 0


@dataclass
class Fill:
    symbol: str
    side: Side
    qty: float
    price: float
    status: str = "filled"
    detail: str = ""
    submitted_at: datetime | None = None


@dataclass
class Account:
    cash: float
    equity: float
    buying_power: float
    broker: str


class ExecutionClient(Protocol):
    name: str

    def submit(self, orders: list[Order], prices: dict[str, float]) -> list[Fill]:
        """Fill `orders`. `prices` is last/close used by the simulated book."""
        ...

    def positions(self) -> dict[str, float]:
        """Signed quantity by symbol."""
        ...

    def account(self, prices: dict[str, float] | None = None) -> Account: ...
