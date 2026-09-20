import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from models import Mark, RankItem
from services.base import BaseMeshService

logger = logging.getLogger("MarksService")


class MarksService(BaseMeshService):
    """Сервис оценок, итоговой успеваемости и рейтинга ученика."""

    def get_marks_for_period(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Mark]:
        self._ensure_ids()
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        student_id = self.config.profile_id
        if not student_id:
            logger.warning("get_marks_for_period: student_id отсутствует")
            return []

        params = {
            "student_id": str(student_id),
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
        }

        try:
            resp = self.get("/api/family/web/v1/marks", params=params)
            if resp.status_code != 200:
                return []

            data = resp.json()
            payload = data.get("payload", []) or []

            marks: List[Mark] = []
            for item in payload:
                subject = item.get("subject_name") or "Предмет"
                value = str(item.get("value", ""))
                date_str = item.get("date")
                if not date_str:
                    continue
                mark_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                control_form = item.get("control_form_name")
                comment = item.get("comment") if item.get("comment_exists") else None
                weight = int(item.get("weight", 1) or 1)

                marks.append(
                    Mark(
                        subject=subject,
                        value=value,
                        date=mark_date,
                        control_form=control_form,
                        comment=comment,
                        weight=weight,
                        is_final=False,
                    )
                )

            marks.sort(key=lambda m: m.date, reverse=True)
            return marks
        except Exception as e:
            logger.error(f"Ошибка в get_marks_for_period: {e}")
            return []

    def get_final_marks(self) -> List[Mark]:
        self._ensure_ids()
        student_id = self.config.profile_id
        if not student_id:
            return []

        try:
            resp = self.get("/api/family/web/v1/subject_marks", params={"student_id": str(student_id)})
            if resp.status_code != 200:
                return []

            data = resp.json()
            payload = data.get("payload", []) or []

            final_marks: List[Mark] = []
            today = date.today()

            for item in payload:
                subject = item.get("subject_name") or "Предмет"

                if item.get("year_mark"):
                    final_marks.append(
                        Mark(
                            subject=subject,
                            value=str(item["year_mark"]),
                            date=today,
                            control_form="Итоговая за год",
                            weight=1,
                            is_final=True,
                        )
                    )

                for period in item.get("periods", []):
                    period_val = period.get("fixed_value") or period.get("value")
                    period_title = period.get("title") or "Период"
                    if period_val and period_val != "0.00":
                        period_date = today
                        if period.get("end_iso"):
                            try:
                                period_date = datetime.strptime(period["end_iso"], "%Y-%m-%d").date()
                            except Exception:
                                pass

                        final_marks.append(
                            Mark(
                                subject=subject,
                                value=str(period_val),
                                date=period_date,
                                control_form=period_title,
                                weight=1,
                                is_final=True,
                            )
                        )

            return final_marks
        except Exception as e:
            logger.error(f"Ошибка в get_final_marks: {e}")
            return []

    def get_rank_by_subjects(self, target_date: Optional[date] = None) -> List[RankItem]:
        self._ensure_ids()
        person_id = self.config.person_id
        if not person_id:
            return []

        if not target_date:
            target_date = date.today()

        params = {
            "personId": person_id,
            "date": target_date.strftime("%Y-%m-%d"),
        }

        try:
            resp = self.get("/api/ej/rating/v1/rank/subjects", params=params)
            if resp.status_code != 200:
                return []

            items = resp.json() or []
            ranks: List[RankItem] = []

            for item in items:
                subject = item.get("subjectName") or "Предмет"
                rank_info = item.get("rank") or {}

                avg_mark = float(rank_info.get("averageMarkFive") or 0.0)
                rank_place = int(rank_info.get("rankPlace") or 0)
                status = rank_info.get("rankStatus") or rank_info.get("trend") or "stable"

                ranks.append(
                    RankItem(
                        subject=subject,
                        average_mark=avg_mark,
                        rank_place=rank_place,
                        rank_status=status,
                    )
                )

            ranks.sort(key=lambda r: r.rank_place)
            return ranks
        except Exception as e:
            logger.error(f"Ошибка в get_rank_by_subjects: {e}")
            return []

    def get_rank_by_class(self, target_date: Optional[date] = None) -> List[RankItem]:
        self._ensure_ids()
        person_id = self.config.person_id
        if not person_id:
            return []

        if not target_date:
            target_date = date.today()

        params = {
            "personId": person_id,
            "date": target_date.strftime("%Y-%m-%d"),
        }

        try:
            resp = self.get("/api/ej/rating/v1/rank/class", params=params)
            if resp.status_code != 200:
                return []

            items = resp.json() or []
            ranks: List[RankItem] = []

            for item in items:
                p_id = item.get("personId")
                rank_info = item.get("rank") or {}

                avg_mark = float(rank_info.get("averageMarkFive") or 0.0)
                rank_place = int(rank_info.get("rankPlace") or 0)
                status = rank_info.get("rankStatus") or rank_info.get("trend") or "stable"

                is_me = p_id == person_id
                subject_label = "Класс (Текущий ученик)" if is_me else "Класс (Одноклассник)"

                ranks.append(
                    RankItem(
                        subject=subject_label,
                        average_mark=avg_mark,
                        rank_place=rank_place,
                        rank_status=status,
                    )
                )

            ranks.sort(key=lambda r: r.rank_place)
            return ranks
        except Exception as e:
            logger.error(f"Ошибка в get_rank_by_class: {e}")
            return []