from click.testing import CliRunner
import pytest

from models import SessionConfig
import mosdiary_cli
from mosdiary_cli import cli


def test_cli_logout():
    runner = CliRunner()
    result = runner.invoke(cli, ["logout"])
    assert result.exit_code == 0


def test_cli_unauthorized_error(monkeypatch: pytest.MonkeyPatch):
    """Проверяет понятное сообщение при отсутствии сессии."""
    monkeypatch.setattr(mosdiary_cli, "load_session", lambda: None)
    runner = CliRunner()
    result = runner.invoke(cli, ["schedule"])
    assert result.exit_code != 0
    assert "Сессия не найдена" in result.output
    assert "mos-diary-cli login" in result.output


def test_cli_login_with_token(mock_jwt_token: str, monkeypatch: pytest.MonkeyPatch):
    """Проверяет команду авторизации mos-diary-cli login --token."""
    monkeypatch.setattr(
        mosdiary_cli,
        "login_with_token",
        lambda raw_token, profile_id: SessionConfig(token=raw_token, profile_id="5193007"),
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["login", "--token", mock_jwt_token])
    assert result.exit_code == 0
    assert "Успешный вход по токену" in result.output
    assert "5193007" in result.output