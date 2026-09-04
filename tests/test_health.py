"""Health-endpoint tests for the Agent API and the Mock ERP."""

from __future__ import annotations

from fastapi.testclient import TestClient

from invoice_agent.api.main import app as api_app
from invoice_agent.mock_erp.main import app as erp_app


def test_api_health() -> None:
    with TestClient(api_app) as client:
        resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_mock_erp_health() -> None:
    with TestClient(erp_app) as client:
        resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "mock-erp"


def test_openapi_available() -> None:
    with TestClient(api_app) as client:
        resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "/api/v1/health" in resp.json()["paths"]
