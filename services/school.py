import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from models import (
    Attendance,
    BuildingPass,
    FoodBalance,
    FoodMenuItem,
    ProfileInfo,
    SchoolEvent,
    SectionClub,
)
from services.base import BaseMeshService

logger = logging.getLogger("SchoolService")


class SchoolService(BaseMeshService):
    """Сервис школьной информации, кружков, проходов (Москвёнок), питания и посещаемости."""

    def get_profile_info(self) -> ProfileInfo:
        self._ensure_ids()
        full_name = "Ученик"
        class_name = "Не указан"
        school_name = "ГБОУ Школа"
        school_address = "Не указан"
        school_principal = "Не указан"
        school_phone = "Не указан"
        email = "Не указан"
        phone = "Не указан"
        snils = "Не указан"
        school_id = None
        class_unit_id = None

        try:
            prof_resp = self.get("/api/family/web/v1/profile")
            if prof_resp.status_code == 200:
                p_data = prof_resp.json()
                prof = p_data.get("profile") or {}
                children = p_data.get("children", [])

                last = prof.get("last_name") or ""
                first = prof.get("first_name") or ""
                middle = prof.get("middle_name") or ""
                if last or first:
                    full_name = f"{last} {first} {middle}".strip()

                email = prof.get("email") or email
                phone = prof.get("phone") or phone
                snils = prof.get("snils") or snils

                if children:
                    ch = children[0]
                    class_name = ch.get("class_name") or class_name
                    class_unit_id = ch.get("class_unit_id")
                    sch = ch.get("school") or {}
                    school_id = sch.get("id")
                    school_name = sch.get("name") or sch.get("short_name") or school_name
                    school_principal = sch.get("principal") or school_principal
                    school_phone = sch.get("phone") or school_phone

            if school_id and self.config.profile_id:
                params = {"school_id": school_id, "student_id": self.config.profile_id}
                if class_unit_id:
                    params["class_unit_id"] = class_unit_id
                s_resp = self.get("/api/family/web/v1/school_info", params=params)
                if s_resp.status_code == 200:
                    s_data = s_resp.json()
                    addr = s_data.get("address", {})
                    if addr and isinstance(addr, dict):
                        school_address = addr.get("address") or school_address
                    if s_data.get("principal"):
                        school_principal = s_data.get("principal")
                    if s_data.get("phone"):
                        school_phone = s_data.get("phone")
        except Exception as e:
            logger.error(f"Ошибка в get_profile_info: {e}")

        return ProfileInfo(
            full_name=full_name,
            class_name=class_name,
            school_name=school_name,
            school_address=school_address,
            school_principal=school_principal,
            school_phone=school_phone,
            email=email,
            phone=phone,
            snils=snils,
        )

    def get_sections_and_clubs(self) -> List[SectionClub]:
        self._ensure_ids()
        clubs: List[SectionClub] = []
        person_id = self.config.person_id
        if not person_id:
            return clubs

        try:
            payload = {
                "personIds": [person_id],
                "searchResultLimit": {"minValue": 1, "maxValue": 100},
                "educationTypeIds": [1, 256],
                "requestStatusIds": ["4", "16"],
            }
            resp = self.post("/api/circles/family/v1/requests/search", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("searchResItems", []) or []:
                    srv = item.get("service") or {}
                    s_class = item.get("serviceClass") or {}
                    club_id = srv.get("serviceId")
                    club_name = srv.get("serviceName") or s_class.get("name") or "Кружок"
                    teacher = s_class.get("teacherName")

                    sched_desc_parts = []
                    for sch in s_class.get("schedule", []) or []:
                        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
                        for d_key, d_label in zip(days, day_names):
                            slots = sch.get(d_key)
                            if slots and isinstance(slots, list):
                                for sl in slots:
                                    sched_desc_parts.append(f"{d_label} {sl.get('f', '')[:5]}-{sl.get('t', '')[:5]}")

                    sched_str = "; ".join(sched_desc_parts) if sched_desc_parts else srv.get("serviceAddress")

                    clubs.append(
                        SectionClub(
                            id=club_id,
                            name=club_name,
                            schedule_description=sched_str,
                            teacher_name=teacher,
                        )
                    )
        except Exception as e:
            logger.error(f"Ошибка в get_sections_and_clubs: {e}")
        return clubs

    def get_building_passes(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[BuildingPass]:
        self._ensure_ids()
        passes: List[BuildingPass] = []
        person_id = self.config.person_id
        if not person_id:
            return passes

        if not end_date:
            end_date = date.today()

        # Лимит API МЭШ: строго не более 7 дней включительно (разница <= 6 дней)
        if not start_date or (end_date - start_date).days > 6:
            start_date = end_date - timedelta(days=6)

        params = {
            "personId": person_id,
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
        }

        try:
            resp = self.get("/api/pass/entrances/v1/visit_durations", params=params)
            if resp.status_code == 200:
                data = resp.json()
                for day_item in data.get("payload", []) or []:
                    d_str = day_item.get("date")
                    if not d_str:
                        continue
                    pass_date = datetime.strptime(d_str[:10], "%Y-%m-%d").date()

                    for v in day_item.get("visits", []) or []:
                        addr = v.get("organizationAddress") or v.get("organizationShortName")
                        in_time = v.get("in")
                        out_time = v.get("out")

                        if in_time and in_time != "-":
                            passes.append(BuildingPass(date=pass_date, time=in_time, entry_type="Вход", address=addr))
                        if out_time and out_time != "-":
                            passes.append(BuildingPass(date=pass_date, time=out_time, entry_type="Выход", address=addr))
            passes.sort(key=lambda p: (p.date, p.time), reverse=True)
        except Exception as e:
            logger.error(f"Ошибка в get_building_passes: {e}")
        return passes

    def get_food_balance(self) -> FoodBalance:
        self._ensure_ids()
        person_id = self.config.person_id
        if not person_id:
            return FoodBalance(balance=0.0, card_number=None)

        try:
            client_param = json.dumps([{"personId": person_id}], separators=(",", ":"))
            resp = self.get("/api/food/meals/v3/clients/balance", params={"clientIds": client_param})
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    item = data[0]
                    raw_bal = float(item.get("balance", 0) or 0)
                    contract_id = str(item.get("contractId", "")) if item.get("contractId") else None
                    return FoodBalance(balance=raw_bal / 100.0, card_number=contract_id)
        except Exception as e:
            logger.error(f"Ошибка в get_food_balance: {e}")

        return FoodBalance(balance=0.0, card_number=None)

    def get_food_menu(self, target_date: Optional[date] = None) -> List[FoodMenuItem]:
        self._ensure_ids()
        menu_items: List[FoodMenuItem] = []
        person_id = self.config.person_id
        if not person_id:
            return menu_items

        if not target_date:
            target_date = date.today()

        try:
            client_param = json.dumps({"personId": person_id}, separators=(",", ":"))
            params = {
                "clientId": client_param,
                "from": target_date.strftime("%Y-%m-%d"),
                "to": target_date.strftime("%Y-%m-%d"),
                "limit": 50,
            }
            resp = self.get("/api/food/meals/v3/orders", params=params)
            if resp.status_code == 200:
                orders = resp.json().get("orders", []) or []
                for o in orders:
                    meal_type = o.get("meal_type") or o.get("name") or "Комплекс"
                    dish = o.get("dish_name") or o.get("item_name") or "Питание"
                    price = float(o.get("price", 0) or 0) / 100.0 if o.get("price") else None

                    menu_items.append(
                        FoodMenuItem(
                            date=target_date,
                            meal_type=meal_type,
                            dish_name=dish,
                            price=price,
                        )
                    )
        except Exception as e:
            logger.error(f"Ошибка в get_food_menu: {e}")
        return menu_items

    def get_attendance(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Attendance]:
        self._ensure_ids()
        attendance_list: List[Attendance] = []
        student_id = self.config.profile_id
        if not student_id:
            return attendance_list

        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        params = {
            "student_id": student_id,
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
        }

        try:
            resp = self.get("/api/family/web/v1/attendance", params=params)
            if resp.status_code == 200:
                data = resp.json().get("attendance", []) or []
                for att in data:
                    d_str = att.get("date")
                    if not d_str:
                        continue
                    a_date = datetime.strptime(d_str[:10], "%Y-%m-%d").date()
                    subj = att.get("subject_name") or "Занятие"
                    presence = att.get("presence") or ("Присутствовал" if not att.get("absence_reason") else "Отсутствовал")

                    attendance_list.append(Attendance(date=a_date, subject=subj, presence=presence))
        except Exception as e:
            logger.error(f"Ошибка в get_attendance: {e}")
        return attendance_list

    def get_school_events(self) -> List[SchoolEvent]:
        self._ensure_ids()
        events: List[SchoolEvent] = []
        try:
            params = {
                "school_id": 606,
                "begin_date": "01.09.2026",
                "end_date": "31.08.2027",
            }
            resp = self.get("/api/ej/organizer/family/v1/events", params=params)
            if resp.status_code == 200:
                items = resp.json() or []
                for ev in items:
                    title = ev.get("title") or "Событие"
                    desc = ev.get("description")
                    place = ev.get("address") or ev.get("building_name")

                    d_str = ev.get("date")
                    if not d_str:
                        continue
                    s_date = datetime.strptime(d_str[:10], "%Y-%m-%d").date()
                    e_date = datetime.strptime(ev["date_end"][:10], "%Y-%m-%d").date() if ev.get("date_end") else None

                    events.append(
                        SchoolEvent(
                            title=title,
                            description=desc,
                            start_date=s_date,
                            end_date=e_date,
                            place=place,
                        )
                    )
        except Exception as e:
            logger.error(f"Ошибка в get_school_events: {e}")
        return events