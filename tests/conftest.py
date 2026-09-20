import base64
import json
import time
from pathlib import Path
import pytest
from models import SessionConfig
import auth.session_manager as session_manager


@pytest.fixture
def mock_jwt_token() -> str:
    """Генерирует тестовый валидный JWT c полями msh, sub и exp на 24 часа."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).decode().rstrip("=")
    payload_data = {
        "sub": "2109290",
        "msh": "c3431963-069c-43a7-b71d-1f01c0c74ab9",
        "ath": "sudir",
        "iss": "https://school.mos.ru",
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400,
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    signature = "mock_signature"
    return f"{header}.{payload}.{signature}"


@pytest.fixture
def mock_session_config(mock_jwt_token: str) -> SessionConfig:
    return SessionConfig(
        token=mock_jwt_token,
        profile_id="5193007",
        profile_type="student",
        person_id="c3431963-069c-43a7-b71d-1f01c0c74ab9",
        expires_at=int(time.time()) + 86400,
    )


@pytest.fixture(autouse=True)
def isolated_session_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Изолирует session.json во временную папку tmp_path для каждого теста."""
    fake_session_file = tmp_path / "session.json"
    monkeypatch.setattr(session_manager, "SESSION_FILE", fake_session_file)
    return fake_session_file