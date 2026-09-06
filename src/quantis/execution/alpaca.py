"""Alpaca *paper* adapter. Live trading is a hard error, not a config switch.

Construction refuses to proceed unless `ALPACA_PAPER` is true, and the TradingClient
is always created with `paper=True`. There is no code path that points at the live
endpoint.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from quantis.config import get_settings
from quantis.execution.types import Account, Fill, Order


class LiveTradingDisabled(RuntimeError):
    """Raised if anyone tries to construct the adapter with paper mode off."""


class AlpacaPaperClient:
    name = "alpaca-paper"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.alpaca_paper:
            raise LiveTradingDisabled("ALPACA_PAPER is false — Quantis will not submit live orders")
        if not (settings.alpaca_api_key and settings.alpaca_secret_key):
            raise RuntimeError("Alpaca keys not set in .env")
        from alpaca.trading.client import TradingClient

        # paper=True is load-bearing. Do not thread settings.alpaca_paper in here.
        self._client = TradingClient(
            settings.alpaca_api_key, settings.alpaca_secret_key, paper=True
        )

    @staticmethod
    def _to_alpaca(symbol: str) -> str:
        return symbol.replace("-", ".")

    @staticmethod
    def _from_alpaca(symbol: str) -> str:
        return symbol.replace(".", "-")

    def submit(self, orders: list[Order], prices: dict[str, float]) -> list[Fill]:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        fills: list[Fill] = []
        for order in orders:
            request = MarketOrderRequest(
                symbol=self._to_alpaca(order.symbol),
                qty=round(order.qty, 4),
                side=OrderSide.BUY if order.side == "buy" else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
            try:
                submitted = self._client.submit_order(request)
                status = str(getattr(submitted, "status", "submitted"))
                fills.append(
                    Fill(
                        symbol=order.symbol,
                        side=order.side,
                        qty=order.qty,
                        price=float(prices.get(order.symbol) or 0.0),
                        status=status,
                        submitted_at=datetime.now(UTC),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                fills.append(
                    Fill(
                        symbol=order.symbol,
                        side=order.side,
                        qty=order.qty,
                        price=0.0,
                        status="rejected",
                        detail=str(exc)[:500],
                        submitted_at=datetime.now(UTC),
                    )
                )
        return fills

    def positions(self) -> dict[str, float]:
        # alpaca-py types get_all_positions() as list[Position | str]; cast to Any so the
        # attribute reads type-check against the SDK's over-broad union.
        out: dict[str, float] = {}
        for pos in cast(list[Any], self._client.get_all_positions()):
            qty = float(pos.qty)
            if str(pos.side) == "short":
                qty = -abs(qty)
            out[self._from_alpaca(str(pos.symbol))] = qty
        return out

    def account(self, prices: dict[str, float] | None = None) -> Account:
        # get_account() is typed TradeAccount | dict; cast to Any to read fields.
        raw = cast(Any, self._client.get_account())
        return Account(
            cash=float(raw.cash),
            equity=float(raw.equity),
            buying_power=float(raw.buying_power),
            broker=self.name,
        )
