"""Тесты на подтверждённые дефекты. ЭТИ ТЕСТЫ ОБЯЗАНЫ ПАДАТЬ.

Красный прогон здесь — требуемый результат и доказательство находки, а не поломка.
`xfail` не используется намеренно: он превратил бы красное в жёлтое и спрятал ровно то,
что сдаётся. Каждый тест сослан на номер BUG-NNN из qa/bugs.md и на пункт SPEC.md.

Если какой-то из этих тестов позеленел — значит объект изменили. Чинится тест
или уточняется ожидание, но НИКОГДА не объект (AGENTS.md).
"""
import pytest

from conftest import NEXT_YEAR, TOMORROW
from helpers import add, assert_rejected, legend, row_count, rows, totals


# --- BUG-001 / BUG-003: необратимые действия без подтверждения ---------------

def test_bug003_delete_asks_confirmation(app):
    """BUG-003, SPEC п.13: удаление записи обязано запрашивать подтверждение."""
    add(app, "100", category="Еда")
    add(app, "200", category="Дом")
    dialogs = []
    app.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    app.click("#tbody tr:first-child button")
    app.wait_for_timeout(300)
    assert dialogs, "подтверждение не запрошено — запись удалена сразу"


def test_bug003_cancelled_delete_keeps_row(app):
    """BUG-003: отказ от подтверждения обязан оставить запись на месте."""
    add(app, "100", category="Еда")
    app.on("dialog", lambda d: d.dismiss())
    app.click("#tbody tr:first-child button")
    app.wait_for_timeout(300)
    assert row_count(app) == 1, "запись удалена, хотя подтверждение не было получено"


def test_bug001_import_asks_confirmation(app, tmp_csv):
    """BUG-001, SPEC п.10: замена списка обязана идти через подтверждение."""
    add(app, "1200.50", category="Продукты")
    dialogs = []
    app.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    app.set_input_files("#fileInput", tmp_csv(
        "other.csv", "date,type,category,amount,comment\n2026-01-01,expense,Чужое,1.00,\n"))
    app.wait_for_timeout(400)
    assert dialogs, "список заменён без подтверждения"


def test_bug001_cancelled_import_keeps_data(app, tmp_csv):
    """BUG-001: отказ от подтверждения обязан оставить текущий список нетронутым."""
    add(app, "1200.50", category="Продукты")
    app.on("dialog", lambda d: d.dismiss())
    app.set_input_files("#fileInput", tmp_csv(
        "other.csv", "date,type,category,amount,comment\n2026-01-01,expense,Чужое,1.00,\n"))
    app.wait_for_timeout(400)
    assert any("Продукты" in r for r in rows(app)), "данные пользователя потеряны"


# --- BUG-002: битый файл стирает данные --------------------------------------

@pytest.mark.parametrize("name,content", [
    ("empty.csv", ""),
    ("garbage.csv", "это не csv вообще\nпросто текст;;;\n"),
    ("badheader.csv", "a,b,c\n1,2,3\n"),
    ("badamount.csv", "date,type,category,amount,comment\n2026-08-16,expense,Еда,abc,\n"),
    ("semicolon.csv", "date;type;category;amount;comment\n2026-08-16;expense;Еда;100.00;\n"),
    ("html.csv", "<html><body>hi</body></html>"),
    ("fewcols.csv", "date,type,category,amount,comment\n2026-08-16,expense,Еда\n"),
])
def test_bug002_broken_file_keeps_current_list(app, tmp_csv, name, content):
    """BUG-002, SPEC п.11: битый файл — сообщение об ошибке, список не изменяется."""
    add(app, "111", category="Исходная")
    before = rows(app)
    app.set_input_files("#fileInput", tmp_csv(name, content))
    app.wait_for_timeout(400)
    assert rows(app) == before, f"{name}: данные пользователя стёрты"


def test_bug002_broken_file_shows_error(app, tmp_csv):
    """BUG-002: пользователь должен увидеть причину, а не пустую таблицу."""
    add(app, "111", category="Исходная")
    app.set_input_files("#fileInput", tmp_csv("garbage.csv", "это не csv вообще\n"))
    app.wait_for_timeout(400)
    assert app.locator("#formError").inner_text().strip(), "сообщения об ошибке нет"


# --- BUG-004: категории не сливаются по регистру ------------------------------

def test_bug004_case_insensitive_categories(app):
    """BUG-004, SPEC п.4: «Кафе», «кафе» и «  кафе  » — одна категория."""
    for c in ["Кафе", "кафе", "  кафе  "]:
        add(app, "100", category=c)
    assert len(legend(app)) == 1, f"категорий в легенде: {legend(app)}"


# --- BUG-005 / BUG-006: даты --------------------------------------------------

@pytest.mark.parametrize("date,label", [
    (TOMORROW.isoformat(), "завтра"),
    (NEXT_YEAR.isoformat(), "через год"),
])
def test_bug005_future_date_rejected(app, date, label):
    """BUG-005, SPEC п.7: дата будущим числом запрещена."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, "100", category="Будущее", date=date)
    assert_rejected(app, before_rows, before_totals)


# BUG-006 отсюда убран: проверка позеленела, и это оказался дефект разведочного скрипта,
# а не объекта — пустая дата отклоняется корректно. Разбор — в qa/bugs.md, пометка к BUG-006.
# Тест живёт в tests/test_form.py::test_empty_date_is_rejected.


# --- BUG-007 / BUG-008: категория --------------------------------------------

@pytest.mark.parametrize("category", ["", "   ", "\t"])
def test_bug007_empty_category_rejected(app, category):
    """BUG-007, SPEC п.5: категория обязательна."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, "100", category=category)
    assert_rejected(app, before_rows, before_totals)


@pytest.mark.parametrize("length", [33, 200])
def test_bug008_long_category_rejected(app, length):
    """BUG-008, SPEC п.6: не более 32 символов. Граница проверена парой: 32 проходит (test_form)."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, "100", category="К" * length)
    assert_rejected(app, before_rows, before_totals)


def test_bug009_long_category_does_not_break_layout(app):
    """BUG-009, SPEC КП: вёрстка таблицы не разъезжается."""
    add(app, "100", category="К" * 200)
    doc_width = app.evaluate("() => document.documentElement.scrollWidth")
    assert doc_width <= 1280, f"страница уехала вбок: {doc_width}px при окне 1280"


def test_bug009_mobile_long_category_no_hscroll(mobile_app):
    """BUG-009 на 375×812, SPEC п.16 + КП: горизонтальной прокрутки быть не должно."""
    add(mobile_app, "300", category="К" * 60)
    doc_width = mobile_app.evaluate("() => document.documentElement.scrollWidth")
    assert doc_width <= 375, f"страница уехала вбок: {doc_width}px при окне 375"


# --- BUG-010 / BUG-011 / BUG-012: сумма --------------------------------------

def test_bug010_amount_above_limit_rejected(app):
    """BUG-010, SPEC п.3: 100 000 000 — первое отклоняемое значение."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, "100000000")
    assert_rejected(app, before_rows, before_totals)


@pytest.mark.parametrize("amount", ["1e5", "1e2", "1_000", "1..2", "+50"])
def test_bug011_loose_number_parsing_rejected(app, amount):
    """BUG-011, SPEC п.1: `1e5` и подобное — отказ, а не тихое приведение к числу."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, amount)
    assert_rejected(app, before_rows, before_totals)


@pytest.mark.parametrize("amount", ["0.001", "0.004", "1e-5"])
def test_bug012_amount_rounding_to_zero_rejected(app, amount):
    """BUG-012, SPEC п.1 + п.2: после округления сумма обязана остаться больше нуля."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, amount)
    assert_rejected(app, before_rows, before_totals)


# --- BUG-013 / BUG-014 / BUG-015: импорт не валидирует данные -----------------

def test_bug013_negative_amount_from_csv_rejected(app, tmp_csv):
    """BUG-013, SPEC п.11 + п.1: отрицательная сумма из файла не должна попадать в учёт."""
    app.set_input_files("#fileInput", tmp_csv(
        "negative.csv", "date,type,category,amount,comment\n2026-08-16,expense,Еда,-500.00,\n"))
    app.wait_for_timeout(400)
    assert row_count(app) == 0, f"загружена запись с отрицательной суммой: {rows(app)}"


def test_bug013_negative_amount_does_not_invert_balance(app, tmp_csv):
    """BUG-013: расход не может увеличивать остаток."""
    app.set_input_files("#fileInput", tmp_csv(
        "negative.csv", "date,type,category,amount,comment\n2026-08-16,expense,Еда,-500.00,\n"))
    app.wait_for_timeout(400)
    assert not totals(app)["balance"].startswith("500"), "расход увеличил остаток"


def test_bug014_unknown_type_from_csv_rejected(app, tmp_csv):
    """BUG-014, SPEC п.11: тип вне income/expense — повод отклонить файл."""
    app.set_input_files("#fileInput", tmp_csv(
        "badtype.csv", "date,type,category,amount,comment\n2026-08-16,dragon,Еда,100.00,\n"))
    app.wait_for_timeout(400)
    assert row_count(app) == 0, f"неизвестный тип загружен как расход: {rows(app)}"


def test_bug015_broken_date_from_csv_rejected(app, tmp_csv):
    """BUG-015, SPEC п.11: нечисловая дата не должна попадать в таблицу как есть."""
    app.set_input_files("#fileInput", tmp_csv(
        "baddate.csv", "date,type,category,amount,comment\nне-дата,expense,Еда,100.00,\n"))
    app.wait_for_timeout(400)
    assert row_count(app) == 0, f"загружена строка с датой «не-дата»: {rows(app)}"


def test_bug015_future_date_from_csv_rejected(app, tmp_csv):
    """BUG-015, SPEC п.11 + п.7: будущая дата запрещена и на пути импорта."""
    app.set_input_files("#fileInput", tmp_csv(
        "future.csv", "date,type,category,amount,comment\n2099-01-01,expense,Еда,100.00,\n"))
    app.wait_for_timeout(400)
    assert row_count(app) == 0, f"загружена запись из 2099 года: {rows(app)}"


def test_bug015_huge_amount_from_csv_rejected(app, tmp_csv):
    """BUG-015, SPEC п.11 + п.3: верхняя граница суммы обязана действовать и при импорте."""
    app.set_input_files("#fileInput", tmp_csv(
        "huge.csv", "date,type,category,amount,comment\n2026-08-16,expense,Еда,999999999999,\n"))
    app.wait_for_timeout(400)
    assert row_count(app) == 0, f"загружена сумма вне границы: {rows(app)}"
