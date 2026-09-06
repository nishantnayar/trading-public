"""Smoke tests for the FastAPI app."""

from fastapi.testclient import TestClient

from quantis.api.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_portfolio_routes_are_mounted() -> None:
    from quantis.db.engine import get_engine
    from quantis.db.models import Base

    Base.metadata.create_all(get_engine())
    for path in ("/signals", "/positions", "/model"):
        assert client.get(path).status_code == 200
