# services/study.py
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from models import (
    AcademicDebt,
    ControlWork,
    ExamPrepItem,
    LearningSkill,
    RewardGift,
    SubjectItem,
)
from services.base import BaseMeshService


class StudyService(BaseMeshService):
    """Сервис учебного плана, предметов, экзаменов, задолженностей, навыков и наград."""

    def get_subjects(self) -> List[SubjectItem]:
        """
        Получает перечень предметов с преподавателями и названиями учебных групп.
        """
        self._ensure_ids()
        subjects: List[SubjectItem] = []

        # 1. Сначала пробуем получить данные из профиля ученика
        group_map: Dict[int, str] = {}
        parallel_curriculum_id = None
        try:
            prof_resp = self.get("/api/family/web/v1/profile")
            if prof_resp.status_code == 200:
                p_data = prof_resp.json()
                children = p_data.get("children", [])
                if children:
                    child = children[0]
                    parallel_curriculum_id = child.get("parallel_curriculum_id")
                    for g in child.get("groups", []) or []:
                        s_id = g.get("subject_id")
                        if s_id:
                            group_map[s_id] = g.get("name", "")
        except Exception:
            pass

        # 2. Получаем развернутый учебный план с назначенными учителями
        if parallel_curriculum_id and self.config.profile_id:
            try:
                plan_resp = self.get(
                    f"/api/family/web/v1/programs/parallel_curriculum/{parallel_curriculum_id}",
                    params={"student_id": self.config.profile_id},
                )
                if plan_resp.status_code == 200:
                    plan_data = plan_resp.json()
                    for section in plan_data.get("sections", []) or []:
                        for sub in section.get("subjects", []) or []:
                            sub_id = sub.get("subject_id")
                            sub_name = sub.get("subject_name") or "Предмет"
                            teachers_list = sub.get("teachers", []) or []
                            teacher_name = ", ".join(filter(None, teachers_list)) or None
                            group_name = group_map.get(sub_id)

                            subjects.append(
                                SubjectItem(
                                    id=sub_id,
                                    name=sub_name,
                                    group_name=group_name,
                                    teacher_name=teacher_name,
                                )
                            )
                    if subjects:
                        return subjects
            except Exception:
                pass

        # Fallback: если учебный план недоступен, отдаем предметы из групп профиля
        for s_id, g_name in group_map.items():
            subjects.append(SubjectItem(id=s_id, name=g_name, group_name=g_name, teacher_name=None))

        return subjects

    def get_control_works(self) -> List[ControlWork]:
        """
        Получает график контрольных и проверочных работ.
        """
        self._ensure_ids()
        control_works: List[ControlWork] = []
        try:
            # Запрашиваем события календаря с расширенными типами работ
            today = date.today()
            params = {
                "person_ids": self.config.person_id,
                "begin_date": today.strftime("%Y-%m-%d"),
                "end_date": (date(today.year, 12, 31) if today.month <= 12 else today).strftime("%Y-%m-%d"),
                "expand": "marks,homework",
                "source_types": "PLAN,EC,EVENTS",
            }
            resp = self.get("/api/eventcalendar/v1/api/events", params=params)
            if resp.status_code == 200:
                events = resp.json().get("response", []) or []
                for ev in events:
                    ctrl_form = ev.get("control_form_name") or ev.get("lesson_type")
                    if ctrl_form in ["TEST", "CONTROL", "Контрольная работа", "Проверочная работа", "Диагностика"]:
                        s_name = ev.get("subject_name") or "Предмет"
                        topic = ev.get("topic") or ev.get("lesson_name") or "Контрольная работа"
                        ev_date = datetime.fromisoformat(ev["start_at"]).date()
                        control_works.append(
                            ControlWork(
                                subject=s_name,
                                topic=topic,
                                date=ev_date,
                                control_form=ctrl_form,
                            )
                        )
        except Exception:
            pass
        return control_works

    def get_exam_prep(self) -> List[ExamPrepItem]:
        """
        Получает предметы подготовки к экзаменам (ЕГЭ / ОГЭ) и спецификации заданий.
        Эндпоинт: /diary/toUchebnikProd/egeoge/examList.json
        """
        self._ensure_ids()
        exam_items: List[ExamPrepItem] = []
        try:
            resp = self.get("/diary/toUchebnikProd/egeoge/examList.json")
            if resp.status_code == 200:
                data = resp.json()
                level = data.get("levelName", "Экзамен")
                for ex in data.get("exam", []) or []:
                    exam_name = ex.get("examName", "Предмет")
                    tasks_count = len(ex.get("tasks", []))
                    req = " (Обязательный)" if ex.get("examRequired") else ""

                    exam_items.append(
                        ExamPrepItem(
                            subject=exam_name,
                            title=f"{level}{req}: {tasks_count} типовых заданий",
                            type=level,
                            progress=0.0,
                            url="https://school.mos.ru/diary/study/exams",
                        )
                    )
        except Exception:
            pass
        return exam_items

    def get_academic_debts(self) -> List[AcademicDebt]:
        """
        Получает перечень академических задолженностей ученика.
        Эндпоинт: /api/ej/core/family/v1/academic_debts
        """
        self._ensure_ids()
        try:
            resp = self.get(
                "/api/ej/core/family/v1/academic_debts",
                params={"class_unit_ids": "2104771", "academic_year_id": 14},
            )
            if resp.status_code != 200:
                return []

            items = resp.json() or []
            debts: List[AcademicDebt] = []
            for d in items:
                debts.append(
                    AcademicDebt(
                        subject=d.get("subject_name", "Предмет"),
                        debt_type=d.get("debt_type", "Задолженность"),
                        control_form=d.get("control_form_name"),
                        due_date=datetime.strptime(d["due_date"], "%Y-%m-%d").date() if d.get("due_date") else None,
                    )
                )
            return debts
        except Exception:
            return []

    def get_learning_skills(self) -> List[LearningSkill]:
        """
        Получает список учебных и метапредметных умений (Soft Skills).
        Эндпоинт: /api/soft_skills/v1/periods
        """
        self._ensure_ids()
        skills: List[LearningSkill] = []
        if not self.config.person_id:
            return skills

        try:
            resp = self.get(
                "/api/soft_skills/v1/periods",
                params={
                    "student_person_id": self.config.person_id,
                    "soft_skills_completed": "false",
                },
                headers={"aid": "14"},
            )
            if resp.status_code == 200:
                data = resp.json()
                for p in data.get("periods", []) or []:
                    p_name = p.get("period_name", "Период")
                    is_cur = " (Текущий период)" if p.get("is_current") else ""
                    skills.append(
                        LearningSkill(
                            subject="Метапредметные навыки (Soft Skills)",
                            skill_name=f"{p_name}{is_cur}",
                            level="Активно" if p.get("is_current") else "Запланировано",
                            score=100.0 if p.get("exist_student_answer") else 0.0,
                        )
                    )
        except Exception:
            pass
        return skills

    def get_rewards_and_gifts(self) -> List[RewardGift]:
        """
        Получает список доступных наград и мерча геймификации МЭШ.
        Эндпоинт: /api/gamification/v1/rewards/search
        """
        self._ensure_ids()
        rewards: List[RewardGift] = []
        try:
            payload = {
                "sorting": {"orderBy": "publishedAt", "direction": "DESC"},
                "filters": {
                    "rewardTypes": ["GIFT", "PARTNER_GIFT"],
                    "statuses": ["ACTIVE"],
                    "isEmptyHidden": True,
                },
                "pagination": {"pageNumber": 1, "pageSize": 20},
            }
            resp = self.post("/api/gamification/v1/rewards/search", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                for r in data.get("content", []) or []:
                    r_id = str(r.get("id"))
                    name = r.get("name", "Награда")
                    pts = r.get("points", 0)
                    img_url = r.get("imageUrl") or r.get("animationUrl")

                    rewards.append(
                        RewardGift(
                            id=r_id,
                            title=name,
                            description=f"Стоимость: {pts} баллов МЭШ. Остаток: {r.get('balance', 0)} шт.",
                            received_date=None,
                            badge_url=img_url,
                        )
                    )
        except Exception:
            pass
        return rewards