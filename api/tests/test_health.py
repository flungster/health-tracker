"""Tests for the health endpoint.

These tests run against the compose database (``make up`` must be running),
which is also where the real migrations live.
"""

import importlib.metadata
from typing import Any

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_when_database_is_reachable() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["status"] == "ok"
    assert body["api"] == "ok"
    assert body["database"] == "ok"


def test_health_reports_the_api_version() -> None:
    response = client.get("/api/v1/health")
    body: dict[str, Any] = response.json()
    assert body["version"] == importlib.metadata.version("health-tracker-api")
