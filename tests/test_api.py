"""Smoke tests for the FastAPI app."""

from fastapi.testclient import TestClient

from quantis.api.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_signals_route_is_mounted() -> None:
    assert "/signals" in app.openapi()["paths"]


def test_portfolio_route_is_mounted() -> None:
    assert "/portfolio" in app.openapi()["paths"]
