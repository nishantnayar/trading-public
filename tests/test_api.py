"""Smoke tests for the FastAPI app."""

from fastapi.testclient import TestClient

from quantis.api.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_portfolio_routes_are_mounted() -> None:
    paths = set(app.openapi()["paths"])
    for path in ("/signals", "/signals/quintiles", "/positions", "/model", "/broker"):
        assert path in paths
