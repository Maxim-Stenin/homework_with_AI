# Рецепты кода

Заготовки для `tests/`. **Селекторы в примерах условные** — настоящие берутся из разметки
`app/index.html` при написании тестов. Дописывать атрибуты в объект ради удобства
запрещено; если за нужный элемент не за что зацепиться, это записывается как замечание
о тестопригодности.

## conftest.py — константы и стенд

```python
import subprocess, sys, time, urllib.request
import pytest

BASE_URL = "http://127.0.0.1:8080/index.html"
DESKTOP = {"width": 1280, "height": 800}
MOBILE = {"width": 375, "height": 812}


def _stand_alive() -> bool:
    try:
        with urllib.request.urlopen(BASE_URL, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def stand():
    """Стенд должен отвечать до первого теста.

    Без этой проверки отсутствующий стенд даёт два десятка таймаутов локаторов,
    из которых причина не читается.
    """
    if _stand_alive():
        yield BASE_URL
        return
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8080",
         "--directory", "app", "--bind", "127.0.0.1"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        if _stand_alive():
            break
        time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"Стенд не поднялся на {BASE_URL}. Порт 8080 занят?")
    yield BASE_URL
    proc.terminate()
```

## Чистое состояние и сбор ошибок консоли

Очистка делается **до** загрузки страницы: иначе приложение успеет прочитать старые
данные из `localStorage`, и тест будет зависеть от предыдущего.

```python
@pytest.fixture
def app(page):
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.set_viewport_size(DESKTOP)
    page.goto(BASE_URL)
    page.evaluate("() => localStorage.clear()")
    page.reload()

    page.console_errors = errors
    yield page
```

Проверка побочного сигнала в конце теста — отдельным утверждением, а не «заодно»:

```python
def test_basic_scenario(app):
    ...
    assert app.console_errors == [], f"Ошибки в консоли: {app.console_errors}"
```

Для мобильного блока — своя фикстура с `MOBILE`; после смены ширины страница
перезагружается, чтобы отработали правила, применяемые при загрузке.

## helpers.py — действия и наблюдения

Всё, что тест делает с приложением, живёт здесь. Тогда тело теста читается как описание
проверки, а не как последовательность кликов.

```python
def add_entry(page, amount, category, date, kind="расход"):
    page.get_by_label("Сумма").fill(str(amount))
    page.get_by_label("Категория").fill(category)
    page.get_by_label("Дата").fill(date)
    page.get_by_role("radio", name=kind).check()
    page.get_by_role("button", name="Добавить").click()


def row_count(page) -> int:
    return page.locator("table tbody tr").count()


def totals(page) -> dict:
    """Числа из блока итогов, приведённые к float."""
    def num(sel):
        raw = page.locator(sel).inner_text()
        return float(raw.replace(" ", "").replace(" ", "").replace(",", "."))
    return {"income": num("#total-income"),
            "expense": num("#total-expense"),
            "balance": num("#balance")}


def legend(page) -> dict:
    """Категория → доля в процентах, как показано в легенде."""
    out = {}
    for item in page.locator(".legend-item").all():
        name = item.locator(".legend-name").inner_text().strip()
        share = item.locator(".legend-share").inner_text().strip().rstrip("%")
        out[name] = float(share.replace(",", "."))
    return out
```

## Параметризация классов эквивалентности

Таблица случаев вместо двадцати похожих тестов. `id=` обязателен: без него в выводе
`pytest` упавший случай читается как `test_rejects[case12]`.

```python
import pytest
from helpers import add_entry, row_count, totals

REJECTED_AMOUNTS = [
    ("0",            "ноль"),
    ("-500",         "отрицательная"),
    ("-0.01",        "отрицательная на границе"),
    ("",             "пустая"),
    ("   ",          "только пробелы"),
    ("abc",          "нечисловая"),
    ("12abc",        "число с хвостом"),
    ("1e5",          "экспоненциальная запись"),
    ("1,5",          "запятая как разделитель"),
    ("100000000",    "на единицу больше предела"),
]


@pytest.mark.parametrize("amount,case", REJECTED_AMOUNTS,
                         ids=[c for _, c in REJECTED_AMOUNTS])
def test_amount_rejected(app, amount, case):
    before_rows, before_totals = row_count(app), totals(app)

    add_entry(app, amount, "Кафе", "2026-08-10")

    # Порядок важен: сначала убеждаемся, что записи НЕ появилось,
    # и только потом — что показано сообщение.
    assert row_count(app) == before_rows, f"Создана запись при сумме {amount!r}"
    assert totals(app) == before_totals, f"Итоги изменились при сумме {amount!r}"
```

Границы задаются парами в одной таблице — проходящее значение и следующее за ним
отклоняемое (`99999999` / `100000000`, 32 символа / 33), чтобы пара не разошлась
при правке.

## Даты считаются, а не пишутся константой

```python
from datetime import date, timedelta

TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
```

Константа `2026-08-14` протухнет и однажды начнёт падать не по дефекту.

## Диалоги подтверждения

Playwright по умолчанию **отклоняет** диалоги браузера. Оба исхода проверяются явно —
и отказ важнее согласия, потому что именно он должен оставить данные нетронутыми.

```python
def test_delete_cancel_keeps_entry(app):
    add_entry(app, 100, "Кафе", TODAY)
    before = row_count(app)

    app.once("dialog", lambda d: d.dismiss())
    app.get_by_role("button", name="Удалить").first.click()

    assert row_count(app) == before, "Отказ от подтверждения удалил запись"
```

Если подтверждение реализовано не диалогом браузера, а элементом на странице,
обработчик не сработает — тест должен падать с внятным сообщением, а не молча
проходить. Проверить это до того, как поверить зелёному прогону.

## Выгрузка файла

```python
def test_export_escapes_quotes(app, tmp_path):
    add_entry(app, 250, 'кофе, "с собой"', TODAY)

    with app.expect_download() as info:
        app.get_by_role("button", name="Сохранить CSV").click()
    path = tmp_path / "out.csv"
    info.value.save_as(path)

    text = path.read_text(encoding="utf-8")
    assert '"кофе, ""с собой"""' in text, f"Экранирование нарушено:\n{text}"
```

Файлы кладутся в `tmp_path` — временный каталог pytest. **Не в папку проекта:**
`AGENTS.md` запрещает писать туда временные файлы.

## Загрузка файла и фикстуры данных

```python
def test_import_broken_row_keeps_list(app):
    add_entry(app, 100, "Кафе", TODAY)
    before = row_count(app)

    app.once("dialog", lambda d: d.accept())
    app.locator("input[type=file]").set_input_files("tests/fixtures/broken_middle.csv")

    assert row_count(app) == before, "Битый файл частично загрузился"
```

Набор файлов в `tests/fixtures/`: `valid_5.csv`, `empty.csv`, `header_only.csv`,
`garbage.txt`, `broken_middle.csv`, `extra_column.csv`, `missing_column.csv`,
`negative_amount.csv`, `future_date.csv`, `long_category.csv`, `over_limit.csv`,
`cp1251.csv`.

Последние пять — самая ценная группа: они отвечают на вопрос, применяется ли валидация
формы к данным из файла. Валидация, живущая только в обработчике формы, — типичный
дефект, и найти его можно только импортом.

## Цикл «сохранить → загрузить»

```python
def test_roundtrip_preserves_dirty_values(app, tmp_path):
    entries = [
        (250,      'кофе, "с собой"'),
        (1000,     "Зарплата"),
        (99999999, "Продажа"),
    ]
    for amount, category in entries:
        add_entry(app, amount, category, TODAY)
    before_rows = table_snapshot(app)     # список кортежей из строк таблицы

    with app.expect_download() as info:
        app.get_by_role("button", name="Сохранить CSV").click()
    path = tmp_path / "rt.csv"
    info.value.save_as(path)

    app.evaluate("() => localStorage.clear()")
    app.reload()
    app.once("dialog", lambda d: d.accept())
    app.locator("input[type=file]").set_input_files(str(path))

    assert table_snapshot(app) == before_rows, "Цикл CSV изменил данные"
```

Сравнивается снимок таблицы целиком, а не отдельные поля: так тест ловит и потерю
записи, и перепутанные колонки, и изменившийся порядок.

## Инварианты

Отдельные тесты, проверяющие то, что обязано выполняться при любом входе. Они ловят
дефекты, для которых никто не написал прицельной проверки.

```python
def test_totals_match_table(app):
    for amount, category, kind in DATASET:
        add_entry(app, amount, category, TODAY, kind)

    rows = table_snapshot(app)
    income = sum(r.amount for r in rows if r.kind == "доход")
    expense = sum(r.amount for r in rows if r.kind == "расход")

    t = totals(app)
    assert t["income"] == pytest.approx(income, abs=0.01)
    assert t["expense"] == pytest.approx(expense, abs=0.01)
    assert t["balance"] == pytest.approx(income - expense, abs=0.01)


def test_legend_shares_sum_to_100(app):
    ...
    assert sum(legend(app).values()) == pytest.approx(100.0, abs=0.5)
```

`pytest.approx` с явным допуском — потому что на экране числа округлены до двух знаков.
Допуск указывается осознанно: слишком широкий скроет дефект округления, ради которого
проверка и написана.

## Тесты на подтверждённых дефектах

Живут в `tests/test_defects.py`. Каждый снабжён ссылкой на баг-репорт и на пункт
спецификации, и каждый **падает**.

```python
def test_category_case_insensitive():
    """BUG-003 · SPEC часть А, пункт 4.

    «Кафе» и «кафе» должны давать один сегмент диаграммы.
    Тест падает — это и есть доказательство дефекта.
    Объект не правится: починка — роль Автора и отдельная сессия.
    """
```

`xfail` не используется: он делает прогон жёлтым и прячет ровно то, что сдаётся.
