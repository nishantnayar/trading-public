"""Current simulated paper broker state (quantis.execution.simulated)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from quantis.execution.simulated import account_state

router = APIRouter()


@router.get("/broker")
def broker() -> dict | None:
    try:
        return account_state()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
