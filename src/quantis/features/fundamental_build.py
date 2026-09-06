"""Point-in-time value/quality feature build from `fundamentals` (EDGAR/yfinance).

Fundamentals arrive quarterly and far sparser than daily bars, so these features are
OPTIONAL by design: LightGBM handles missing values natively (a name with no filing yet,
or a filer whose XBRL tags didn't map, simply trains on the 11 price features for that
row). Do not `dropna` on these columns the way `dataset.load_features` does for price
features — that would gut the panel back to yfinance-pilot-only coverage. See
docs/LIMITATIONS.md.

Two steps:
1. `build_fundamental_events` — one row per FILING, keyed by the real SEC `as_of`
   (filing) date, with trailing-twelve-month (TTM) ratios computed from up to 4
   quarters of history.
2. `build_daily_fundamental_features` — `merge_asof` those events onto every trading
   day, so a filing is visible from its `as_of` date forward until superseded by the
   next one (point-in-time correct: never uses a filing before it was actually filed).
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from quantis.db.engine import session_scope
from quantis.db.models import DailyBar, Feature, Fundamental

FUND_FEATURE_NAMES = ["gross_margin", "roe_ttm", "accruals_ttm", "book_to_market"]

# Trailing-twelve-month window in quarters. Rows with fewer than 4 prior quarters for a
# symbol are left NaN rather than annualising a partial sum.
TTM_QUARTERS = 4

_RAW_COLUMNS = [
    "symbol",
    "period_end",
    "as_of",
    "revenue",
    "gross_profit",
    "net_income",
    "total_assets",
    "total_equity",
    "shares_outstanding",
    "operating_cash_flow",
]


def load_fundamentals_long() -> pd.DataFrame:
    """Raw quarterly fundamentals, one row per filed period."""
    columns = [getattr(Fundamental, name) for name in _RAW_COLUMNS]
    with session_scope() as session:
        rows = session.execute(
            select(*columns).order_by(Fundamental.symbol, Fundamental.period_end)
        ).all()
    df = pd.DataFrame(rows, columns=_RAW_COLUMNS)
    for col in _RAW_COLUMNS:
        if col not in ("symbol", "period_end", "as_of"):
            df[col] = df[col].astype(float)
    return df


def build_fundamental_events(fund: pd.DataFrame) -> pd.DataFrame:
    """One row per filing: (symbol, as_of, total_equity, shares_outstanding, <ratios>).

    TTM sums use a trailing 4-period rolling window over each symbol's own filed
    quarters (not calendar quarters — a filer with a gap simply waits longer for a full
    window, which is conservative rather than fabricating a quarter).
    """
    empty_cols = ["symbol", "as_of", "total_equity", "shares_outstanding", *FUND_FEATURE_NAMES[:3]]
    if fund.empty:
        return pd.DataFrame(columns=empty_cols)

    fund = fund.sort_values(["symbol", "period_end"]).reset_index(drop=True)

    def _ttm(col: str) -> pd.Series:
        return fund.groupby("symbol")[col].transform(
            lambda s: s.rolling(TTM_QUARTERS, min_periods=TTM_QUARTERS).sum()
        )

    fund["ttm_revenue"] = _ttm("revenue")
    fund["ttm_gross_profit"] = _ttm("gross_profit")
    fund["ttm_net_income"] = _ttm("net_income")
    fund["ttm_ocf"] = _ttm("operating_cash_flow")

    fund["gross_margin"] = fund["ttm_gross_profit"] / fund["ttm_revenue"].replace(0.0, pd.NA)
    fund["roe_ttm"] = fund["ttm_net_income"] / fund["total_equity"].replace(0.0, pd.NA)
    fund["accruals_ttm"] = (fund["ttm_net_income"] - fund["ttm_ocf"]) / fund[
        "total_assets"
    ].replace(0.0, pd.NA)

    events = fund[
        [
            "symbol",
            "as_of",
            "total_equity",
            "shares_outstanding",
            "gross_margin",
            "roe_ttm",
            "accruals_ttm",
        ]
    ]
    events = events.dropna(subset=["gross_margin", "roe_ttm", "accruals_ttm"], how="all")
    return events.sort_values(["symbol", "as_of"]).reset_index(drop=True)


def load_close_long(start: dt.date | None = None) -> pd.DataFrame:
    """Daily close, long format — the join target for the asof merge."""
    query = select(DailyBar.symbol, DailyBar.date, DailyBar.close)
    if start is not None:
        query = query.where(DailyBar.date >= start)
    with session_scope() as session:
        rows = session.execute(query.order_by(DailyBar.symbol, DailyBar.date)).all()
    df = pd.DataFrame(rows, columns=["symbol", "date", "close"])
    df["close"] = df["close"].astype(float)
    return df


def build_daily_fundamental_features(
    events: pd.DataFrame, close_long: pd.DataFrame
) -> pd.DataFrame:
    """As-of merge: each trading day gets the most recent filing known by that date."""
    out_cols = ["symbol", "date", *FUND_FEATURE_NAMES]
    if events.empty or close_long.empty:
        return pd.DataFrame(columns=out_cols)

    # merge_asof requires a numeric/datetime64 "on" key; DB reads and test fixtures both
    # hand back plain `datetime.date` objects (dtype=object), which it rejects outright.
    # merge_asof with a `by` group key still requires the "on" column sorted GLOBALLY
    # (not just within each group), so sort by date first, symbol only as a tiebreaker.
    close_long = close_long.assign(date=pd.to_datetime(close_long["date"]))
    close_long = close_long.sort_values(["date", "symbol"]).reset_index(drop=True)
    events = events.assign(as_of=pd.to_datetime(events["as_of"]))
    events = events.sort_values(["as_of", "symbol"]).reset_index(drop=True)

    merged = pd.merge_asof(
        close_long,
        events.rename(columns={"as_of": "date"}),
        on="date",
        by="symbol",
        direction="backward",
    )
    valid_shares = merged["shares_outstanding"].notna() & (merged["shares_outstanding"] > 0)
    merged["book_to_market"] = pd.NA
    merged.loc[valid_shares, "book_to_market"] = merged.loc[valid_shares, "total_equity"] / (
        merged.loc[valid_shares, "shares_outstanding"] * merged.loc[valid_shares, "close"]
    )
    merged["date"] = merged["date"].dt.date

    return merged[out_cols].copy()


def upsert_fundamental_features(df: pd.DataFrame) -> int:
    """Idempotent upsert of ONLY the 4 fundamental columns into `features`.

    Uses the same (symbol, date) primary key as the price feature store; a row that
    doesn't exist yet (fundamentals precede a price-feature build, or vice versa) is
    inserted with the other columns left null rather than being skipped.
    """
    if df.empty:
        return 0
    records = df.where(pd.notna(df), None).to_dict("records")
    written = 0
    with session_scope() as session:
        for i in range(0, len(records), 1000):
            chunk = records[i : i + 1000]
            stmt = insert(Feature).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Feature.symbol, Feature.date],
                set_={name: getattr(stmt.excluded, name) for name in FUND_FEATURE_NAMES},
            )
            session.execute(stmt)
            written += len(chunk)
    return written


def run(start: dt.date | None = None) -> dict:
    """Load fundamentals, compute point-in-time ratios, upsert daily features."""
    fund = load_fundamentals_long()
    if fund.empty:
        logger.warning("no fundamentals found — run scripts/ingest_fundamentals_edgar.py first")
        return {"rows": 0}

    events = build_fundamental_events(fund)
    if events.empty:
        logger.warning("no filing has a full TTM window yet — nothing to compute")
        return {"rows": 0}

    close_long = load_close_long(start)
    features = build_daily_fundamental_features(events, close_long)
    if start is not None:
        features = features[features["date"] >= start]

    written = upsert_fundamental_features(features)
    logger.info("wrote {} fundamental-feature rows", written)
    return {"rows": written}


if __name__ == "__main__":
    print(run())
