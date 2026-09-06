"""Value/quality feature build: TTM ratios and the point-in-time asof merge.

The critical property (mirroring `tests/test_leakage.py` for price features): a
fundamental feature must never be visible on a trading day BEFORE its filing's
`as_of` date. `build_daily_fundamental_features` uses `merge_asof(direction="backward")`
for exactly this reason — these tests pin that behaviour down.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from quantis.features.fundamental_build import (
    FUND_FEATURE_NAMES,
    build_daily_fundamental_features,
    build_fundamental_events,
)


def _quarterly_fund(
    symbol: str, n_quarters: int, start: dt.date = dt.date(2023, 1, 1)
) -> pd.DataFrame:
    """n_quarters of clean, growing fundamentals for one symbol, filed 45 days later."""
    rows = []
    for i in range(n_quarters):
        period_end = start + dt.timedelta(days=91 * i)
        rows.append(
            {
                "symbol": symbol,
                "period_end": period_end,
                "as_of": period_end + dt.timedelta(days=45),
                "revenue": 1000.0 + 10 * i,
                "gross_profit": 400.0 + 4 * i,
                "net_income": 100.0 + i,
                "total_assets": 5000.0,
                "total_equity": 2000.0,
                "shares_outstanding": 100.0,
                "operating_cash_flow": 120.0 + i,
            }
        )
    return pd.DataFrame(rows)


def test_build_fundamental_events_requires_four_quarters() -> None:
    fund = _quarterly_fund("AAA", n_quarters=3)
    events = build_fundamental_events(fund)
    assert events.empty  # fewer than TTM_QUARTERS=4 -> no ratio can be computed


def test_build_fundamental_events_computes_ratios_on_fourth_quarter() -> None:
    fund = _quarterly_fund("AAA", n_quarters=4)
    events = build_fundamental_events(fund)
    assert len(events) == 1
    row = events.iloc[0]
    ttm_revenue = 1000 + 1010 + 1020 + 1030
    ttm_gross_profit = 400 + 404 + 408 + 412
    ttm_net_income = 100 + 101 + 102 + 103
    ttm_ocf = 120 + 121 + 122 + 123
    assert row["gross_margin"] == pytest.approx(ttm_gross_profit / ttm_revenue)
    assert row["roe_ttm"] == pytest.approx(ttm_net_income / 2000.0)
    assert row["accruals_ttm"] == pytest.approx((ttm_net_income - ttm_ocf) / 5000.0)


def test_daily_merge_never_sees_a_filing_before_its_as_of_date() -> None:
    """The core point-in-time guarantee: no look-ahead across the asof merge."""
    fund = _quarterly_fund("AAA", n_quarters=4)
    events = build_fundamental_events(fund)
    as_of = events.iloc[0]["as_of"]

    dates = pd.bdate_range(as_of - dt.timedelta(days=10), as_of + dt.timedelta(days=10))
    close_long = pd.DataFrame({"symbol": "AAA", "date": dates.date, "close": 50.0})

    daily = build_daily_fundamental_features(events, close_long)
    daily = daily.set_index("date")

    before = daily.loc[daily.index < as_of]
    on_or_after = daily.loc[daily.index >= as_of]

    assert before[FUND_FEATURE_NAMES].isna().all().all()
    assert on_or_after["gross_margin"].notna().all()


def test_book_to_market_uses_the_daily_close() -> None:
    fund = _quarterly_fund("AAA", n_quarters=4)
    events = build_fundamental_events(fund)
    as_of = events.iloc[0]["as_of"]

    dates = [as_of, as_of + dt.timedelta(days=1)]
    close_long = pd.DataFrame({"symbol": "AAA", "date": dates, "close": [40.0, 20.0]})

    daily = build_daily_fundamental_features(events, close_long).set_index("date")

    # total_equity=2000, shares_outstanding=100 -> market_cap = close * 100
    assert daily.loc[dates[0], "book_to_market"] == pytest.approx(2000.0 / (100.0 * 40.0))
    assert daily.loc[dates[1], "book_to_market"] == pytest.approx(2000.0 / (100.0 * 20.0))


def test_missing_shares_outstanding_leaves_book_to_market_null() -> None:
    fund = _quarterly_fund("AAA", n_quarters=4)
    fund["shares_outstanding"] = np.nan
    events = build_fundamental_events(fund)
    as_of = events.iloc[0]["as_of"]

    close_long = pd.DataFrame({"symbol": "AAA", "date": [as_of], "close": [40.0]})
    daily = build_daily_fundamental_features(events, close_long)

    assert daily["book_to_market"].isna().all()


def test_multiple_symbols_do_not_leak_into_each_other() -> None:
    fund = pd.concat(
        [_quarterly_fund("AAA", 4), _quarterly_fund("BBB", 4, start=dt.date(2023, 4, 1))],
        ignore_index=True,
    )
    events = build_fundamental_events(fund)
    assert set(events["symbol"]) == {"AAA", "BBB"}

    dates = pd.bdate_range("2023-01-01", "2024-03-01").date
    close_long = pd.concat(
        [
            pd.DataFrame({"symbol": "AAA", "date": dates, "close": 10.0}),
            pd.DataFrame({"symbol": "BBB", "date": dates, "close": 10.0}),
        ],
        ignore_index=True,
    )
    daily = build_daily_fundamental_features(events, close_long)
    assert set(daily["symbol"]) == {"AAA", "BBB"}
    # Each symbol's rows only ever pick up that symbol's own events.
    for symbol in ("AAA", "BBB"):
        sub = daily[daily["symbol"] == symbol]
        assert sub["gross_margin"].dropna().nunique() >= 1
