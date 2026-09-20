import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from models import OlympiadItem
from services.base import BaseMeshService

logger = logging.getLogger("OlympiadsService")

STAGE_NAMES = {
    "School": "Школьный",
    "Municipal": "Муниципальный",
    "District": "Районный",
    "Regional": "Региональный",
    "Final": "Заключительный",
    "All-Russian": "Всероссийский",
    "Invitational": "Пригласительный",
    "Main qualifier": "Основной отборочный",
    "Additional qualifying": "Дополнительный отборочный",
    "International": "Международный",
}

STATUS_NAMES = {
    "REGISTRATION": "Регистрация открыта",
    "REGISTERED": "Зарегистрирован",
    "PARTICIPATION": "Участник",
    "WINNER": "Победитель 🏆",
    "PRIZE_WINNER": "Призёр 🥈",
    "PUBLISHED_FINAL_RESULTS": "Итоги опубликованы",
    "IN_PROGRESS": "Идёт тур",
    "CHECKING": "Проверка работ",
    "APPEAL": "Апелляция",
    "STOPPED": "Завершено",
    "COMPLETED": "Завершено",
}


class OlympiadsService(BaseMeshService):
    """Сервис олимпиад, конкурсов и результатов тестирований."""

    def get_olympiads(self) -> List[OlympiadItem]:
        self._ensure_ids()
        olympiads: List[OlympiadItem] = []

        try:
            current_year = date.today().year
            payload = {
                "page": {"number": 0, "size": 50},
                "searchString": "",
                "sort": {"fieldName": "startAt", "order": "DESC"},
                "subjectIds": [],
                "stageCodes": [],
                "parallelIds": [],
                "years": [current_year, current_year - 1],
                "includeCurrent": True,
                "includeFuture": True,
                "includeCompleted": True,
                "showParticipantContests": True,
            }

            headers = {
                "x-mes-subsystem": "constuweb",
                "Content-Type": "application/json",
            }

            resp = self.post(
                "/api/contests/exec/v1/contests/overview",
                json=payload,
                headers=headers,
            )

            if resp.status_code == 200:
                data = resp.json()
                page_data = data.get("page") or {}
                items = page_data.get("content", []) or []

                for item in items:
                    c_id = str(item.get("contestId") or "")
                    name = item.get("contestName") or "Олимпиада"

                    raw_stage = item.get("stageCode") or ""
                    stage_name = STAGE_NAMES.get(raw_stage, raw_stage or "Основной")

                    raw_status = item.get("statusCode") or ""
                    status_name = STATUS_NAMES.get(raw_status, raw_status or "Участник")

                    o_date = None
                    if item.get("startAt"):
                        try:
                            o_date = datetime.strptime(item["startAt"][:10], "%Y-%m-%d").date()
                        except Exception:
                            pass

                    score = float(item["score"]) if item.get("score") is not None else None
                    max_score = float(item["maxScore"]) if item.get("maxScore") is not None else None
                    diploma_url = item.get("diplomaUrl") or item.get("awardUrl")

                    olympiads.append(
                        OlympiadItem(
                            id=c_id,
                            name=name,
                            stage=stage_name,
                            subject=item.get("subjectName"),
                            status=status_name,
                            score=score,
                            max_score=max_score,
                            date=o_date,
                            diploma_url=diploma_url,
                        )
                    )

            olympiads.sort(key=lambda o: o.date or date.min, reverse=True)
        except Exception as e:
            logger.error(f"Ошибка в get_olympiads: {e}")

        return olympiads