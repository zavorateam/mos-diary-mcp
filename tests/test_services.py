from datetime import date, timedelta
import httpx
import pytest

from models import SessionConfig
from services.base import BaseMeshService
from services.marks import MarksService
from services.schedule import ScheduleService
from services.school import SchoolService
from services.tasks import TasksService


def test_base_service_headers(mock_session_config: SessionConfig):
    """Проверяет отсутствие кук и наличие обязательных заголовков."""
    service = BaseMeshService(mock_session_config)
    headers = service.client.headers

    assert headers["Authorization"] == f"Bearer {mock_session_config.token}"
    assert headers["Profile-Id"] == mock_session_config.profile_id
    assert headers["X-mes-subsystem"] == "familyweb"
    assert headers["X-Mes-RoleId"] == "1"
    assert len(service.client.cookies) == 0


def test_base_service_auto_refresh_on_401(mock_session_config: SessionConfig, monkeypatch: pytest.MonkeyPatch):
    """Проверяет повторный запрос при получении 401 Unauthorized."""
    attempts = 0

    def handler(request: httpx.Request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(401, text="Unauthorized")
        return httpx.Response(200, json={"payload": "success"})

    client = httpx.Client(base_url="https://school.mos.ru", transport=httpx.MockTransport(handler))
    service = BaseMeshService(mock_session_config, client=client)

    # Мокаем успешный рефреш
    monkeypatch.setattr(service, "_handle_unauthorized", lambda: True)

    resp = service.get("/test/endpoint")
    assert resp.status_code == 200
    assert attempts == 2


def test_schedule_service(mock_session_config: SessionConfig):
    """Проверяет парсинг расписания уроков."""

    def handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "response": [
                    {
                        "subject_name": "Геометрия",
                        "start_at": "2026-09-20T08:30:00",
                        "finish_at": "2026-09-20T09:15:00",
                        "room_number": "304",
                        "topic": "Теорема Пифагора",
                    }
                ]
            },
        )

    mock_client = httpx.Client(base_url="https://school.mos.ru", transport=httpx.MockTransport(handler))
    svc = ScheduleService(mock_session_config, client=mock_client)
    lessons = svc.get_schedule(date(2026, 9, 20), date(2026, 9, 20))

    assert len(lessons) == 1
    assert lessons[0].subject == "Геометрия"
    assert lessons[0].begin_time == "08:30"
    assert lessons[0].room_number == "304"
    assert lessons[0].lesson_name == "Теорема Пифагора"


def test_tasks_service(mock_session_config: SessionConfig):
    """Проверяет парсинг домашних заданий и вложенных материалов."""

    def handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "payload": [
                    {
                        "subject_name": "Литература",
                        "homework": "Читать главу 4",
                        "date": "2026-09-22",
                        "is_done": False,
                        "materials": [{"title": "Учебник", "urls": [{"url": "https://uchebnik.mos.ru"}]}],
                    }
                ]
            },
        )

    mock_client = httpx.Client(base_url="https://school.mos.ru", transport=httpx.MockTransport(handler))
    svc = TasksService(mock_session_config, client=mock_client)
    hws = svc.get_homeworks()

    assert len(hws) == 1
    assert hws[0].subject == "Литература"
    assert hws[0].is_done is False
    assert len(hws[0].materials) == 1
    assert hws[0].materials[0].url == "https://uchebnik.mos.ru"


def test_marks_service(mock_session_config: SessionConfig):
    """Проверяет парсинг оценок."""

    def handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "payload": [
                    {
                        "subject_name": "Физика",
                        "value": "5",
                        "date": "2026-09-18",
                        "weight": 2,
                        "control_form_name": "Лабораторная работа",
                    }
                ]
            },
        )

    mock_client = httpx.Client(base_url="https://school.mos.ru", transport=httpx.MockTransport(handler))
    svc = MarksService(mock_session_config, client=mock_client)
    marks = svc.get_marks_for_period()

    assert len(marks) == 1
    assert marks[0].value == "5"
    assert marks[0].weight == 2
    assert marks[0].control_form == "Лабораторная работа"


def test_school_service_passes_limit(mock_session_config: SessionConfig):
    """Проверяет строгое ограничение диапазона проходов (не более 7 дней), защищая от HTTP 400."""
    requested_params = {}

    def handler(request: httpx.Request):
        nonlocal requested_params
        requested_params = dict(request.url.params)
        return httpx.Response(200, json={"payload": []})

    mock_client = httpx.Client(base_url="https://school.mos.ru", transport=httpx.MockTransport(handler))
    svc = SchoolService(mock_session_config, client=mock_client)

    today = date(2026, 9, 20)
    svc.get_building_passes(start_date=today - timedelta(days=20), end_date=today)

    from_dt = date.fromisoformat(requested_params["from"])
    to_dt = date.fromisoformat(requested_params["to"])
    diff_days = (to_dt - from_dt).days + 1
    assert diff_days <= 7  # Требование шлюза МЭШ


def test_school_food_balance(mock_session_config: SessionConfig):
    """Проверяет расчет баланса питания из копеек в рубли."""

    def handler(request: httpx.Request):
        return httpx.Response(200, json=[{"balance": 15450, "contractId": "987654321"}])

    mock_client = httpx.Client(base_url="https://school.mos.ru", transport=httpx.MockTransport(handler))
    svc = SchoolService(mock_session_config, client=mock_client)
    food = svc.get_food_balance()

    assert food.balance == 154.50
    assert food.card_number == "987654321"