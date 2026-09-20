import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from models import PortfolioItem
from services.base import BaseMeshService

logger = logging.getLogger("PortfolioService")


class PortfolioService(BaseMeshService):
    """Сервис портфолио ученика: творчество, культура, спорт, наука и гражданская активность."""

    def get_portfolio(self) -> List[PortfolioItem]:
        self._ensure_ids()
        portfolio_items: List[PortfolioItem] = []
        person_id = self.config.person_id
        if not person_id:
            return portfolio_items

        headers = {
            "X-Mes-Subsystem": "studentportfolioweb",
            "Accept": "application/json, text/plain, */*",
        }

        # 1. Творчество и Гражданская активность
        try:
            resp = self.get(f"/portfolio/app/persons/{person_id}/affilations/list", params={"size": 9999}, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get("data", []) or []
                for aff in data:
                    cat_name = (aff.get("category") or {}).get("value") or "Активность"
                    name = aff.get("name") or "Участие в объединении"
                    subcat = (aff.get("subcategory") or {}).get("value")
                    role = aff.get("status") or "Участник"
                    desc = f"{subcat} | Роль: {role}" if subcat else f"Роль: {role}"

                    p_date = None
                    if aff.get("startDate"):
                        try:
                            p_date = datetime.strptime(aff["startDate"][:10], "%Y-%m-%d").date()
                        except Exception:
                            pass

                    portfolio_items.append(
                        PortfolioItem(
                            category=cat_name,
                            title=name,
                            description=desc,
                            date=p_date,
                            document_url=None,
                        )
                    )
        except Exception as e:
            logger.error(f"Ошибка в portfolio affilations: {e}")

        # 2. Культура (музеи, театры, усадьбы)
        try:
            resp = self.get(f"/portfolio/app/persons/{person_id}/cultural/list/", params={"size": 9999}, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get("data", []) or []
                for cult in data:
                    inst_name = cult.get("culturalInstitutionName") or "Культурное учреждение"
                    inst_type = cult.get("culturalInstitutionType") or "Мероприятие"

                    p_date = None
                    if cult.get("visitTime"):
                        try:
                            p_date = datetime.strptime(cult["visitTime"][:10], "%Y-%m-%d").date()
                        except Exception:
                            pass

                    portfolio_items.append(
                        PortfolioItem(
                            category="Культура",
                            title=inst_name,
                            description=f"Тип: {inst_type} (Посещение подтверждено)",
                            date=p_date,
                            document_url=None,
                        )
                    )
        except Exception as e:
            logger.error(f"Ошибка в portfolio cultural: {e}")

        # 3. Наука и Экзамены (ОГЭ / ГИА / МЦКО)
        try:
            resp = self.get(f"/portfolio/app/persons/{person_id}/govexams/list/", headers=headers)
            if resp.status_code == 200:
                data = resp.json().get("data", []) or []
                for ex in data:
                    s_name = ex.get("name") or "Предмет"
                    f_gia = ex.get("formaGia") or "Экзамен"
                    mark = ex.get("normalizedMarkValue")
                    score = ex.get("primaryMarkValue")
                    max_score = ex.get("primaryMarkBasis")

                    p_date = None
                    if ex.get("date"):
                        try:
                            p_date = datetime.strptime(ex["date"][:10], "%Y-%m-%d").date()
                        except Exception:
                            pass

                    desc = f"{f_gia} — Оценка: {mark}"
                    if score is not None and max_score is not None:
                        desc += f" (Баллы: {score}/{max_score})"

                    portfolio_items.append(
                        PortfolioItem(
                            category="Наука",
                            title=f"Государственная аттестация: {s_name}",
                            description=desc,
                            date=p_date,
                            document_url=None,
                        )
                    )
        except Exception as e:
            logger.error(f"Ошибка в portfolio govexams: {e}")

        portfolio_items.sort(key=lambda x: x.date or date.min, reverse=True)
        return portfolio_items