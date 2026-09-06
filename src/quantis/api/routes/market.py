"""Live market-data endpoints (coverage, universe, bars, ingest)."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from quantis.api import queries

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "quantis-api"}


@router.get("/coverage")
def coverage() -> dict:
    try:
        return queries.coverage()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/universe")
def universe() -> list[dict]:
    try:
        return queries.universe_rows()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/sectors")
def sectors() -> list[dict]:
    try:
        return queries.sector_counts()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/bars/{symbol}")
def bars(
    symbol: str,
    start: Annotated[dt.date | None, Query()] = None,
    years: Annotated[int, Query(ge=1, le=10)] = 3,
) -> list[dict]:
    start = start or (dt.date.today() - dt.timedelta(days=365 * years))
    try:
        return queries.daily_bars(symbol.upper(), start)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/ingest-runs")
def ingest_runs(limit: Annotated[int, Query(ge=1, le=100)] = 20) -> list[dict]:
    try:
        return queries.ingest_runs(limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
