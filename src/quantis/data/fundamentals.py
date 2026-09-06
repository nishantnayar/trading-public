"""Quarterly fundamentals: a FundamentalSource interface with a yfinance implementation.

Alpaca does not serve fundamentals, so this is a separate source from prices. Mirrors the
`PriceSource` pattern in `prices.py` so a paid vendor can be swapped in later.

Point-in-time: yfinance exposes the fiscal `period_end` but NOT the SEC filing date, so
`as_of` (the date the figures are treated as public) is derived as
`period_end + REPORTING_LAG_DAYS`. See docs/LIMITATIONS.md.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol

import pandas as pd
from loguru import logger

# Conservative publication lag. Real 10-Qs land in 30-45 days; being late biases the
# system AGAINST leakage rather than toward it.
REPORTING_LAG_DAYS = 60

FUNDAMENTAL_COLUMNS = [
    "symbol",
    "period_end",
    "as_of",
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "total_assets",
    "total_equity",
    "total_debt",
    "shares_outstanding",
    "operating_cash_flow",
    "capex",
]

# Our column -> candidate yfinance row labels (they vary across tickers/versions).
_INCOME_MAP = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "Total Operating Income As Reported"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
}
_BALANCE_MAP = {
    "total_assets": ["Total Assets"],
    "total_equity": ["Stockholders Equity", "Total Equity Gross Minority Interest"],
    "total_debt": ["Total Debt"],
    "shares_outstanding": ["Ordinary Shares Number", "Share Issued"],
}
_CASHFLOW_MAP = {
    "operating_cash_flow": [
        "Operating Cash Flow",
        "Cash Flow From Continuing Operating Activities",
    ],
    "capex": ["Capital Expenditure"],
}


class FundamentalSource(Protocol):
    name: str

    def get_quarterly(self, symbols: list[str]) -> pd.DataFrame:
        """Return a long DataFrame with FUNDAMENTAL_COLUMNS (one row per symbol-period)."""
        ...


def _pick_row(df: pd.DataFrame, labels: list[str]) -> pd.Series | None:
    """First matching row from a yfinance statement frame, or None if absent."""
    if df is None or df.empty:
        return None
    for label in labels:
        if label in df.index:
            return df.loc[label]
    return None


class YFinanceFundamentals:
    """Quarterly income statement / balance sheet / cash flow from yfinance."""

    name = "yfinance"

    def __init__(self, lag_days: int = REPORTING_LAG_DAYS) -> None:
        self.lag_days = lag_days

    def get_quarterly(self, symbols: list[str]) -> pd.DataFrame:
        import yfinance as yf

        frames: list[pd.DataFrame] = []
        for symbol in symbols:
            try:
                frames.append(self._one_symbol(yf.Ticker(symbol), symbol))
            except Exception as exc:  # noqa: BLE001 — one bad ticker must not kill the batch
                logger.warning("fundamentals failed for {}: {}", symbol, exc)
        if not frames:
            return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)
        return pd.concat(frames, ignore_index=True)

    def _one_symbol(self, ticker, symbol: str) -> pd.DataFrame:
        statements = [
            (ticker.quarterly_income_stmt, _INCOME_MAP),
            (ticker.quarterly_balance_sheet, _BALANCE_MAP),
            (ticker.quarterly_cashflow, _CASHFLOW_MAP),
        ]

        columns: dict[str, pd.Series] = {}
        for frame, mapping in statements:
            for our_name, labels in mapping.items():
                row = _pick_row(frame, labels)
                if row is not None:
                    columns[our_name] = row

        if not columns:
            logger.warning("no fundamental rows found for {}", symbol)
            return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)

        out = pd.DataFrame(columns).reset_index(names="period_end")
        out["period_end"] = pd.to_datetime(out["period_end"]).dt.date
        out = out.dropna(subset=["period_end"])
        out["symbol"] = symbol
        out["as_of"] = out["period_end"].map(lambda d: d + dt.timedelta(days=self.lag_days))

        for column in FUNDAMENTAL_COLUMNS:
            if column not in out.columns:
                out[column] = None

        # yfinance pads its oldest columns with all-NaN periods — drop those so coverage
        # counts reflect genuinely usable quarters.
        keys = ("symbol", "period_end", "as_of")
        value_columns = [c for c in FUNDAMENTAL_COLUMNS if c not in keys]
        out = out.dropna(subset=value_columns, how="all")

        logger.info("{}: {} usable quarterly periods", symbol, len(out))
        return out[FUNDAMENTAL_COLUMNS]
