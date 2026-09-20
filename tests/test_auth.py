import time
import httpx
import pytest

from auth.session_manager import (
    decode_jwt,
    delete_session,
    load_session,
    login_with_token,
    refresh_token,
    save_session,
)
from models import SessionConfig


def test_decode_jwt_valid(mock_jwt_token: str):
    """Проверяет корректность декодирования JWT полезной нагрузки."""
    data = decode_jwt(mock_jwt_token)
    assert data.get("sub") == "2109290"
    assert data.get("msh") == "c3431963-069c-43a7-b71d-1f01c0c74ab9"
    assert data.get("exp") is not None


def test_decode_jwt_with_bearer_prefix(mock_jwt_token: str):
    """Проверяет, что префикс 'Bearer ' корректно отсекается."""
    data = decode_jwt(f"Bearer {mock_jwt_token}")
    assert data.get("sub") == "2109290"


def test_decode_jwt_invalid():
    """Проверяет поведение при передаче невалидного токена."""
    assert decode_jwt("invalid.token") == {}
    assert decode_jwt("") == {}


def test_save_and_load_session(mock_session_config: SessionConfig):
    """Проверяет цикл сохранения и чтения session.json без кук."""
    save_session(mock_session_config)
    loaded = load_session()
    assert loaded is not None
    assert loaded.token == mock_session_config.token
    assert loaded.profile_id == mock_session_config.profile_id
    assert loaded.person_id == mock_session_config.person_id
    assert loaded.expires_at == mock_session_config.expires_at


def test_delete_session(mock_session_config: SessionConfig):
    """Проверяет удаление session.json при logout."""
    save_session(mock_session_config)
    assert delete_session() is True
    assert load_session() is None
    assert delete_session() is False


def test_login_with_token_auto_detect_profile(mock_jwt_token: str, monkeypatch: pytest.MonkeyPatch):
    """Проверяет вход по токену с автоматическим определением профиля через API."""

    def mock_get(self, url, **kwargs):
        return httpx.Response(
            200,
            json={
                "profile": {"id": 5193007, "type": "student"},
                "children": [{"id": 5193007, "contingent_guid": "c3431963-069c-43a7-b71d-1f01c0c74ab9"}],
            },
        )

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    cfg = login_with_token(mock_jwt_token)
    assert cfg.profile_id == "5193007"
    assert cfg.person_id == "c3431963-069c-43a7-b71d-1f01c0c74ab9"
    assert cfg.token == mock_jwt_token



def test_refresh_token_success(mock_session_config: SessionConfig, monkeypatch: pytest.MonkeyPatch):
    """Проверяет успешный вызов эндпоинта v2/token/refresh?roleId=1&subsystem=2."""
    new_token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIyMTA5MjkwIiwiaWF0IjoxNzg5ODg3ODM4LCJleHAiOjE3ODk5NzQyMzh9.new_sig"

    def mock_get(self, url, **kwargs):
        assert "roleId=1&subsystem=2" in str(url)
        headers = kwargs.get("headers", {})
        assert headers.get("Authorization") == f"Bearer {mock_session_config.token}"
        return httpx.Response(200, text=f'"{new_token}"')

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    refreshed = refresh_token(mock_session_config)
    assert refreshed is not None
    assert refreshed.token == new_token
    assert refreshed.expires_at == 1789974238


def test_refresh_token_parent_role(mock_session_config: SessionConfig, monkeypatch: pytest.MonkeyPatch):
    """Проверяет передачу roleId=2 для профиля родителя."""
    mock_session_config.profile_type = "parent"

    def mock_get(client, url, **kwargs):
        assert "roleId=2&subsystem=2" in str(url)
        return httpx.Response(200, text='"token"')

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    refresh_token(mock_session_config)