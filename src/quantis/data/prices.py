"""Daily price bars: a PriceSource interface with an Alpaca implementation.

Alpaca is the primary source (same vendor as execution). yfinance is kept as a documented
fallback behind the same interface.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol

import pandas as pd
from loguru import logger

from quantis.config import get_settings

# Canonical bar columns produced by every PriceSource.
BAR_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume", "vwap", "trade_count"]


class PriceSource(Protocol):
    name: str

    def get_daily_bars(
        self, symbols: list[str], start: dt.date, end: dt.date
    ) -> pd.DataFrame:
        """Return a long DataFrame with BAR_COLUMNS (one row per symbol-date)."""
        ...


class AlpacaDailyBars:
    """Split/dividend-adjusted daily bars from Alpaca (free IEX feed)."""

    name = "alpaca"

    def __init__(self) -> None:
        from alpaca.data.historical import StockHistoricalDataClient

        s = get_settings()
        if not (s.alpaca_api_key and s.alpaca_secret_key):
            raise RuntimeError("Alpaca keys not set in .env")
        self._client = StockHistoricalDataClient(s.alpaca_api_key, s.alpaca_secret_key)

    def get_daily_bars(
        self, symbols: list[str], start: dt.date, end: dt.date
    ) -> pd.DataFrame:
        from alpaca.data.enums import Adjustment, DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        req = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=dt.datetime.combine(start, dt.time.min),
            end=dt.datetime.combine(end, dt.time.max),
            adjustment=Adjustment.ALL,  # split + dividend adjusted
            feed=DataFeed.IEX,  # free tier
        )
        resp = self._client.get_stock_bars(req)
        df = resp.df
        if df is None or df.empty:
            logger.warning("Alpaca returned no bars for {} symbols", len(symbols))
            return pd.DataFrame(columns=BAR_COLUMNS)
        return self._normalize(df)

    @staticmethod
    def _normalize(df: pd.DataFrame) -> pd.DataFrame:
        # resp.df is MultiIndex (symbol, timestamp) with columns:
        # open, high, low, close, volume, trade_count, vwap
        out = df.reset_index()
        out = out.rename(columns={"timestamp": "date"})
        out["date"] = pd.to_datetime(out["date"]).dt.tz_convert("America/New_York").dt.date
        for col in ("vwap", "trade_count"):
            if col not in out.columns:
                out[col] = None
        return out[BAR_COLUMNS]
