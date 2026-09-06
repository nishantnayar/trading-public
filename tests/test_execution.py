"""Paper broker: simulated ledger, order generation, live-trading lock."""

from __future__ import annotations

import pytest
from sqlalchemy import delete

from quantis.execution.alpaca import AlpacaPaperClient, LiveTradingDisabled
from quantis.execution.rebalance import MIN_NOTIONAL, orders_for_targets
from quantis.execution.simulated import SimulatedBroker
from quantis.execution.types import Order


def test_simulated_buy_and_short_update_cash_and_qty() -> None:
    broker = SimulatedBroker(cash=10_000, persist=False)
    fills = broker.submit(
        [
            Order("AAA", "buy", 10),
            Order("BBB", "sell", 5),
        ],
        {"AAA": 100.0, "BBB": 40.0},
    )
    assert all(f.status == "filled" for f in fills)
    assert broker.account({"AAA": 100.0, "BBB": 40.0}).cash == pytest.approx(9_200)
    assert broker.positions() == {"AAA": 10.0, "BBB": -5.0}
    assert broker.account({"AAA": 100.0, "BBB": 40.0}).equity == pytest.approx(10_000)


def test_missing_price_rejects_without_changing_the_book() -> None:
    broker = SimulatedBroker(cash=1_000, persist=False)
    fills = broker.submit([Order("ZZZ", "buy", 1)], prices={})
    assert fills[0].status == "rejected"
    assert broker.positions() == {}
    assert broker.account({}).cash == pytest.approx(1_000)


def test_rejects_non_positive_qty() -> None:
    broker = SimulatedBroker(persist=False)
    with pytest.raises(ValueError, match="qty must be > 0"):
        broker.submit([Order("AAA", "buy", 0)], {"AAA": 1.0})


def test_orders_for_targets_closes_and_opens() -> None:
    orders = orders_for_targets(
        target_weights={"AAA": 0.5, "BBB": -0.5},
        current_qty={"AAA": 10.0},
        prices={"AAA": 100.0, "BBB": 50.0},
        equity=10_000,
    )
    by_symbol = {o.symbol: o for o in orders}
    assert by_symbol["AAA"].side == "buy"
    assert by_symbol["AAA"].qty == pytest.approx(40.0)
    assert by_symbol["BBB"].side == "sell"
    assert by_symbol["BBB"].qty == pytest.approx(100.0)


def test_orders_skip_dust_notional() -> None:
    orders = orders_for_targets(
        target_weights={"AAA": 0.5},
        current_qty={"AAA": 50.0},
        prices={"AAA": 100.0},
        equity=10_000,
    )
    assert orders == []
    tiny = orders_for_targets(
        target_weights={"AAA": 0.5},
        current_qty={"AAA": 50.0 - (MIN_NOTIONAL - 1) / 100.0},
        prices={"AAA": 100.0},
        equity=10_000,
    )
    assert tiny == []


def test_orders_require_positive_equity() -> None:
    with pytest.raises(ValueError, match="equity must be > 0"):
        orders_for_targets({"AAA": 1.0}, {}, {"AAA": 10.0}, equity=0)


def test_simulated_persists_to_postgres() -> None:
    from quantis.db.engine import get_engine, session_scope
    from quantis.db.models import Base, BrokerAccount, BrokerFill, BrokerPosition

    Base.metadata.create_all(get_engine())
    with session_scope() as session:
        session.execute(delete(BrokerFill).where(BrokerFill.broker == "test-sim"))
        session.execute(delete(BrokerPosition).where(BrokerPosition.broker == "test-sim"))
        session.execute(delete(BrokerAccount).where(BrokerAccount.broker == "test-sim"))
    broker = SimulatedBroker(cash=8_000, persist=True, name="test-sim")
    broker.submit([Order("AAA", "buy", 2)], {"AAA": 50.0})
    reloaded = SimulatedBroker(cash=0, persist=True, name="test-sim")
    assert reloaded.positions()["AAA"] == pytest.approx(2.0)
    with session_scope() as session:
        acct = session.get(BrokerAccount, "test-sim")
        assert acct is not None
        assert float(acct.cash) == pytest.approx(7_900)


def test_make_broker_rejects_unknown_names() -> None:
    from quantis.execution.broker import make_broker

    with pytest.raises(ValueError, match="unknown broker"):
        make_broker("live")


def test_alpaca_adapter_refuses_live_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from quantis import config as config_mod

    config_mod.get_settings.cache_clear()
    monkeypatch.setenv("ALPACA_PAPER", "false")
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    config_mod.get_settings.cache_clear()
    with pytest.raises(LiveTradingDisabled, match="will not submit live"):
        AlpacaPaperClient()
    config_mod.get_settings.cache_clear()
