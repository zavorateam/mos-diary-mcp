# 🎓 mos-diary-cli

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Textual](https://img.shields.io/badge/Textual-TUI-purple.svg)](https://textual.textualize.io/)
[![MCP](https://img.shields.io/badge/MCP-Protocol-orange.svg)](https://modelcontextprotocol.io/)
[![Tests: Pytest](https://img.shields.io/badge/tests-21%20passed-brightgreen.svg)](https://pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**mos-diary-cli** — полнофункциональный модульный Python-клиент, консольный интерфейс (CLI), интерактивный TUI-дашборд и сервер (REST API + MCP) для экосистемы **«Московской электронной школы» (МЭШ / [school.mos.ru](https://school.mos.ru))**.

Единый универсальный шлюз к школьным данным: от расписания и домашних заданий до оценок, рейтингов, меню столовой, проходов через турникеты («Москвёнок»), олимпиад и портфолио. К сожалению, только read-only для данных.

---

## Возможности проекта

| Сервис | Описание | Основные эндпоинты |
|---|---|---|
| **1. Расписание** | Расписание уроков, кабинеты, темы занятий, сетка звонков и учебные периоды/каникулы. | `/api/schedule`, `/api/schedule/bells`, `/api/schedule/periods` |
| **2. Задания** | Домашние задания со статусами сдачи, прикреплёнными файлами и материалами ЦДЗ. | `/api/tasks/homeworks`, `/api/tasks/projects` |
| **3. Оценки** | Текущие оценки с весами и формами контроля, итоговые/годовые оценки, рейтинг по классу и предметам. | `/api/marks`, `/api/marks/final`, `/api/marks/ranks/*` |
| **4. Учёба** | Учебный план с преподавателями, подготовка к ЕГЭ/ОГЭ, задолженности, Soft Skills, мерч МЭШ. | `/api/study/subjects`, `/api/study/exam-prep`, `/api/study/rewards` |
| **5. Школа** | Карточка школы, кружки и секции, фиксация проходов («Москвёнок»), баланс лицевого счёта и меню. | `/api/school/profile`, `/api/school/sections`, `/api/school/passes`, `/api/school/food/*` |
| **6. Олимпиады** | Всероссийская и Московская олимпиады, этапы (Школьный, Муниципальный и др.), статусы участия. | `/api/olympiads` |
| **7. Портфолио** | Творчество, культура (посещения музеев), результаты независимых диагностик МЦКО и ГИА. | `/api/portfolio` |

---

## 🖥️ Сценарии использования

1. **Человек в терминале (TUI / CLI):**
   * Быстрый просмотр уроков, ДЗ или оценок одной командой в bash/zsh.
   * Полноэкранный интерактивный терминальный интерфейс (TUI) на библиотеке Textual с навигацией по датам и вкладкам.
2. **AI-ассистенты (Model Context Protocol / MCP):**
   * Прямое подключение к Claude Desktop, Cursor, Continue или любому LLM-агенту через стандартный ввод/вывод (`stdio`).
3. **Локальный микросервис (REST API + OpenAPI):**
   * Полноценный сервер FastAPI с автодокументацией Swagger UI для интеграций (виджеты, Telegram-боты, умный дом).

---

## 📁 Структура проекта

```text
mos-diary-cli/
├── auth/
│   ├── session_manager.py  # Управление сессией: JWT decode, session.json, авторефреш
│   └── playwright_auth.py  # Веб-авторизация (Playwright) с защитой от KFP антифрода
├── services/
│   ├── base.py             # Базовый HTTP-клиент с управлением сессиями и заголовками
│   ├── schedule.py         # 1. Расписание уроков, звонки, каникулы
│   ├── tasks.py            # 2. Домашние задания и проектная деятельность
│   ├── marks.py            # 3. Текущие/итоговые оценки и рейтинги
│   ├── study.py            # 4. Учебный план, учителя, ЕГЭ/ОГЭ, навыки, награды
│   ├── school.py           # 5. Профиль школы, кружки, турникеты («Москвёнок»), еда
│   ├── olympiads.py        # 6. Олимпиады и конкурсы
│   └── portfolio.py        # 7. Достижения, культура, ГИА, МЦКО
├── tests/
│   ├── conftest.py         # Изоляция session.json и тестовые фикстуры
│   ├── test_auth.py        # Тесты JWT, session_manager и рефреша
│   ├── test_services.py    # Тесты доменных сервисов МЭШ и сетевых моков
│   ├── test_api_endpoints.py # Тесты REST API эндпоинтов FastAPI
│   └── test_cli.py         # Тесты CLI команд Click
├── models.py               # Единый реестр Pydantic v2 моделей данных
├── mosdiary_cli.py         # Клиент: Click CLI + Textual TUI дашборд
├── mosdiary_server.py      # Сервер: FastAPI REST API (--http) / MCP Server (по умолчанию)
├── session.json            # Локальная сессия авторизации (создаётся автоматически)
└── requirements.txt        # Зависимости проекта
```

---

## 🛠️ Установка и настройка

### 1. Клонирование и зависимости

```bash
git clone https://github.com/your-username/mos-diary-cli.git
cd mos-diary-cli

python3 -m venv .venv
source .venv/bin/activate  # На Windows: .venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

### 2. Авторизация

Доступно два варианта входа:

**Вариант А: Интерактивно через браузер (рекомендуется):**
```bash
python mosdiary_cli.py login
```
Откроется окно браузера с официальным шлюзом авторизации МЭШ / СУДИР. Войдите по логину/паролю или через Госуслуги. Клиент автоматически перехватит токен, заполнит `profile_id` и сохранит конфигурацию в `session.json`.

**Вариант Б: Прямой ввод токена:**
```bash
python mosdiary_cli.py login --token "eyJhbGciOiJSUzI1NiIs..."
```
Клиент автоматически декодирует идентификатор ученика, обратится к профилю МЭШ и сохранит сессию.

**Сброс сессии:**
```bash
python mosdiary_cli.py logout
```

---

## 💻 Использование

### 1. Интерактивный TUI-дашборд

Запуск визуального терминального интерфейса:

```bash
python mosdiary_cli.py
# или
python mosdiary_cli.py tui
```

* **Горячие клавиши:**
  * `+` / `-` — переход к следующему / предыдущему дню;
  * `t` — возврат на сегодняшний день;
  * `r` — принудительное обновление данных;
  * `q` — выход из дашборда;
  * `Мышь` / `Tab` — переключение между 7 вкладками.

---

### 2. Консольные команды (CLI)

```bash
# 1. Расписание уроков на сегодня
python mosdiary_cli.py schedule

# Расписание на 3 дня вперёд
python mosdiary_cli.py schedule --days 3

# 2. Домашние задания на ближайшие 14 дней
python mosdiary_cli.py tasks --days 14

# 3. Оценки за последние 30 дней и рейтинг
python mosdiary_cli.py marks --days 30

# 4. Учебный план и преподаватели
python mosdiary_cli.py study

# 5. Профиль школы, кружки и баланс карты «Москвёнок»
python mosdiary_cli.py school

# 6. Олимпиады и конкурсы
python mosdiary_cli.py olympiads

# 7. Достижения и портфолио
python mosdiary_cli.py portfolio
```

---

### 3. REST API Сервер (FastAPI + Swagger UI)

Запуск локального сервера:

```bash
python mosdiary_server.py --http --host 127.0.0.1 --port 8000
```

* **Swagger UI документация:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **OpenAPI схема:** [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

**Примеры запросов (`curl`):**
```bash
# Авторизация/смена токена через REST
curl -X POST http://127.0.0.1:8000/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"token": "eyJhbGciOiJSUz..."}'

# Получить расписание уроков
curl http://127.0.0.1:8000/api/schedule

# Баланс питания «Москвёнок»
curl http://127.0.0.1:8000/api/school/food/balance
```

---

### 4. Подключение к AI через MCP (Model Context Protocol)

Для подключения к **Claude Desktop**, **Cursor** или **Continue**, добавьте конфигурацию в ваш `mcpServers`:

```json
{
  "mcpServers": {
    "mosdiary": {
      "command": "python",
      "args": [
        "/абсолютный/путь/к/mos-diary-cli/mosdiary_server.py"
      ]
    }
  }
}
```

LLM-ассистент получит доступ к инструментам:
* `mes_auth_token` — авторизация/смена активного Bearer токена;
* `mes_get_schedule` — расписание уроков и сетка звонков;
* `mes_get_homeworks` — список домашних заданий с материалами;
* `mes_get_projects` — активные проектные работы;
* `mes_get_marks` — текущие оценки и формы контроля;
* `mes_get_ranks` — рейтинг учащегося по классу и предметам;
* `mes_get_study_overview` — контрольные работы, долги, Soft Skills и награды;
* `mes_get_school_overview` — профиль школы, кружки, баланс питания и проходы через турникет;
* `mes_get_olympiads` — олимпиады и этапы участия;
* `mes_get_portfolio` — культурные мероприятия, независимые диагностики и экзамены.

---

## 🧪 Тестирование

Запуск полного набора изолированных модульных тестов:

```bash
pytest tests/ -v
```

Все 21 тест выполняются оффлайн благодаря `httpx.MockTransport` и не требуют активного подключения к серверам МЭШ, да и вообще с ним не взаимодействует.

---

## Перспективы (Roadmap)

- [ ] Асинхронная неблокирующая подгрузка данных в TUI.
- [ ] Поддержка многопрофильности (переключение между несколькими детьми для роли родителя).
- [ ] Экспорт расписания уроков в календари (`.ics` / Google Calendar / Apple Calendar).

---

## 📄 Лицензия и отказ от ответственности

Проект распространяется под лицензией **MIT**.

**Отказ от ответственности:** Данный программный комплекс является неофициальным инструментом и разрабатывается исключительно в образовательных и исследовательских целях. Все права на товарные знаки и сервисы «МЭШ» и «Московская электронная школа» принадлежат их законным правообладателям (Правительство Москвы / ДИТ Москвы).