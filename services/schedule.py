import logging
from datetime import date, datetime
from typing import List, Optional

from models import BellTime, CalendarPeriod, Lesson
from services.base import BaseMeshService

logger = logging.getLogger("ScheduleService")


class ScheduleService(BaseMeshService):
    """Сервис расписания уроков, звонков и календарных периодов."""

    def get_schedule(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Lesson]:
        self._ensure_ids()
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = start_date

        person_id = self.config.person_id
        if not person_id:
            logger.warning("get_schedule: person_id отсутствует")
            return []

        params = {
            "person_ids": person_id,
            "begin_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "expand": "marks,homework,absence_reason_id,health_status,nonattendance_reason_id",
            "source_types": "PLAN,AE,EC,EVENTS,AFISHA,ORGANIZER,OLYMPIAD,PROF",
        }

        try:
            resp = self.get("/api/eventcalendar/v1/api/events", params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
            events = data.get("response", []) or []

            lessons: List[Lesson] = []
            for item in events:
                if item.get("cancelled", False):
                    continue

                start_iso = item.get("start_at")
                finish_iso = item.get("finish_at")
                if not start_iso or not finish_iso:
                    continue

                try:
                    start_dt = datetime.fromisoformat(start_iso)
                    finish_dt = datetime.fromisoformat(finish_iso)
                    les_date = start_dt.date()
                    begin_time = start_dt.strftime("%H:%M")
                    end_time = finish_dt.strftime("%H:%M")
                except Exception:
                    les_date = start_date
                    begin_time = "00:00"
                    end_time = "00:00"

                subject = item.get("subject_name") or item.get("title") or "Занятие"
                room = item.get("room_number") or item.get("room_name")

                hw = item.get("homework") or {}
                hw_descs = hw.get("descriptions", [])
                topic = item.get("topic") or (hw_descs[0] if hw_descs else None)

                lessons.append(
                    Lesson(
                        date=les_date,
                        subject=subject,
                        begin_time=begin_time,
                        end_time=end_time,
                        lesson_name=topic,
                        group_name=None,
                        room_number=str(room) if room else None,
                        teacher_name=None,
                        is_virtual=bool(item.get("link_to_join")),
                        lesson_id=item.get("id"),
                    )
                )

            # Сортировка: сначала по дате, затем по времени начала урока
            lessons.sort(key=lambda l: (l.date or date.min, l.begin_time))
            return lessons
        except Exception as e:
            logger.error(f"Ошибка в get_schedule: {e}")
            return []

    def get_bell_schedule(self, target_date: Optional[date] = None) -> List[BellTime]:
        lessons = self.get_schedule(target_date, target_date)
        unique_times = []
        for l in lessons:
            pair = (l.begin_time, l.end_time)
            if pair not in unique_times:
                unique_times.append(pair)

        unique_times.sort(key=lambda p: p[0])

        bells = []
        for idx, (b_time, e_time) in enumerate(unique_times, start=1):
            bells.append(BellTime(lesson_number=idx, begin_time=b_time, end_time=e_time))
        return bells

    def get_academic_periods(self) -> List[CalendarPeriod]:
        self._ensure_ids()
        try:
            years_resp = self.get("/api/ej/core/family/v1/academic_years")
            if years_resp.status_code != 200:
                return []
            years = years_resp.json()
            current_year = next((y for y in years if y.get("current_year")), years[-1] if years else None)
            if not current_year:
                return []

            year_id = current_year.get("id")

            params = {
                "academic_year_id": year_id,
                "student_profile_id": self.config.profile_id,
            }
            periods_resp = self.get("/api/ej/core/family/v1/periods_schedules", params=params)
            if periods_resp.status_code != 200:
                return []

            data = periods_resp.json()
            result: List[CalendarPeriod] = []
            today = date.today()

            for sched in data:
                for p in sched.get("periods", []):
                    b_str = p.get("begin_date")
                    e_str = p.get("end_date")
                    if not b_str or not e_str:
                        continue
                    b_date = datetime.strptime(b_str[:10], "%Y-%m-%d").date()
                    e_date = datetime.strptime(e_str[:10], "%Y-%m-%d").date()
                    name = p.get("name", "Период")
                    if p.get("is_vacation"):
                        name = f"{name} (Каникулы)"

                    is_current = b_date <= today <= e_date
                    result.append(
                        CalendarPeriod(
                            name=name,
                            start_date=b_date,
                            end_date=e_date,
                            is_current=is_current,
                        )
                    )

            result.sort(key=lambda cp: cp.start_date)
            return result
        except Exception as e:
            logger.error(f"Ошибка в get_academic_periods: {e}")
            return []