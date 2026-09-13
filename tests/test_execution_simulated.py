"""Simulated broker rebalance planning — pure function, no DB."""

from __future__ import annotations

import pytest

from quantis.execution.simulated import MIN_TRADE_NOTIONAL, _plan_rebalance


def test_starting_from_all_cash_buys_the_full_target_book() -> None:
    plan = _plan_rebalance(
        weights={"A": 0.5, "B": 0.5},
        current_qty={},
        prices={"A": 100.0, "B": 50.0},
        cash=1000.0,
    )
    assert plan.equity == pytest.approx(1000.0)
    assert plan.positions["A"] == pytest.approx(5.0)  # 500 / 100
    assert plan.positions["B"] == pytest.approx(10.0)  # 500 / 50
    assert plan.cash == pytest.approx(0.0)
    assert {f.symbol for f in plan.fills} == {"A", "B"}
    assert all(f.side == "buy" for f in plan.fills)


def test_unchanged_weights_produce_no_fills() -> None:
    first = _plan_rebalance(weights={"A": 1.0}, current_qty={}, prices={"A": 100.0}, cash=1000.0)
    second = _plan_rebalance(
        weights={"A": 1.0},
        current_qty={"A": first.positions["A"]},
        prices={"A": 100.0},
        cash=first.cash,
    )
    assert second.fills == []
    assert second.positions == first.positions


def test_symbol_dropped_from_weights_is_fully_sold() -> None:
    plan = _plan_rebalance(
        weights={},
        current_qty={"A": 10.0},
        prices={"A": 100.0},
        cash=0.0,
    )
    assert "A" not in plan.positions
    assert len(plan.fills) == 1
    assert plan.fills[0].side == "sell"
    assert plan.fills[0].qty == pytest.approx(10.0)
    assert plan.cash == pytest.approx(1000.0)  # sold 10 shares @ 100
    assert plan.equity == pytest.approx(1000.0)  # unchanged by the trade itself


def test_trades_below_min_notional_are_skipped() -> None:
    # Already very close to target - the remaining delta is tiny dust.
    plan = _plan_rebalance(
        weights={"A": 1.0},
        current_qty={"A": 9.9999},
        prices={"A": 100.0},
        cash=0.01,
        min_trade_notional=MIN_TRADE_NOTIONAL,
    )
    assert plan.fills == []
    assert plan.positions["A"] == pytest.approx(9.9999)


def test_symbol_with_no_price_is_left_untouched() -> None:
    plan = _plan_rebalance(
        weights={"A": 1.0},
        current_qty={"A": 5.0},
        prices={},  # no price available for A this run
        cash=0.0,
    )
    assert plan.fills == []
    assert plan.positions["A"] == pytest.approx(5.0)
    assert plan.equity == pytest.approx(0.0)  # unpriced position marked at 0


def test_equity_is_conserved_across_a_rebalance() -> None:
    # Cash + position value before should equal cash + position value after,
    # since trades happen at the same marks used to compute equity.
    plan = _plan_rebalance(
        weights={"A": 0.3, "B": 0.7},
        current_qty={"A": 20.0, "C": 5.0},
        prices={"A": 50.0, "B": 25.0, "C": 200.0},
        cash=1000.0,
    )
    before_equity = 1000.0 + 20.0 * 50.0 + 5.0 * 200.0
    after_equity = plan.cash + sum(
        qty * {"A": 50.0, "B": 25.0, "C": 200.0}[s] for s, qty in plan.positions.items()
    )
    assert before_equity == pytest.approx(plan.equity)
    assert after_equity == pytest.approx(plan.equity)
