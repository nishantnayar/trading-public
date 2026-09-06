"""Quantis FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quantis.api.routes.market import router as market_router
from quantis.api.routes.portfolio import router as portfolio_router
from quantis.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Quantis API", version="0.1.0")
    origins = [item.strip() for item in settings.api_cors_origins.split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(market_router)
    app.include_router(portfolio_router)
    return app


app = create_app()
