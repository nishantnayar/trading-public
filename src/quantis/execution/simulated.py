"""In-process broker with optional Postgres persistence.

Fills at the supplied mark (normally yesterday's close). Shorts are allowed: selling
a name you do not own just increases cash and records a negative qty. This is a
research ledger, not a locate/borrow model.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from quantis.db.engine import session_scope
from quantis.db.models import BrokerAccount, BrokerFill, BrokerPosition
from quantis.execution.types import Account, Fill, Order

DEFAULT_CASH = 100_000.0


class SimulatedBroker:
    """In-process broker. `name` is the ledger key when persist=True."""

    def __init__(
        self, cash: float = DEFAULT_CASH, persist: bool = False, name: str = "simulated"
    ) -> None:
        self.name = name
        self.persist = persist
        self._cash = cash
        self._qty: dict[str, float] = {}
        if persist:
            self._load()

    def _load(self) -> None:
        with session_scope() as session:
            acct = session.get(BrokerAccount, self.name)
            if acct is not None:
                self._cash = float(acct.cash)
            rows = session.execute(
                select(BrokerPosition).where(BrokerPosition.broker == self.name)
            ).scalars()
            self._qty = {row.symbol: float(row.qty) for row in rows if float(row.qty) != 0}

    def _save(self, fills: list[Fill]) -> None:
        with session_scope() as session:
            stmt = insert(BrokerAccount).values(broker=self.name, cash=self._cash)
            session.execute(
                stmt.on_conflict_do_update(
                    index_elements=[BrokerAccount.broker],
                    set_={"cash": stmt.excluded.cash},
                )
            )
            session.execute(delete(BrokerPosition).where(BrokerPosition.broker == self.name))
            for symbol, qty in self._qty.items():
                if abs(qty) < 1e-9:
                    continue
                session.add(BrokerPosition(broker=self.name, symbol=symbol, qty=qty))
            for fill in fills:
                session.add(
                    BrokerFill(
                        broker=self.name,
                        symbol=fill.symbol,
                        side=fill.side,
                        qty=fill.qty,
                        price=fill.price,
                        status=fill.status,
                        submitted_at=fill.submitted_at or datetime.now(UTC),
                        detail=fill.detail or None,
                    )
                )

    def submit(self, orders: list[Order], prices: dict[str, float]) -> list[Fill]:
        fills: list[Fill] = []
        for order in orders:
            if order.qty <= 0:
                raise ValueError(f"qty must be > 0, got {order.qty} for {order.symbol}")
            price = prices.get(order.symbol)
            if price is None or price <= 0:
                fills.append(
                    Fill(
                        symbol=order.symbol,
                        side=order.side,
                        qty=order.qty,
                        price=0.0,
                        status="rejected",
                        detail="no mark price",
                        submitted_at=datetime.now(UTC),
                    )
                )
                continue
            signed = order.qty if order.side == "buy" else -order.qty
            self._cash -= signed * price
            self._qty[order.symbol] = self._qty.get(order.symbol, 0.0) + signed
            fills.append(
                Fill(
                    symbol=order.symbol,
                    side=order.side,
                    qty=order.qty,
                    price=float(price),
                    status="filled",
                    submitted_at=datetime.now(UTC),
                )
            )
        if self.persist:
            self._save(fills)
        return fills

    def positions(self) -> dict[str, float]:
        return {s: q for s, q in self._qty.items() if abs(q) > 1e-9}

    def account(self, prices: dict[str, float] | None = None) -> Account:
        prices = prices or {}
        mtm = sum(qty * prices.get(symbol, 0.0) for symbol, qty in self._qty.items())
        equity = self._cash + mtm
        return Account(
            cash=self._cash,
            equity=equity,
            buying_power=self._cash,
            broker=self.name,
        )
