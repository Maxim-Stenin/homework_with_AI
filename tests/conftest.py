"""Фикстуры прогона.

Стенд поднимается отдельной командой из AGENTS.md и НЕ запускается тестами:
если стенда нет, тесты обязаны сказать об этом прямо, а не молча поднять свой
на соседнем порту. Адрес и порт живут здесь одной константой.

Проверяемая версия задаётся переменной окружения APP_URL. По умолчанию — исходный
объект, как и было в сессии 6; ретест после фикса (сессия 8) подставляет сюда
исправленную копию. Так один и тот же набор тестов идёт против обеих версий,
и разница в результатах — это разница версий, а не разница наборов.

    исходный:    python -m pytest tests -v
    исправленный: APP_URL=http://127.0.0.1:8080/index_refactor.html python -m pytest tests -v
"""
import datetime
import os
import urllib.error
import urllib.request

import pytest

BASE_URL = os.environ.get("APP_URL", "http://127.0.0.1:8080/index.html")
STORAGE_KEY = "finance.csv"

DESKTOP = {"width": 1280, "height": 800}
MOBILE = {"width": 375, "height": 812}

TODAY = datetime.date.today()
YESTERDAY = TODAY - datetime.timedelta(days=1)
TOMORROW = TODAY + datetime.timedelta(days=1)
NEXT_YEAR = TODAY + datetime.timedelta(days=365)


@pytest.fixture(scope="session", autouse=True)
def stand_is_up():
    """Стенд проверяется по ответу, а не по факту запуска команды."""
    try:
        with urllib.request.urlopen(BASE_URL, timeout=5) as r:
            assert r.status == 200, f"стенд ответил {r.status}"
            assert r.read(), "стенд отдал пустое тело"
    except (urllib.error.URLError, OSError) as exc:
        pytest.exit(
            f"Стенд {BASE_URL} не отвечает ({exc}). Поднимите его командой из README.md:\n"
            "  py -m http.server 8080 --directory app --bind 127.0.0.1\n"
            "либо, для исправленной копии:\n"
            "  py -m http.server 8080 --directory app-fixed --bind 127.0.0.1",
            returncode=3,
        )


@pytest.fixture
def console_errors(page):
    """Побочные сигналы собираются фоном у каждого теста."""
    errors = []
    page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    return errors


@pytest.fixture
def app(page, console_errors):
    """Чистое состояние ДО загрузки страницы: иначе приложение прочитает старые данные."""
    page.set_viewport_size(DESKTOP)
    page.goto(BASE_URL)
    page.evaluate("localStorage.clear()")
    page.reload()
    yield page
    assert not console_errors, f"ошибки в консоли: {console_errors}"


@pytest.fixture
def mobile_app(browser):
    ctx = browser.new_context(viewport=MOBILE)
    pg = ctx.new_page()
    pg.goto(BASE_URL)
    pg.evaluate("localStorage.clear()")
    pg.reload()
    yield pg
    ctx.close()


@pytest.fixture
def tmp_csv(tmp_path):
    """Фабрика CSV-фикстур: файлы кладутся во временную папку pytest, не в проект."""
    def make(name: str, content: str):
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return str(p)
    return make
