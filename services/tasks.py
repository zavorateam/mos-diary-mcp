from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from models import Homework, HomeworkMaterial, ProjectTask
from services.base import BaseMeshService


class TasksService(BaseMeshService):
    """Сервис работы с домашними заданиями и проектной деятельностью."""

    def get_homeworks(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Homework]:
        """
        Получает список домашних заданий за указанный интервал дат.
        Эндпоинт: /api/family/web/v1/homeworks
        """
        self._ensure_ids()
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = start_date + timedelta(days=14)

        student_id = self.config.profile_id
        if not student_id:
            return []

        params = {
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
            "student_id": str(student_id),
        }

        try:
            resp = self.get("/api/family/web/v1/homeworks", params=params)
            if resp.status_code != 200:
                return []

            data = resp.json()
            payload = data.get("payload", []) or []

            homeworks: List[Homework] = []
            for item in payload:
                subject = item.get("subject_name") or "Общее"
                description = item.get("homework") or item.get("description") or ""

                date_str = item.get("date")
                if not date_str:
                    continue
                hw_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                is_done = bool(item.get("is_done", False))

                # Парсинг прикрепленных материалов (файлы, тесты ЦДЗ, интерактивные приложения)
                materials: List[HomeworkMaterial] = []
                for mat in item.get("materials", []) or []:
                    m_title = mat.get("title") or mat.get("type_name") or "Материал"
                    m_type = mat.get("type_name") or mat.get("type")

                    # Извлечение URL
                    m_url = None
                    urls_list = mat.get("urls", [])
                    if urls_list and isinstance(urls_list, list):
                        m_url = urls_list[0].get("url")
                    elif mat.get("uuid"):
                        m_url = f"https://uchebnik.mos.ru/material_view/atomic_objects/{mat['uuid']}"

                    materials.append(
                        HomeworkMaterial(
                            title=m_title,
                            type=m_type,
                            url=m_url,
                        )
                    )

                homeworks.append(
                    Homework(
                        subject=subject,
                        description=description.strip(),
                        date=hw_date,
                        is_done=is_done,
                        materials=materials,
                    )
                )

            # Сортировка по сроку сдачи
            homeworks.sort(key=lambda h: h.date)
            return homeworks
        except Exception:
            return []

    def get_projects(self) -> List[ProjectTask]:
        """
        Получает список проектных задач учащегося.
        Эндпоинт: /api/projects/core/project-tasks?personId=...
        """
        self._ensure_ids()
        person_id = self.config.person_id
        if not person_id:
            return []

        try:
            resp = self.get("/api/projects/core/project-tasks", params={"personId": person_id})
            if resp.status_code != 200:
                return []
            data = resp.json()
            items = data.get("content", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

            projects: List[ProjectTask] = []
            for p in items:
                deadline = None
                if p.get("deadline") or p.get("end_date"):
                    try:
                        d_str = p.get("deadline") or p.get("end_date")
                        deadline = datetime.fromisoformat(d_str).date()
                    except Exception:
                        pass

                projects.append(
                    ProjectTask(
                        id=p.get("id") or p.get("task_id"),
                        title=p.get("title") or p.get("name") or "Проектное задание",
                        subject=p.get("subject_name") or p.get("subject"),
                        status=p.get("status") or p.get("state"),
                        deadline=deadline,
                        description=p.get("description") or p.get("text"),
                        role=p.get("role") or p.get("role_name"),
                    )
                )
            return projects
        except Exception:
            return []