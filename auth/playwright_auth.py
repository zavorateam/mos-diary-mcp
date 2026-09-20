import asyncio
import logging
from typing import Optional
from urllib.parse import quote

from playwright.async_api import async_playwright

from auth.session_manager import decode_jwt, login_with_token
from models import SessionConfig

logger = logging.getLogger("PlaywrightAuth")

# Скрипт маскировки под обычный браузер (обход Kaspersky Fraud Prevention и Yandex SmartCaptcha)
STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US', 'en'] });
"""


async def run_playwright_auth(headless: bool = False, role_id: int = 1, subsystem: int = 2) -> SessionConfig:
    """
    Запускает браузер в stealth-режиме, открывая прямой редирект на /v2/token/refresh.
    """
    # Формируем прямой backUrl с нужными параметрами
    refresh_target = f"https://school.mos.ru/v2/token/refresh?roleId={role_id}&subsystem={subsystem}"
    initial_url = f"https://school.mos.ru/?backUrl={quote(refresh_target, safe='')}"

    print("Запуск браузера для авторизации в МЭШ...")

    async with async_playwright() as p:
        # Запуск с отключением флагов автоматизации для обхода антифрода
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--start-maximized",
        ]

        browser = None
        # Пробуем системный Chrome, если установлен (самый надежный отпечаток для KFP), иначе bundled Chromium
        try:
            browser = await p.chromium.launch(
                headless=headless,
                channel="chrome",
                args=launch_args,
            )
        except Exception:
            browser = await p.chromium.launch(
                headless=headless,
                args=launch_args,
            )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0",
            locale="ru-RU",
            viewport={"width": 1280, "height": 800},
        )

        # Применяем маскировку до загрузки страницы
        await context.add_init_script(STEALTH_INIT_SCRIPT)

        page = await context.new_page()
        captured_token: Optional[str] = None
        captured_profile_id: Optional[str] = None
        captured_profile_type: str = "student" if role_id == 1 else "parent"

        # 1. Ловим токен напрямую из ответа v2/token/refresh
        async def handle_response(response):
            nonlocal captured_token
            if "/v2/token/refresh" in response.url and response.status == 200:
                try:
                    text = (await response.text()).strip().strip('"')
                    if text.startswith("Bearer "):
                        text = text[7:]
                    if text.startswith("eyJ"):
                        captured_token = text
                except Exception:
                    pass

        page.on("response", handle_response)

        # 2. Ловим токен и заголовки из фоновых запросов
        def handle_request(request):
            nonlocal captured_token, captured_profile_id, captured_profile_type
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer ey") and not captured_token:
                captured_token = auth[7:]

            p_id = request.headers.get("profile-id")
            if p_id and not captured_profile_id:
                captured_profile_id = p_id

            p_type = request.headers.get("profile-type")
            if p_type:
                captured_profile_type = p_type

        page.on("request", handle_request)

        print(f"Открываем шлюз МЭШ: {initial_url}")
        print("Пожалуйста, выполните вход в аккаунт...")
        await page.goto(initial_url, wait_until="domcontentloaded")

        # Ожидаем завершения входа и редиректа до 120 секунд
        for _ in range(120):
            if captured_token:
                break

            # Проверяем, не открылась ли страница /v2/token/refresh в самом окне
            if "/v2/token/refresh" in page.url:
                try:
                    body_text = (await page.text_content("body") or "").strip().strip('"')
                    if body_text.startswith("eyJ"):
                        captured_token = body_text
                        break
                except Exception:
                    pass

            # Безопасная проверка кук без ругательств Pylance
            cookies = await context.cookies()
            for c in cookies:
                c_name = c.get("name")
                c_value = c.get("value")
                if c_name == "aupd_token" and c_value and not captured_token:
                    captured_token = c_value
                if c_name == "active_student" and c_value and not captured_profile_id:
                    captured_profile_id = c_value

            if captured_token and captured_profile_id:
                break

            await asyncio.sleep(1.0)

        await browser.close()

        if not captured_token:
            raise RuntimeError("Авторизация не завершена: токен не был получен.")

        cfg = login_with_token(
            raw_token=captured_token,
            profile_id=captured_profile_id,
            profile_type=captured_profile_type,
        )
        print(f"✓ Вход выполнен успешно! ID профиля: {cfg.profile_id}")
        return cfg


def start_auth() -> SessionConfig:
    return asyncio.run(run_playwright_auth())


if __name__ == "__main__":
    start_auth()