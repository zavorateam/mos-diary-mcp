from datetime import date
from fastapi.testclient import TestClient
import pytest

from models import SessionConfig
import mosdiary_server
from mosdiary_server import api_app


@pytest.fixture(autouse=True)
def setup_server_config(mock_session_config: SessionConfig, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(mosdiary_server, "_current_config", mock_session_config)
    monkeypatch.setattr(mosdiary_server, "get_active_config", lambda: mock_session_config)


def test_health():
    client = TestClient(api_app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_auth_token_endpoint(mock_jwt_token: str, monkeypatch: pytest.MonkeyPatch):
    client = TestClient(api_app)
    monkeypatch.setattr(
        mosdiary_server,
        "login_with_token",
        lambda raw_token, profile_id: SessionConfig(token=raw_token, profile_id="999"),
    )
    resp = client.post("/api/auth/token", json={"token": mock_jwt_token})
    assert resp.status_code == 200
    assert "999" in resp.json()["message"]


def test_homeworks_endpoint_optional_date(monkeypatch: pytest.MonkeyPatch):
    """Проверяет эндпоинт ДЗ как с датой по умолчанию (None), так и с переданной."""
    client = TestClient(api_app)

    monkeypatch.setattr(
        "mosdiary_server.TasksService.get_homeworks",
        lambda self, start, end: [],
    )

    # Без передачи start_date (дефолт из Query)
    resp = client.get("/api/tasks/homeworks")
    assert resp.status_code == 200
    assert resp.json() == []

    # С явной передачей start_date
    resp = client.get("/api/tasks/homeworks?start_date=2026-09-20&days=7")
    assert resp.status_code == 200