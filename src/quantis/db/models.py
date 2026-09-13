"""SQLAlchemy ORM models for the quantis database."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Symbol(Base):
    """A tradable instrument in the investable universe."""

    __tablename__ = "symbols"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(128))
    sector: Mapped[str | None] = mapped_column(String(64), index=True)
    exchange: Mapped[str | None] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    added_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bars: Mapped[list[DailyBar]] = relationship(back_populates="symbol_ref")


class DailyBar(Base):
    """One adjusted daily OHLCV bar for a symbol."""

    __tablename__ = "daily_bars"

    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("symbols.symbol", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)

    open: Mapped[float] = mapped_column(Numeric(18, 6))
    high: Mapped[float] = mapped_column(Numeric(18, 6))
    low: Mapped[float] = mapped_column(Numeric(18, 6))
    close: Mapped[float] = mapped_column(Numeric(18, 6))
    volume: Mapped[int] = mapped_column(BigInteger)
    vwap: Mapped[float | None] = mapped_column(Numeric(18, 6))
    trade_count: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(32), default="alpaca")
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    symbol_ref: Mapped[Symbol] = relationship(back_populates="bars")


class Fundamental(Base):
    """One quarterly fundamental report for a symbol, stored point-in-time.

    `period_end` is the fiscal period the figures describe; `as_of` is the date the
    figures were assumed to be publicly known. Features must filter on `as_of` (never
    `period_end`), otherwise the model would see numbers before they were published.
    Free sources do not expose true filing dates, so `as_of` is `period_end` plus a
    conservative reporting lag — a documented approximation, not a filing date.
    """

    __tablename__ = "fundamentals"

    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("symbols.symbol", ondelete="CASCADE"), primary_key=True
    )
    period_end: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    as_of: Mapped[dt.date] = mapped_column(Date, index=True)

    # Income statement (trailing quarter)
    revenue: Mapped[float | None] = mapped_column(Numeric(24, 4))
    gross_profit: Mapped[float | None] = mapped_column(Numeric(24, 4))
    operating_income: Mapped[float | None] = mapped_column(Numeric(24, 4))
    net_income: Mapped[float | None] = mapped_column(Numeric(24, 4))

    # Balance sheet
    total_assets: Mapped[float | None] = mapped_column(Numeric(24, 4))
    total_equity: Mapped[float | None] = mapped_column(Numeric(24, 4))
    total_debt: Mapped[float | None] = mapped_column(Numeric(24, 4))
    shares_outstanding: Mapped[float | None] = mapped_column(Numeric(24, 4))

    # Cash flow (drives the accruals quality feature)
    operating_cash_flow: Mapped[float | None] = mapped_column(Numeric(24, 4))
    capex: Mapped[float | None] = mapped_column(Numeric(24, 4))

    source: Mapped[str] = mapped_column(String(32), default="yfinance")
    reporting_lag_days: Mapped[int] = mapped_column(BigInteger, default=60)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Feature(Base):
    """One row of point-in-time features for a symbol on a date.

    Every column is computed from bars with `date <= this row's date` only. Execution is
    assumed at the NEXT session, so a feature row dated `t` is legitimately tradable at
    `t+1` without look-ahead. See `features/definitions.py` for each formula.
    """

    __tablename__ = "features"

    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("symbols.symbol", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True, index=True)

    # Momentum
    mom_1m: Mapped[float | None] = mapped_column(Numeric(18, 8))
    mom_3m: Mapped[float | None] = mapped_column(Numeric(18, 8))
    mom_6m: Mapped[float | None] = mapped_column(Numeric(18, 8))
    mom_12_1: Mapped[float | None] = mapped_column(Numeric(18, 8))

    # Short-term reversal
    ret_5d: Mapped[float | None] = mapped_column(Numeric(18, 8))

    # Volatility (annualised)
    vol_20d: Mapped[float | None] = mapped_column(Numeric(18, 8))
    vol_60d: Mapped[float | None] = mapped_column(Numeric(18, 8))

    # Technical
    rsi_14: Mapped[float | None] = mapped_column(Numeric(18, 8))
    dist_52w_high: Mapped[float | None] = mapped_column(Numeric(18, 8))
    ma_ratio_50_200: Mapped[float | None] = mapped_column(Numeric(18, 8))

    # Liquidity
    dollar_vol_20d: Mapped[float | None] = mapped_column(Numeric(18, 8))

    # Value / quality (from `fundamentals`, point-in-time asof `as_of`). Sparse by
    # design — coverage depends on the EDGAR backfill, and LightGBM handles the
    # resulting NaNs natively rather than requiring these columns complete.
    gross_margin: Mapped[float | None] = mapped_column(Numeric(18, 8))
    roe_ttm: Mapped[float | None] = mapped_column(Numeric(18, 8))
    accruals_ttm: Mapped[float | None] = mapped_column(Numeric(18, 8))
    book_to_market: Mapped[float | None] = mapped_column(Numeric(18, 8))

    computed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IngestRun(Base):
    """Audit row for each data-ingestion run (observability)."""

    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flow: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    symbols_processed: Mapped[int | None] = mapped_column(BigInteger)
    rows_written: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="running")
    detail: Mapped[str | None] = mapped_column(String(512))


class PortfolioSnapshot(Base):
    """Latest full-period backtest of the portfolio construction
    (quantis.signals.portfolio) - equal-weight, sector-capped, reallocated by
    default. One row, replaced on every run - a snapshot, not history.
    """

    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    period_start: Mapped[dt.date | None] = mapped_column(Date)
    period_end: Mapped[dt.date | None] = mapped_column(Date)
    trading_days: Mapped[int] = mapped_column(BigInteger)
    total_return: Mapped[float] = mapped_column(Numeric(18, 6))
    cagr: Mapped[float] = mapped_column(Numeric(18, 6))
    ann_vol: Mapped[float] = mapped_column(Numeric(18, 6))
    sharpe: Mapped[float] = mapped_column(Numeric(18, 6))
    max_drawdown: Mapped[float] = mapped_column(Numeric(18, 6))
    avg_names_long: Mapped[float] = mapped_column(Numeric(18, 4))
    avg_exposure: Mapped[float] = mapped_column(Numeric(18, 6))
    annualized_turnover: Mapped[float] = mapped_column(Numeric(18, 4))
    max_sector_weight: Mapped[float | None] = mapped_column(Numeric(18, 6))
    reallocated: Mapped[bool] = mapped_column(Boolean, default=True)
    max_name_weight: Mapped[float | None] = mapped_column(Numeric(18, 6))
    vol_target: Mapped[float | None] = mapped_column(Numeric(18, 6))
    avg_leverage: Mapped[float] = mapped_column(Numeric(18, 6), default=1.0)
    computed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BrokerAccount(Base):
    """Cash ledger for a simulated paper broker. One row per `broker` name."""

    __tablename__ = "broker_accounts"

    broker: Mapped[str] = mapped_column(String(32), primary_key=True)
    cash: Mapped[float] = mapped_column(Numeric(18, 4), default=100_000.0)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BrokerPosition(Base):
    """Current simulated holding of one symbol at one broker. Qty is signed
    (short would be negative; this system never shorts, so always >= 0).
    """

    __tablename__ = "broker_positions"

    broker: Mapped[str] = mapped_column(String(32), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    qty: Mapped[float] = mapped_column(Numeric(18, 6))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BrokerFill(Base):
    """One simulated fill from a rebalance - append-only history, unlike the
    account/position tables which hold current state.
    """

    __tablename__ = "broker_fills"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    broker: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8))
    qty: Mapped[float] = mapped_column(Numeric(18, 6))
    price: Mapped[float] = mapped_column(Numeric(18, 6))
    submitted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Signal(Base):
    """Latest trend-rule signal for one watchlist symbol (quantis.signals).

    One row per symbol - each run replaces that symbol's row, so this is
    always "the current signal", not a history. `date` is the bar the signal
    was computed on, not when the row was written.
    """

    __tablename__ = "signals"

    symbol: Mapped[str] = mapped_column(
        String(16), ForeignKey("symbols.symbol", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[dt.date] = mapped_column(Date)
    signal: Mapped[str] = mapped_column(String(8))
    close: Mapped[float] = mapped_column(Numeric(18, 6))
    sma_fast: Mapped[float | None] = mapped_column(Numeric(18, 6))
    sma_slow: Mapped[float | None] = mapped_column(Numeric(18, 6))
    mom_12_1: Mapped[float | None] = mapped_column(Numeric(18, 8))
    computed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
