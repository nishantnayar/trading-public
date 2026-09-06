"""Published scores, target weights, and model diagnostics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from quantis.api import queries_portfolio as q

router = APIRouter()


@router.get("/signals")
def signals() -> dict:
    try:
        return q.signals_snapshot()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/signals/quintiles")
def quintiles() -> list[dict]:
    try:
        return q.quintile_labels()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/positions")
def positions() -> dict:
    try:
        return q.positions_snapshot()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/model")
def model() -> dict:
    try:
        return q.model_snapshot()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/broker")
def broker() -> dict:
    try:
        return q.broker_snapshot()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
