from datetime import date as dt_date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ========== Конфигурация сессии ==========
class SessionConfig(BaseModel):
    token: str
    profile_id: str
    profile_type: str = "student"  # "student" (roleId=1) или "parent" (roleId=2)
    person_id: Optional[str] = None
    expires_at: Optional[int] = None
    refresh_endpoint: str = "https://school.mos.ru/v2/token/refresh"


# ========== 1. Расписание ==========
class Lesson(BaseModel):
    date: Optional[dt_date] = None
    subject: str
    begin_time: str
    end_time: str
    lesson_name: Optional[str] = None
    group_name: Optional[str] = None
    room_number: Optional[str] = None
    teacher_name: Optional[str] = None
    is_virtual: bool = False
    lesson_id: Optional[int] = None


class BellTime(BaseModel):
    lesson_number: int
    begin_time: str
    end_time: str


class CalendarPeriod(BaseModel):
    name: str
    start_date: dt_date
    end_date: dt_date
    is_current: bool = False


# ========== 2. Задания ==========
class HomeworkMaterial(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None


class Homework(BaseModel):
    subject: str
    description: str
    date: dt_date
    is_done: bool = False
    materials: List[HomeworkMaterial] = Field(default_factory=list)


class ProjectTask(BaseModel):
    id: Optional[int] = None
    title: str
    subject: Optional[str] = None
    status: Optional[str] = None
    deadline: Optional[dt_date] = None
    description: Optional[str] = None
    role: Optional[str] = None


# ========== 3. Оценки ==========
class Mark(BaseModel):
    subject: str
    value: str
    date: dt_date
    control_form: Optional[str] = None
    comment: Optional[str] = None
    weight: Optional[int] = 1
    is_final: bool = False


class RankItem(BaseModel):
    subject: Optional[str] = None
    average_mark: float
    rank_place: int
    rank_status: Optional[str] = "stable"


# ========== 4. Учёба ==========
class SubjectItem(BaseModel):
    id: Optional[int] = None
    name: str
    group_name: Optional[str] = None
    teacher_name: Optional[str] = None


class ControlWork(BaseModel):
    subject: str
    topic: str
    date: dt_date
    control_form: Optional[str] = None


class ExamPrepItem(BaseModel):
    subject: str
    title: str
    type: Optional[str] = None
    progress: Optional[float] = None
    url: Optional[str] = None


class AcademicDebt(BaseModel):
    subject: str
    debt_type: str
    control_form: Optional[str] = None
    due_date: Optional[dt_date] = None


class LearningSkill(BaseModel):
    subject: str
    skill_name: str
    level: str
    score: Optional[float] = None


class RewardGift(BaseModel):
    id: Optional[str] = None
    title: str
    description: Optional[str] = None
    received_date: Optional[dt_date] = None
    badge_url: Optional[str] = None


# ========== 5. Школа ==========
class SectionClub(BaseModel):
    id: Optional[int] = None
    name: str
    schedule_description: Optional[str] = None
    teacher_name: Optional[str] = None


class Attendance(BaseModel):
    date: dt_date
    subject: str
    presence: Optional[str] = None


class BuildingPass(BaseModel):
    date: dt_date
    time: str
    entry_type: str
    address: Optional[str] = None


class FoodBalance(BaseModel):
    balance: float
    card_number: Optional[str] = None


class FoodMenuItem(BaseModel):
    date: dt_date
    meal_type: str
    dish_name: str
    price: Optional[float] = None


class SchoolEvent(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: dt_date
    end_date: Optional[dt_date] = None
    place: Optional[str] = None


class ProfileInfo(BaseModel):
    full_name: str
    class_name: str
    school_name: str
    school_address: str = "Не указан"
    school_principal: str = "Не указан"
    school_phone: str = "Не указан"
    email: str = "Не указан"
    phone: str = "Не указан"
    snils: str = "Не указан"


# ========== 6. Олимпиады ==========
class OlympiadItem(BaseModel):
    id: Optional[str] = None
    name: str
    stage: str
    subject: Optional[str] = None
    status: Optional[str] = None
    score: Optional[float] = None
    max_score: Optional[float] = None
    date: Optional[dt_date] = None
    diploma_url: Optional[str] = None


# ========== 7. Портфолио ==========
class PortfolioItem(BaseModel):
    category: str
    title: str
    description: Optional[str] = None
    date: Optional[dt_date] = None
    document_url: Optional[str] = None