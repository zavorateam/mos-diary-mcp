import logging
from typing import Any, Dict, Optional

import httpx

from auth.session_manager import refresh_token
from models import SessionConfig

logger = logging.getLogger("MeshAPI")
logging.getLogger("httpx").setLevel(logging.WARNING)


class BaseMeshService:
    """Базовый сервис: только Bearer-авторизация и Profile-Id заголовки."""

    def __init__(
        self,
        config: SessionConfig,
        base_url: str = "https://school.mos.ru",
        client: Optional[httpx.Client] = None,
    ):
        self.config = config
        self.base_url = base_url.rstrip("/")

        if client is not None:
            self.client = client
        else:
            self._init_client()

    def _init_client(self):
        role_id = "2" if self.config.profile_type in ("parent", "agent", "AGENT") else "1"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "X-mes-subsystem": "familyweb",
            "X-Mes-RoleId": role_id,
        }

        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"

        if self.config.profile_id:
            headers["Profile-Id"] = str(self.config.profile_id)

        if self.config.profile_type:
            headers["Profile-Type"] = str(self.config.profile_type)
            headers["X-Mes-Role"] = str(self.config.profile_type)

        self.client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=20.0,
            follow_redirects=True,
        )

    def _ensure_ids(self):
        """Гарантирует наличие person_id и profile_id."""
        if not self.config.person_id or not self.config.profile_id:
            try:
                resp = self.client.get("/api/family/web/v1/profile")
                if resp.status_code == 200:
                    data = resp.json()
                    prof = data.get("profile", {})
                    children = data.get("children", [])
                    if prof and not self.config.profile_id:
                        self.config.profile_id = str(prof.get("id", ""))
                    if children and not self.config.person_id:
                        self.config.person_id = str(children[0].get("contingent_guid", ""))
            except Exception as e:
                logger.warning(f"Не удалось обновить profile/person ID: {e}")

    def _handle_unauthorized(self) -> bool:
        """При 401 пробует обновить токен и переинициализировать клиент."""
        refreshed = refresh_token(self.config)
        if refreshed:
            self.config = refreshed
            self._init_client()
            return True
        return False

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
        try:
            resp = self.client.get(path, params=params, headers=headers, **kwargs)
            if resp.status_code == 401 and self._handle_unauthorized():
                return self.client.get(path, params=params, headers=headers, **kwargs)
            return resp
        except Exception as e:
            logger.error(f"Ошибка GET {path}: {e}")
            raise

    def post(self, path: str, json: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, **kwargs) -> httpx.Response:
        try:
            resp = self.client.post(path, json=json, headers=headers, **kwargs)
            if resp.status_code == 401 and self._handle_unauthorized():
                return self.client.post(path, json=json, headers=headers, **kwargs)
            return resp
        except Exception as e:
            logger.error(f"Ошибка POST {path}: {e}")
            raise

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()