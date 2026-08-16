"""Фикстуры прогона по ИСПРАВЛЕННОЙ копии объекта.

Набор — копия `tests/`, сделанная в сессии 9 (роль Тестировщика) и поправленная
под `app-fixed/index_refactor.html`. Старый набор `tests/` НЕ ТРОГАЛСЯ намеренно:
он доказывает прогон сессии 6 по исходному объекту, на него ссылаются
`full-run/test-plan.md`, `review/results.md` и база сравнения
`fix-run/artifacts/baseline-original.txt`. Поправив его на месте, мы потеряли бы
возможность воспроизвести прошлое измерение.

Что изменено против `tests/conftest.py` и почему:

1. `BASE_URL` по умолчанию указывает на `index_refactor.html`. Раньше по умолчанию
   стоял исходный объект, и адрес исправленной копии приходилось задавать переменной
   окружения. Для набора, который существует ровно ради ретеста, умолчание наоборот:
   забытая переменная окружения не должна тихо увести прогон на другую версию.
2. Добавлена фикстура `dialogs` — сборщик сообщений `confirm`. В фиксе появились
   подтверждения при удалении и загрузке (SPEC п. 10 и п. 13), а Playwright по умолчанию
   **отклоняет** любой диалог. Тест, который об этом не знает, показывает «действие
   не выполнилось» и выглядит как провал фикса.

Запуск (стенд поднимается отдельно, тестами не поднимается):

    py -m http.server 8080 --directory app-fixed --bind 127.0.0.1
    py -m pytest tests-fixed -v
"""
import datetime
import os
import urllib.error
import urllib.request

import pytest

BASE_URL = os.environ.get("APP_URL", "http://127.0.0.1:8080/index_refactor.html")
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
            f"Стенд {BASE_URL} не отвечает ({exc}). Поднимите его командой из AGENTS.md:\n"
            "  py -m http.server 8080 --directory app-fixed --bind 127.0.0.1\n"
            "Обе версии на одном порту: одновременно поднимается только одна.",
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
def dialogs(page):
    """Все диалоги, которые страница показала за тест.

    Нужна там, где проверяется САМ ФАКТ подтверждения, а не его последствие:
    приложение, которое молча делает необратимое, и приложение, которое спросило
    и получило согласие, снаружи выглядят одинаково.
    """
    seen = []
    page.on("dialog", lambda d: (seen.append(d.message), d.dismiss()))
    return seen


@pytest.fixture
def tmp_csv(tmp_path):
    """Фабрика CSV-фикстур: файлы кладутся во временную папку pytest, не в проект."""
    def make(name: str, content: str):
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return str(p)
    return make
