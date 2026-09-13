"""Latest portfolio-construction backtest snapshot (quantis.signals.portfolio)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from quantis.api import queries_portfolio as q

router = APIRouter()


@router.get("/portfolio")
def portfolio() -> dict | None:
    try:
        return q.latest_portfolio()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
