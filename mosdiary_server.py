#!/usr/bin/env python3
"""
Dual-mode MES Diary Server (MCP 2.x + FastAPI)
"""

import argparse
import json
from datetime import date, datetime, timedelta
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, Query
from pydantic import BaseModel
from mcp.server.mcpserver import MCPServer

from auth.session_manager import load_session, login_with_token
from models import (
    AcademicDebt,
    Attendance,
    BellTime,
    BuildingPass,
    CalendarPeriod,
    ControlWork,
    ExamPrepItem,
    FoodBalance,
    FoodMenuItem,
    Homework,
    LearningSkill,
    Lesson,
    Mark,
    OlympiadItem,
    PortfolioItem,
    ProfileInfo,
    ProjectTask,
    RankItem,
    RewardGift,
    SchoolEvent,
    SectionClub,
    SessionConfig,
    SubjectItem,
)
from services.marks import MarksService
from services.olympiads import OlympiadsService
from services.portfolio import PortfolioService
from services.schedule import ScheduleService
from services.school import SchoolService
from services.study import StudyService
from services.tasks import TasksService

_current_config: Optional[SessionConfig] = None


def get_active_config() -> SessionConfig:
    global _current_config
    if _current_config:
        return _current_config

    cfg = load_session()
    if cfg:
        _current_config = cfg
        return _current_config

    raise RuntimeError(
        "Сессия МЭШ не найдена. Выполните 'mos-diary-cli login' или вызовите tool mes_auth_token."
    )


def _json_out(data) -> str:
    """JSON, устойчивый к наивному экранированию в SDK (escape \\ перед ")."""
    return json.dumps(data, ensure_ascii=False).replace("\\", "\\\\")


# =======================================================
# 1. MCP 2.x Server
# =======================================================
mcp = MCPServer("mosdiary")


@mcp.tool()
def mes_auth_token(token: str, profile_id: Optional[str] = None) -> str:
    """Авторизация в МЭШ по Bearer токену доступа (JWT aupd_token)."""
    global _current_config
    _current_config = login_with_token(raw_token=token, profile_id=profile_id)
    return f"Успешная авторизация в МЭШ. Profile ID: {_current_config.profile_id}"


@mcp.tool()
def mes_get_schedule(target_date: Optional[str] = None) -> str:
    """1. Расписание уроков и звонков на дату (YYYY-MM-DD, по умолчанию сегодня)."""
    cfg = get_active_config()
    dt = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else date.today()
    lessons = ScheduleService(cfg).get_schedule(dt, dt)
    return _json_out([l.model_dump(mode="json") for l in lessons])


@mcp.tool()
def mes_get_homeworks(days: int = 14) -> str:
    """2. Список домашних заданий на указанное количество дней вперед."""
    cfg = get_active_config()
    start = date.today()
    end = start + timedelta(days=days)
    hws = TasksService(cfg).get_homeworks(start, end)
    return _json_out([h.model_dump(mode="json") for h in hws])


@mcp.tool()
def mes_get_projects() -> str:
    """2. Проектная деятельность учащегося."""
    cfg = get_active_config()
    projects = TasksService(cfg).get_projects()
    return _json_out([p.model_dump(mode="json") for p in projects])


@mcp.tool()
def mes_get_marks(days: int = 30) -> str:
    """3. Текущие оценки учащегося за последние N дней."""
    cfg = get_active_config()
    end = date.today()
    start = end - timedelta(days=days)
    marks = MarksService(cfg).get_marks_for_period(start, end)
    return _json_out([m.model_dump(mode="json") for m in marks])


@mcp.tool()
def mes_get_ranks() -> str:
    """3. Рейтинг учащегося по предметам и по классу."""
    cfg = get_active_config()
    ranks = MarksService(cfg).get_rank_by_subjects()
    return _json_out([r.model_dump(mode="json") for r in ranks])


@mcp.tool()
def mes_get_study_overview() -> str:
    """4. График контрольных, подготовка к ЕГЭ/ОГЭ, долги и награды."""
    cfg = get_active_config()
    svc = StudyService(cfg)
    overview = {
        "control_works": [c.model_dump(mode="json") for c in svc.get_control_works()],
        "debts": [d.model_dump(mode="json") for d in svc.get_academic_debts()],
        "skills": [s.model_dump(mode="json") for s in svc.get_learning_skills()],
        "rewards": [r.model_dump(mode="json") for r in svc.get_rewards_and_gifts()],
    }
    return _json_out(overview)


@mcp.tool()
def mes_get_school_overview() -> str:
    """5. Школьный профиль, секции, баланс питания (Москвёнок) и проходы."""
    cfg = get_active_config()
    svc = SchoolService(cfg)
    data = {
        "profile": svc.get_profile_info().model_dump(mode="json"),
        "balance": svc.get_food_balance().model_dump(mode="json"),
        "sections": [s.model_dump(mode="json") for s in svc.get_sections_and_clubs()],
        "passes": [p.model_dump(mode="json") for p in svc.get_building_passes()],
    }
    return _json_out(data)


@mcp.tool()
def mes_get_olympiads() -> str:
    """6. Олимпиады и интеллектуальные конкурсы."""
    cfg = get_active_config()
    olymp = OlympiadsService(cfg).get_olympiads()
    return _json_out([o.model_dump(mode="json") for o in olymp])


@mcp.tool()
def mes_get_portfolio() -> str:
    """7. Портфолио учащегося (грамоты, сертификаты, культура)."""
    cfg = get_active_config()
    port = PortfolioService(cfg).get_portfolio()
    return _json_out([p.model_dump(mode="json") for p in port])


# =======================================================
# 2. FastAPI REST Application (--http)
# =======================================================
api_app = FastAPI(
    title="МЭШ REST API Server",
    description="REST API для экосистемы «Московская электронная школа».",
    version="2.4.0",
)


class TokenPayload(BaseModel):
    token: str
    profile_id: Optional[str] = None


@api_app.get("/api/health", tags=["Система"])
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@api_app.post("/api/auth/token", tags=["Авторизация"])
def import_token(payload: TokenPayload):
    res = mes_auth_token(payload.token, payload.profile_id)
    return {"status": "success", "message": res}


@api_app.get("/api/schedule", response_model=List[Lesson], tags=["1. Расписание"])
def api_schedule(
    start_date: Optional[date] = Query(default_factory=date.today),
    end_date: Optional[date] = None,
):
    return ScheduleService(get_active_config()).get_schedule(start_date, end_date)


@api_app.get("/api/schedule/bells", response_model=List[BellTime], tags=["1. Расписание"])
def api_bells(target_date: Optional[date] = Query(default_factory=date.today)):
    return ScheduleService(get_active_config()).get_bell_schedule(target_date)


@api_app.get("/api/schedule/periods", response_model=List[CalendarPeriod], tags=["1. Расписание"])
def api_periods():
    return ScheduleService(get_active_config()).get_academic_periods()


@api_app.get("/api/tasks/homeworks", response_model=List[Homework], tags=["2. Задания"])
def api_homeworks(days: int = 14, start_date: Optional[date] = Query(default_factory=date.today)):
    actual_start = start_date or date.today()
    end = actual_start + timedelta(days=days)
    return TasksService(get_active_config()).get_homeworks(actual_start, end)


@api_app.get("/api/tasks/projects", response_model=List[ProjectTask], tags=["2. Задания"])
def api_projects():
    return TasksService(get_active_config()).get_projects()


@api_app.get("/api/marks", response_model=List[Mark], tags=["3. Оценки"])
def api_marks(days: int = 30):
    end = date.today()
    start = end - timedelta(days=days)
    return MarksService(get_active_config()).get_marks_for_period(start, end)


@api_app.get("/api/marks/final", response_model=List[Mark], tags=["3. Оценки"])
def api_final_marks():
    return MarksService(get_active_config()).get_final_marks()


@api_app.get("/api/marks/ranks/subjects", response_model=List[RankItem], tags=["3. Оценки"])
def api_ranks_subjects():
    return MarksService(get_active_config()).get_rank_by_subjects()


@api_app.get("/api/marks/ranks/class", response_model=List[RankItem], tags=["3. Оценки"])
def api_ranks_class():
    return MarksService(get_active_config()).get_rank_by_class()


@api_app.get("/api/study/subjects", response_model=List[SubjectItem], tags=["4. Учёба"])
def api_subjects():
    return StudyService(get_active_config()).get_subjects()


@api_app.get("/api/study/control-works", response_model=List[ControlWork], tags=["4. Учёба"])
def api_control_works():
    return StudyService(get_active_config()).get_control_works()


@api_app.get("/api/study/exam-prep", response_model=List[ExamPrepItem], tags=["4. Учёба"])
def api_exam_prep():
    return StudyService(get_active_config()).get_exam_prep()


@api_app.get("/api/study/debts", response_model=List[AcademicDebt], tags=["4. Учёба"])
def api_debts():
    return StudyService(get_active_config()).get_academic_debts()


@api_app.get("/api/study/skills", response_model=List[LearningSkill], tags=["4. Учёба"])
def api_skills():
    return StudyService(get_active_config()).get_learning_skills()


@api_app.get("/api/study/rewards", response_model=List[RewardGift], tags=["4. Учёба"])
def api_rewards():
    return StudyService(get_active_config()).get_rewards_and_gifts()


@api_app.get("/api/school/profile", response_model=ProfileInfo, tags=["5. Школа"])
def api_profile():
    return SchoolService(get_active_config()).get_profile_info()


@api_app.get("/api/school/sections", response_model=List[SectionClub], tags=["5. Школа"])
def api_sections():
    return SchoolService(get_active_config()).get_sections_and_clubs()


@api_app.get("/api/school/passes", response_model=List[BuildingPass], tags=["5. Школа"])
def api_passes(days: int = 7):
    end = date.today()
    start = end - timedelta(days=min(days - 1, 6))
    return SchoolService(get_active_config()).get_building_passes(start, end)


@api_app.get("/api/school/food/balance", response_model=FoodBalance, tags=["5. Школа"])
def api_food_balance():
    return SchoolService(get_active_config()).get_food_balance()


@api_app.get("/api/school/food/menu", response_model=List[FoodMenuItem], tags=["5. Школа"])
def api_food_menu(target_date: Optional[date] = Query(default_factory=date.today)):
    return SchoolService(get_active_config()).get_food_menu(target_date)


@api_app.get("/api/school/attendance", response_model=List[Attendance], tags=["5. Школа"])
def api_attendance(days: int = 30):
    end = date.today()
    start = end - timedelta(days=days)
    return SchoolService(get_active_config()).get_attendance(start, end)


@api_app.get("/api/school/events", response_model=List[SchoolEvent], tags=["5. Школа"])
def api_school_events():
    return SchoolService(get_active_config()).get_school_events()


@api_app.get("/api/olympiads", response_model=List[OlympiadItem], tags=["6. Олимпиады"])
def api_olympiads():
    return OlympiadsService(get_active_config()).get_olympiads()


@api_app.get("/api/portfolio", response_model=List[PortfolioItem], tags=["7. Портфолио"])
def api_portfolio():
    return PortfolioService(get_active_config()).get_portfolio()


# =======================================================
# Точка входа
# =======================================================
def main():
    parser = argparse.ArgumentParser(description="МЭШ Diary Server")
    parser.add_argument("--http", action="store_true", help="Запуск REST API сервера")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.http:
        print(f"🚀 МЭШ REST API запущен на http://{args.host}:{args.port}")
        print(f"📖 Swagger UI документация: http://{args.host}:{args.port}/docs")
        uvicorn.run(api_app, host=args.host, port=args.port)
    else:
        # MCP 2.x stdio запуск
        mcp.run()


if __name__ == "__main__":
    main()
