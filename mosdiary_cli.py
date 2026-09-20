#!/usr/bin/env python3
import asyncio
import logging
import sys
from datetime import date, timedelta
from typing import Optional

import click
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static, TabbedContent, TabPane

logging.getLogger("httpx").setLevel(logging.WARNING)

from auth.playwright_auth import run_playwright_auth
from auth.session_manager import delete_session, load_session, login_with_token
from models import SessionConfig
from services.marks import MarksService
from services.olympiads import OlympiadsService
from services.portfolio import PortfolioService
from services.schedule import ScheduleService
from services.school import SchoolService
from services.study import StudyService
from services.tasks import TasksService


def get_config() -> SessionConfig:
    cfg = load_session()
    if cfg:
        return cfg
    raise click.ClickException(
        "Сессия не найдена. Пожалуйста, выполните вход:\n"
        "  • Через браузер: mos-diary-cli login\n"
        "  • Или по токену: mos-diary-cli login --token <JWT>"
    )


# =======================================================
# 1. TUI (Интерфейс на Textual)
# =======================================================
class DiaryScreen(Screen):
    BINDINGS = [
        Binding("q", "quit", "Выход"),
        Binding("-", "prev_day", "День -"),
        Binding("+", "next_day", "День +"),
        Binding("t", "today", "Сегодня"),
        Binding("r", "refresh", "Обновить"),
    ]

    def __init__(self, cfg: SessionConfig):
        super().__init__()
        self.cfg = cfg
        self.current_date = date.today()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Horizontal(
            Static("", id="date_label", classes="date-label"),
            Button("◀ Вчера (-)", id="prev_day_btn"),
            Button("Сегодня (t)", id="today_btn", variant="primary"),
            Button("Завтра (+) ▶", id="next_day_btn"),
            Button("🔄 Обновить (r)", id="refresh_btn", variant="warning"),
            id="date_panel",
        )

        with TabbedContent(initial="schedule"):
            with TabPane("1. Расписание", id="schedule"):
                yield DataTable(id="schedule_table")

            with TabPane("2. Задания", id="tasks"):
                yield DataTable(id="tasks_table")

            with TabPane("3. Оценки", id="marks"):
                yield DataTable(id="marks_table")

            with TabPane("4. Учёба", id="study"):
                yield DataTable(id="study_table")

            with TabPane("5. Школа", id="school"):
                yield Static("", id="school_text", classes="panel-text")

            with TabPane("6. Олимпиады", id="olympiads"):
                yield DataTable(id="olympiads_table")

            with TabPane("7. Портфолио", id="portfolio"):
                yield DataTable(id="portfolio_table")

        yield Footer()

    async def on_mount(self):
        for t_id in ("#schedule_table", "#tasks_table", "#marks_table", "#study_table", "#olympiads_table", "#portfolio_table"):
            table = self.query_one(t_id, DataTable)
            table.cursor_type = "row"

        self.update_date_label()
        await self._load_all_data()

    def update_date_label(self):
        weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        w_name = weekdays[self.current_date.weekday()]
        self.query_one("#date_label", Static).update(f"📅 {self.current_date.strftime('%d.%m.%Y')} ({w_name})")

    async def _load_all_data(self):
        loop = asyncio.get_running_loop()

        # 1. Расписание
        try:
            lessons = await loop.run_in_executor(None, ScheduleService(self.cfg).get_schedule, self.current_date, self.current_date)
            t = self.query_one("#schedule_table", DataTable)
            t.clear(columns=True)
            t.add_columns("Время", "Каб.", "Предмет", "Тема / Задание")
            if lessons:
                for les in lessons:
                    t.add_row(
                        f"{les.begin_time} - {les.end_time}",
                        les.room_number or "-",
                        les.subject,
                        (les.lesson_name or "")[:70],
                    )
            else:
                t.add_row("—", "—", "На этот день уроков нет (выходной)", "")
        except Exception:
            pass

        # 2. Домашние задания
        try:
            hws = await loop.run_in_executor(
                None,
                TasksService(self.cfg).get_homeworks,
                self.current_date,
                self.current_date + timedelta(days=14),
            )
            t = self.query_one("#tasks_table", DataTable)
            t.clear(columns=True)
            t.add_columns("Срок", "Статус", "Предмет", "Задание", "Материалы")
            if hws:
                for h in hws:
                    st = "✓ Сдано" if h.is_done else "⏳ Надо сделать"
                    mats = f"📎 ({len(h.materials)} влож.)" if h.materials else ""
                    t.add_row(h.date.strftime("%d.%m"), st, h.subject, h.description[:60], mats)
            else:
                t.add_row("—", "—", "Домашних заданий нет", "", "")
        except Exception:
            pass

        # 3. Оценки
        try:
            marks = await loop.run_in_executor(
                None,
                MarksService(self.cfg).get_marks_for_period,
                self.current_date - timedelta(days=30),
                self.current_date,
            )
            t = self.query_one("#marks_table", DataTable)
            t.clear(columns=True)
            t.add_columns("Дата", "Предмет", "Оценка", "Вес", "Форма контроля", "Комментарий")
            if marks:
                for m in marks:
                    t.add_row(
                        m.date.strftime("%d.%m"),
                        m.subject,
                        f"[{m.value}]",
                        f"x{m.weight}",
                        m.control_form or "-",
                        m.comment or "",
                    )
            else:
                t.add_row("—", "Оценок за период нет", "", "", "", "")
        except Exception:
            pass

        # 4. Учёба
        try:
            subjects = await loop.run_in_executor(None, StudyService(self.cfg).get_subjects)
            t = self.query_one("#study_table", DataTable)
            t.clear(columns=True)
            t.add_columns("Предмет", "Преподаватель", "Группа")
            for s in subjects:
                t.add_row(s.name, s.teacher_name or "Не назначен", s.group_name or "-")
        except Exception:
            pass

        # 5. Школа
        try:
            p = await loop.run_in_executor(None, SchoolService(self.cfg).get_profile_info)
            b = await loop.run_in_executor(None, SchoolService(self.cfg).get_food_balance)
            clubs = await loop.run_in_executor(None, SchoolService(self.cfg).get_sections_and_clubs)
            passes = await loop.run_in_executor(None, SchoolService(self.cfg).get_building_passes, self.current_date - timedelta(days=6), self.current_date)

            clubs_text = "\n".join([f"  • {c.name} ({c.schedule_description or ''})" for c in clubs]) if clubs else "  Нет записей"
            passes_text = "\n".join([f"  • {pass_item.date.strftime('%d.%m')} {pass_item.time} — {pass_item.entry_type} ({pass_item.address or ''})" for pass_item in passes[:5]]) if passes else "  Нет данных"

            info_text = (
                f"👤 Ученик: {p.full_name} ({p.class_name})\n"
                f"🏫 Школа: {p.school_name}\n"
                f"📍 Адрес: {p.school_address} | Директор: {p.school_principal}\n"
                f"💳 Лицевой счёт питания: {b.card_number or '—'} | Баланс: {b.balance:.2f} руб.\n\n"
                f"🎨 Кружки и секции:\n{clubs_text}\n\n"
                f"🚪 Последние проходы (Москвёнок):\n{passes_text}"
            )
            self.query_one("#school_text", Static).update(info_text)
        except Exception:
            pass

        # 6. Олимпиады
        try:
            olymp = await loop.run_in_executor(None, OlympiadsService(self.cfg).get_olympiads)
            t = self.query_one("#olympiads_table", DataTable)
            t.clear(columns=True)
            t.add_columns("Дата", "Этап", "Олимпиада / Конкурс", "Статус")
            for o in olymp:
                d_str = o.date.strftime("%d.%m.%Y") if o.date else "—"
                t.add_row(d_str, o.stage, o.name[:65], o.status or "—")
        except Exception:
            pass

        # 7. Портфолио
        try:
            port = await loop.run_in_executor(None, PortfolioService(self.cfg).get_portfolio)
            t = self.query_one("#portfolio_table", DataTable)
            t.clear(columns=True)
            t.add_columns("Дата", "Категория", "Достижение / Мероприятие", "Описание")
            for p in port:
                d_str = p.date.strftime("%d.%m.%Y") if p.date else "—"
                t.add_row(d_str, f"[{p.category}]", p.title[:55], (p.description or "")[:45])
        except Exception:
            pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "prev_day_btn":
            await self.action_prev_day()
        elif event.button.id == "next_day_btn":
            await self.action_next_day()
        elif event.button.id == "today_btn":
            await self.action_today()
        elif event.button.id == "refresh_btn":
            await self.action_refresh()

    async def action_prev_day(self):
        self.current_date -= timedelta(days=1)
        self.update_date_label()
        await self._load_all_data()

    async def action_next_day(self):
        self.current_date += timedelta(days=1)
        self.update_date_label()
        await self._load_all_data()

    async def action_today(self):
        self.current_date = date.today()
        self.update_date_label()
        await self._load_all_data()

    async def action_refresh(self):
        await self._load_all_data()

    async def action_quit(self):
        self.app.exit()


class DiaryApp(App):
    CSS = """
    #date_panel { dock: top; height: 3; align: center middle; background: $boost; padding: 0 1; }
    .date-label { padding: 0 2; text-style: bold; color: $accent; }
    .panel-text { padding: 1 2; height: 1fr; }
    DataTable { height: 1fr; }
    """

    def __init__(self, cfg: SessionConfig):
        super().__init__()
        self.cfg = cfg

    def on_mount(self):
        self.install_screen(DiaryScreen(self.cfg), name="main")
        self.push_screen("main")


# =======================================================
# 2. CLI Команды
# =======================================================
@click.group()
def cli():
    """МЭШ Дневник CLI — быстрый доступ к сервисам Московской электронной школы."""
    pass


@cli.command()
@click.option("--token", default=None, help="Прямой ввод Bearer JWT-токена (aupd_token).")
@click.option("--profile-id", default=None, help="Идентификатор профиля (если не определён автоматически).")
def login(token: Optional[str], profile_id: Optional[str]):
    """Авторизация в МЭШ через Playwright (браузер) или по токену."""
    if token:
        try:
            cfg = login_with_token(raw_token=token, profile_id=profile_id)
            click.secho(f"✓ Успешный вход по токену! Profile ID: {cfg.profile_id}", fg="green", bold=True)
        except Exception as e:
            click.secho(f"Ошибка входа: {e}", fg="red")
    else:
        try:
            asyncio.run(run_playwright_auth())
        except Exception as e:
            click.secho(f"Ошибка Playwright: {e}", fg="red")


@cli.command()
def logout():
    """Выход из аккаунта и сброс сессии."""
    if delete_session():
        click.secho("✓ Сессия успешно сброшена (session.json удалён).", fg="yellow")
    else:
        click.echo("Активная сессия не была найдена.")


@cli.command()
@click.option("--days", default=1, help="Количество дней расписания.")
def schedule(days: int):
    """1. Расписание уроков и звонков."""
    cfg = get_config()
    start = date.today()
    end = start + timedelta(days=days - 1)
    lessons = ScheduleService(cfg).get_schedule(start, end)

    weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

    lessons_by_date = {}
    cur = start
    while cur <= end:
        lessons_by_date[cur] = []
        cur += timedelta(days=1)

    for l in lessons:
        l_date = l.date or start
        if l_date in lessons_by_date:
            lessons_by_date[l_date].append(l)

    for d, day_lessons in lessons_by_date.items():
        w_name = weekdays[d.weekday()]
        click.secho(f"\n📅 {w_name}, {d.strftime('%d.%m.%Y')}:", fg="cyan", bold=True)
        if not day_lessons:
            click.echo("  🏖️ Занятий нет (выходной / каникулы)")
            continue
        for l in day_lessons:
            room = f"[{l.room_number}]" if l.room_number else ""
            click.echo(f"  🕒 {l.begin_time}-{l.end_time} {room:<7} | {l.subject}: {l.lesson_name or ''}")


@cli.command()
@click.option("--days", default=14, help="Интервал поиска ДЗ в днях.")
def tasks(days: int):
    """2. Домашние задания."""
    cfg = get_config()
    start = date.today()
    click.secho(f"\n📝 Домашние задания ({start.strftime('%d.%m')} - {(start + timedelta(days=days)).strftime('%d.%m')}):", fg="cyan", bold=True)
    hws = TasksService(cfg).get_homeworks(start, start + timedelta(days=days))
    if not hws:
        click.echo("  Заданий нет.")
        return
    for h in hws:
        mark = "✓" if h.is_done else " "
        mats = f" (📎 {len(h.materials)} влож.)" if h.materials else ""
        click.echo(f"  [{mark}] {h.date.strftime('%d.%m')} | {h.subject}: {h.description}{mats}")


@cli.command()
@click.option("--days", default=30, help="Количество дней для выборки оценок.")
def marks(days: int):
    """3. Текущие и итоговые оценки, рейтинг."""
    cfg = get_config()
    end = date.today()
    start = end - timedelta(days=days)
    svc = MarksService(cfg)

    click.secho(f"\n⭐ Оценки за последние {days} дней:", fg="cyan", bold=True)
    for m in svc.get_marks_for_period(start, end):
        cf = f"({m.control_form})" if m.control_form else ""
        click.echo(f"  {m.date.strftime('%d.%m')} | {m.subject:<30} -> Оценка: {m.value} (вес {m.weight}) {cf}")

    click.secho("\n🏆 Рейтинг по предметам:", fg="cyan", bold=True)
    for r in svc.get_rank_by_subjects():
        click.echo(f"  • {r.subject:<30}: Ср.балл {r.average_mark:.2f} | Место: {r.rank_place} ({r.rank_status})")


@cli.command()
def study():
    """4. Учёба (предметы, преподаватели, ЕГЭ, награды)."""
    cfg = get_config()
    svc = StudyService(cfg)
    click.secho("\n📚 Учебные предметы и преподаватели:", fg="cyan", bold=True)
    for s in svc.get_subjects():
        click.echo(f"  • {s.name:<35} | Учитель: {s.teacher_name or '—'}")


@cli.command()
def school():
    """5. Школа (профиль, питание, кружки, проходы)."""
    cfg = get_config()
    svc = SchoolService(cfg)
    p = svc.get_profile_info()
    b = svc.get_food_balance()
    click.secho("\n🏫 Информация об ученике и школе:", fg="cyan", bold=True)
    click.echo(f"  Ученик : {p.full_name} ({p.class_name})")
    click.echo(f"  Школа  : {p.school_name}")
    click.echo(f"  Адрес  : {p.school_address}")
    click.echo(f"  Питание: баланс {b.balance:.2f} руб. (счет: {b.card_number or '—'})")


@cli.command()
def olympiads():
    """6. Олимпиады и конкурсы."""
    cfg = get_config()
    click.secho("\n🏅 Олимпиады и этапы:", fg="cyan", bold=True)
    for o in OlympiadsService(cfg).get_olympiads():
        d_str = o.date.strftime("%d.%m.%Y") if o.date else "—"
        click.echo(f"  • [{d_str}] [{o.stage}] {o.name}: {o.status}")


@cli.command()
def portfolio():
    """7. Портфолио учащегося."""
    cfg = get_config()
    click.secho("\n🎖 Достижения и портфолио:", fg="cyan", bold=True)
    for p in PortfolioService(cfg).get_portfolio():
        d_str = p.date.strftime("%d.%m.%Y") if p.date else "—"
        click.echo(f"  • [{d_str}] [{p.category}] {p.title} — {p.description or ''}")


@cli.command()
def tui():
    """Запуск интерактивного TUI дашборда."""
    DiaryApp(get_config()).run()


def main():
    if len(sys.argv) == 1:
        DiaryApp(get_config()).run()
    else:
        cli()


if __name__ == "__main__":
    main()