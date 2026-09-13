"""Current trend-rule signal for each watchlist symbol (quantis.signals)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from quantis.api import queries_signals as q

router = APIRouter()


@router.get("/signals")
def signals() -> list[dict]:
    try:
        return q.latest_signals()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
