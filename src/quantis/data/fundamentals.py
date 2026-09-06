"""Quarterly fundamentals: a FundamentalSource interface with a yfinance implementation.

Alpaca does not serve fundamentals, so this is a separate source from prices. Mirrors the
`PriceSource` pattern in `prices.py` so a paid vendor can be swapped in later.

Point-in-time: yfinance exposes the fiscal `period_end` but NOT the SEC filing date, so
`as_of` (the date the figures are treated as public) is derived as
`period_end + REPORTING_LAG_DAYS`. See docs/LIMITATIONS.md.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Protocol

import httpx
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


class EdgarFundamentals:
    """Quarterly fundamentals from SEC EDGAR's XBRL company-facts API.

    The correct fix for the yfinance gap: free, no API key, and one companyfacts call
    returns a filer's ENTIRE XBRL history (often 10+ years), unlike yfinance's ~5-quarter
    cap. Crucially, each fact carries `filed` — the actual SEC filing date — so `as_of`
    here is a real point-in-time anchor, not `period_end + assumed_lag`.

    Duration facts (revenue, income, cash flow) are filed at multiple granularities
    (quarterly AND cumulative YTD/annual) with no tag distinguishing them; this filters
    to facts whose (end - start) is ~1 quarter (80-100 days) to keep only standalone
    quarterly figures. Some filers only tag YTD cumulative values with no
    quarter-length variant, so quarterly coverage is not guaranteed for every metric on
    every filer — see docs/LIMITATIONS.md. `total_debt` is left null: no single XBRL
    tag (LongTermDebt vs LongTermDebtNoncurrent vs DebtCurrent vs ...) is used
    consistently enough across filers to trust without per-filer mapping.
    """

    name = "edgar"

    _TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    _FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    _REQUEST_PAUSE = 0.15  # SEC allows <=10 req/s; stay comfortably under it
    _FORMS = ("10-Q", "10-K")
    _MIN_QUARTER_DAYS, _MAX_QUARTER_DAYS = 80, 100

    _DURATION_CONCEPTS: dict[str, tuple[str, ...]] = {
        "revenue": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        "gross_profit": ("GrossProfit",),
        "operating_income": ("OperatingIncomeLoss",),
        "net_income": ("NetIncomeLoss", "ProfitLoss"),
        "operating_cash_flow": (
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ),
        "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    }
    _INSTANT_CONCEPTS: dict[str, tuple[str, ...]] = {
        "total_assets": ("Assets",),
        "total_equity": (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        "shares_outstanding": (
            "CommonStockSharesOutstanding",
            "EntityCommonStockSharesOutstanding",
        ),
    }

    def __init__(self, user_agent: str | None = None) -> None:
        if user_agent is None:
            from quantis.config import get_settings

            user_agent = get_settings().edgar_user_agent
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}, timeout=20.0
        )
        self._cik_map: dict[str, str] | None = None

    @staticmethod
    def _bucket_period_ends(
        sorted_ends: list[dt.date], tolerance_days: int = 10
    ) -> dict[dt.date, dt.date]:
        """Map each raw `end` date to a canonical period anchor.

        Consecutive `end` dates within `tolerance_days` of each other are treated as
        the same fiscal quarter (see the pass-1 comment above); the earliest date in
        each cluster becomes that cluster's key.
        """
        bucket: dict[dt.date, dt.date] = {}
        anchor: dt.date | None = None
        for end in sorted_ends:
            if anchor is None or (end - anchor).days > tolerance_days:
                anchor = end
            bucket[end] = anchor
        return bucket

    # Concepts many filers tag ONLY as YTD-cumulative in 10-Qs (3/6/9-month figures),
    # never as a standalone quarter — cash-flow-statement items are the classic case.
    # These get reconstructed via fiscal-year differencing (see
    # `_reconstruct_standalone_quarters`) as a fallback for whatever the direct
    # quarterly-duration pass (span 80-100 days) didn't already capture.
    _RECONSTRUCT_FROM_YTD = ("operating_cash_flow",)

    @staticmethod
    def _reconstruct_standalone_quarters(
        unit_facts: list[dict],
    ) -> list[tuple[dt.date, dt.date, float]]:
        """Difference consecutive YTD-cumulative facts within a fiscal year.

        EDGAR's `fy`/`fp` tags identify each duration fact as Q1/Q2/Q3 (cumulative
        from fiscal-year start) or FY (annual) regardless of its raw span, which is
        exactly what's needed to recover a standalone quarter: Q1 is already
        standalone; Q2 minus Q1, Q3 minus Q2, and FY minus Q3 recover Q2/Q3/Q4. A
        fiscal year missing an earlier quarter breaks the chain from that point (a
        gap can't be differenced away), which simply yields less reconstructed
        coverage for that filer/year rather than a wrong number.
        """
        by_period: dict[tuple[int, str], tuple[dt.date, dt.date, float]] = {}
        for fact in unit_facts:
            fy, fp = fact.get("fy"), fact.get("fp")
            start, end, filed = fact.get("start"), fact.get("end"), fact.get("filed")
            if fy is None or fp is None or not start or not end or not filed:
                continue
            end_d, filed_d = dt.date.fromisoformat(end), dt.date.fromisoformat(filed)
            key = (fy, fp)
            if key not in by_period or filed_d < by_period[key][1]:
                by_period[key] = (end_d, filed_d, fact["val"])

        out: list[tuple[dt.date, dt.date, float]] = []
        for fy in sorted({fy for fy, _ in by_period}):
            prev_val, prev_filed = 0.0, None
            for fp in ("Q1", "Q2", "Q3", "FY"):
                key = (fy, fp)
                if key not in by_period:
                    break
                end_d, filed_d, cum_val = by_period[key]
                quarter_val = cum_val - prev_val
                quarter_filed = max(filed_d, prev_filed) if prev_filed else filed_d
                out.append((end_d, quarter_filed, quarter_val))
                prev_val, prev_filed = cum_val, filed_d
        return out

    def _tickers_to_ciks(self) -> dict[str, str]:
        if self._cik_map is not None:
            return self._cik_map
        resp = self._client.get(self._TICKERS_URL)
        resp.raise_for_status()
        self._cik_map = {
            str(row["ticker"]).upper(): str(row["cik_str"]).zfill(10)
            for row in resp.json().values()
        }
        return self._cik_map

    def get_quarterly(self, symbols: list[str]) -> pd.DataFrame:
        ciks = self._tickers_to_ciks()
        frames: list[pd.DataFrame] = []
        for symbol in symbols:
            cik = ciks.get(symbol.upper())
            if cik is None:
                logger.warning("no EDGAR CIK found for {}", symbol)
                continue
            try:
                frame = self._one_symbol(cik, symbol)
                if not frame.empty:
                    frames.append(frame)
            except Exception as exc:  # noqa: BLE001 — one bad filer must not kill the batch
                logger.warning("EDGAR fundamentals failed for {}: {}", symbol, exc)
            time.sleep(self._REQUEST_PAUSE)
        if not frames:
            return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)
        return pd.concat(frames, ignore_index=True)

    def _one_symbol(self, cik: str, symbol: str) -> pd.DataFrame:
        resp = self._client.get(self._FACTS_URL.format(cik=int(cik)))
        if resp.status_code == 404:
            return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)
        resp.raise_for_status()
        facts = resp.json().get("facts", {}).get("us-gaap", {})

        # Pass 1: collect every candidate fact as (end, filed, column, val). Different
        # concepts tag the SAME fiscal quarter with slightly different `end` dates
        # (e.g. a 52/53-week fiscal Saturday-close for balance-sheet facts vs a
        # calendar quarter-end for some income-statement facts), so an exact-date join
        # would silently split one quarter's data across two half-populated rows.
        raw: list[tuple[dt.date, dt.date, str, float]] = []

        for column, tags in self._DURATION_CONCEPTS.items():
            for tag in tags:
                for unit_facts in facts.get(tag, {}).get("units", {}).values():
                    for fact in unit_facts:
                        if fact.get("form") not in self._FORMS:
                            continue
                        start, end = fact.get("start"), fact.get("end")
                        if not start or not end:
                            continue
                        span = (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days
                        if not (self._MIN_QUARTER_DAYS <= span <= self._MAX_QUARTER_DAYS):
                            continue
                        raw.append(
                            (
                                dt.date.fromisoformat(end),
                                dt.date.fromisoformat(fact["filed"]),
                                column,
                                fact["val"],
                            )
                        )

        for column, tags in self._INSTANT_CONCEPTS.items():
            for tag in tags:
                for unit_facts in facts.get(tag, {}).get("units", {}).values():
                    for fact in unit_facts:
                        if fact.get("form") not in self._FORMS or not fact.get("end"):
                            continue
                        raw.append(
                            (
                                dt.date.fromisoformat(fact["end"]),
                                dt.date.fromisoformat(fact["filed"]),
                                column,
                                fact["val"],
                            )
                        )

        if not raw:
            return pd.DataFrame(columns=FUNDAMENTAL_COLUMNS)

        # Fallback for concepts many filers only tag as YTD-cumulative: reconstruct
        # the standalone quarter via fiscal-year differencing. Folded in AFTER the
        # as-reported facts below (via setdefault) so it only fills genuine gaps.
        reconstructed: list[tuple[dt.date, dt.date, str, float]] = []
        for column in self._RECONSTRUCT_FROM_YTD:
            for tag in self._DURATION_CONCEPTS[column]:
                unit_facts_all = [
                    f for units in facts.get(tag, {}).get("units", {}).values() for f in units
                ]
                for end_d, filed_d, val in self._reconstruct_standalone_quarters(unit_facts_all):
                    reconstructed.append((end_d, filed_d, column, val))

        # Pass 2: bucket `end` dates within a tolerance window so facts for the same
        # quarter land in one row regardless of which end-date convention tagged them.
        all_ends = sorted({end for end, _, _, _ in raw} | {end for end, _, _, _ in reconstructed})
        bucket_by_end = self._bucket_period_ends(all_ends)

        rows: dict[dt.date, dict[str, float]] = {}
        filed_by_period: dict[dt.date, dt.date] = {}
        # Earliest-filed value wins per (period, column): later facts for the same
        # quarter are restatements in a subsequent filing's comparative column, and
        # the point-in-time-honest figure is the one first reported. Reconstructed
        # (YTD-differenced) facts are folded in afterwards and never override an
        # as-reported standalone figure, since setdefault only fills missing columns.
        for end, filed, column, val in sorted(raw, key=lambda r: r[1]):
            period = bucket_by_end[end]
            rows.setdefault(period, {}).setdefault(column, val)
            filed_by_period[period] = max(filed_by_period.get(period, filed), filed)
        for end, filed, column, val in sorted(reconstructed, key=lambda r: r[1]):
            period = bucket_by_end[end]
            rows.setdefault(period, {}).setdefault(column, val)
            filed_by_period[period] = max(filed_by_period.get(period, filed), filed)

        records = []
        for period_end, values in sorted(rows.items()):
            record: dict[str, object] = {
                "symbol": symbol,
                "period_end": period_end,
                "as_of": filed_by_period[period_end],
            }
            for col in FUNDAMENTAL_COLUMNS:
                if col not in ("symbol", "period_end", "as_of"):
                    record[col] = values.get(col)
            records.append(record)

        out = pd.DataFrame(records, columns=FUNDAMENTAL_COLUMNS)
        value_columns = [
            c for c in FUNDAMENTAL_COLUMNS if c not in ("symbol", "period_end", "as_of")
        ]
        for col in value_columns:
            out[col] = out[col].astype("float64")
        out = out.dropna(subset=value_columns, how="all")
        logger.info("{}: {} usable quarterly periods (EDGAR)", symbol, len(out))
        return out
