"""Point-in-time correctness of the fundamentals loader."""

from __future__ import annotations

import datetime as dt

import pandas as pd

from quantis.data.fundamentals import (
    FUNDAMENTAL_COLUMNS,
    REPORTING_LAG_DAYS,
    YFinanceFundamentals,
    _pick_row,
)


class _FakeTicker:
    """Mimics the yfinance statement frames: rows = line items, columns = period ends."""

    def __init__(self, periods: list[str]) -> None:
        self._cols = [pd.Timestamp(p) for p in periods]
        self.quarterly_income_stmt = pd.DataFrame(
            [[100.0] * len(periods), [40.0] * len(periods)],
            index=["Total Revenue", "Net Income"],
            columns=self._cols,
        )
        self.quarterly_balance_sheet = pd.DataFrame(
            [[900.0] * len(periods)], index=["Total Assets"], columns=self._cols
        )
        self.quarterly_cashflow = pd.DataFrame(
            [[55.0] * len(periods)], index=["Operating Cash Flow"], columns=self._cols
        )


def test_as_of_is_lagged_past_period_end() -> None:
    """`as_of` must never equal `period_end` — figures aren't public on the period end."""
    source = YFinanceFundamentals()
    df = source._one_symbol(_FakeTicker(["2025-03-31", "2025-06-30"]), "TEST")

    assert not df.empty
    for row in df.itertuples():
        assert row.as_of > row.period_end
        assert (row.as_of - row.period_end).days == REPORTING_LAG_DAYS


def test_reporting_lag_is_configurable() -> None:
    source = YFinanceFundamentals(lag_days=90)
    df = source._one_symbol(_FakeTicker(["2025-03-31"]), "TEST")
    assert df.iloc[0]["as_of"] == dt.date(2025, 3, 31) + dt.timedelta(days=90)


def test_schema_and_missing_labels_are_null() -> None:
    """Absent yfinance labels yield null columns, never a crash or a shifted column."""
    df = YFinanceFundamentals()._one_symbol(_FakeTicker(["2025-03-31"]), "TEST")

    assert list(df.columns) == FUNDAMENTAL_COLUMNS
    assert df.iloc[0]["revenue"] == 100.0
    assert df.iloc[0]["net_income"] == 40.0
    # "Gross Profit" / "Total Debt" were not in the fake statements.
    assert pd.isna(df.iloc[0]["gross_profit"])
    assert pd.isna(df.iloc[0]["total_debt"])


def test_all_nan_periods_are_dropped() -> None:
    """yfinance pads its oldest columns with NaN; those rows must not inflate coverage."""
    ticker = _FakeTicker(["2025-03-31", "2025-06-30"])
    for frame in (
        ticker.quarterly_income_stmt,
        ticker.quarterly_balance_sheet,
        ticker.quarterly_cashflow,
    ):
        frame.iloc[:, 0] = float("nan")

    df = YFinanceFundamentals()._one_symbol(ticker, "TEST")
    assert len(df) == 1
    assert df.iloc[0]["period_end"] == dt.date(2025, 6, 30)


def test_pick_row_prefers_first_available_alias() -> None:
    frame = pd.DataFrame([[1.0]], index=["Operating Revenue"], columns=[pd.Timestamp("2025-03-31")])
    assert _pick_row(frame, ["Total Revenue", "Operating Revenue"]) is not None
    assert _pick_row(frame, ["Nonexistent"]) is None
    assert _pick_row(pd.DataFrame(), ["Total Revenue"]) is None
