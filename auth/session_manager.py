import base64
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from models import SessionConfig

logger = logging.getLogger("SessionManager")

SESSION_FILE = Path(__file__).resolve().parent.parent / "session.json"


def decode_jwt(token: str) -> Dict[str, Any]:
    """Декодирует полезную нагрузку JWT без верификации подписи."""
    try:
        token = token.strip()
        if token.startswith("Bearer "):
            token = token[7:]
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception:
        return {}


def load_session() -> Optional[SessionConfig]:
    """Загружает сохраненную сессию из session.json."""
    if not SESSION_FILE.exists():
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return SessionConfig(**data)
    except Exception as e:
        logger.warning(f"Ошибка загрузки session.json: {e}")
        return None


def save_session(cfg: SessionConfig) -> None:
    """Сохраняет чистую сессию без кук в session.json."""
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg.model_dump(exclude_none=True), f, indent=2, ensure_ascii=False)


def delete_session() -> bool:
    """Удаляет файл session.json (выход из системы)."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
        return True
    return False


def login_with_token(
    raw_token: str,
    profile_id: Optional[str] = None,
    profile_type: str = "student",
) -> SessionConfig:
    """
    Авторизует по JWT-токену:
    - Извлекает person_id (msh) и expires_at (exp) из JWT
    - Автоматически находит profile_id через /api/family/web/v1/profile, если он не передан
    """
    token = raw_token.strip()
    if token.startswith("Bearer "):
        token = token[7:]

    payload = decode_jwt(token)
    person_id = payload.get("msh")
    expires_at = payload.get("exp")
    sub_id = payload.get("sub")

    # Если profile_id не передан вручную, запрашиваем профиль МЭШ
    if not profile_id:
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0",
            "x-mes-subsystem": "familyweb",
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get("https://school.mos.ru/api/family/web/v1/profile", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    prof = data.get("profile") or {}
                    children = data.get("children") or []
                    if prof.get("id"):
                        profile_id = str(prof["id"])
                    elif children and children[0].get("id"):
                        profile_id = str(children[0]["id"])
                    if not person_id and children and children[0].get("contingent_guid"):
                        person_id = children[0]["contingent_guid"]
        except Exception as e:
            logger.warning(f"Не удалось автоматически получить profile_id: {e}")

    # Фолбек на идентификатор субъекта из JWT
    if not profile_id and sub_id:
        profile_id = str(sub_id)

    if not profile_id:
        raise ValueError("Не удалось определить Profile ID. Укажите его вручную: --profile-id <ID>")

    cfg = SessionConfig(
        token=token,
        profile_id=str(profile_id),
        profile_type=profile_type,
        person_id=person_id,
        expires_at=expires_at,
    )
    save_session(cfg)
    return cfg


def refresh_token(cfg: SessionConfig) -> Optional[SessionConfig]:
    """
    Фоновое продление токена через найденный эндпоинт МЭШ:
    GET https://school.mos.ru/v2/token/refresh?roleId=1&subsystem=2
    """
    role_id = 2 if cfg.profile_type in ("parent", "agent", "AGENT") else 1
    url = f"{cfg.refresh_endpoint}?roleId={role_id}&subsystem=2"

    headers = {
        "Authorization": f"Bearer {cfg.token}",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0",
        "Accept": "application/json, text/plain, */*",
        "x-mes-subsystem": "familyweb",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                new_token = resp.text.strip().strip('"')
                if new_token.startswith("Bearer "):
                    new_token = new_token[7:]

                if len(new_token) > 50:
                    cfg.token = new_token
                    payload = decode_jwt(new_token)
                    cfg.expires_at = payload.get("exp")
                    save_session(cfg)
                    logger.info("Сессия МЭШ успешно продлена.")
                    return cfg
    except Exception as e:
        logger.warning(f"Не удалось обновить токен сессии: {e}")

    return None