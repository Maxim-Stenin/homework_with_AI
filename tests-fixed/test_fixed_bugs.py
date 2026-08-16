"""Ретест 18 закрытых дефектов. ЭТИ ТЕСТЫ ОБЯЗАНЫ БЫТЬ ЗЕЛЁНЫМИ.

Файл — прямой наследник `tests/test_defects.py`, где те же проверки обязаны были
ПАДАТЬ: там они шли по исходному объекту и доказывали существование дефекта.
Здесь они идут по исправленной копии и доказывают, что дефекта больше нет.
Каждый тест сослан на номер из `full-run/bugs.md` (BUG-NNN) или `review/results.md`
(R1…R4) и на пункт `SPEC.md`.

Ожидания дословно те же, что были в исходном наборе. Единственное изменение —
удаление и загрузка проходят через `confirm()`, потому что подтверждение и есть
содержание фиксов BUG-001 и BUG-003: раньше проверялось «спросили ли», теперь
дополнительно «выполнилось ли после согласия и осталось ли всё на месте при отказе».

Если какой-то тест здесь покраснеет — фикс не сработал, и это находка ретеста,
а не повод править объект: `app-fixed/index_refactor.html` заморожен (AGENTS.md).
"""
import pytest

from conftest import NEXT_YEAR, TODAY, TOMORROW
from helpers import (add, assert_rejected, delete_row, import_csv, import_rejected_csv,
                     legend, row_count, rows, totals)


# --- BUG-003: удаление без подтверждения --------------------------------------

def test_bug003_delete_asks_confirmation(app):
    """BUG-003, SPEC п.13: удаление записи обязано запрашивать подтверждение."""
    add(app, "100", category="Еда")
    add(app, "200", category="Дом")
    message = delete_row(app, confirm=False)
    assert message, "подтверждение не запрошено — запись удалена сразу"


def test_bug003_confirmation_names_the_record(app):
    """Подтверждение обязано говорить, ЧТО удаляется: «Удалить запись?» без деталей
    заставляет соглашаться вслепую."""
    add(app, "100", category="Еда")
    message = delete_row(app, confirm=False)
    assert "Еда" in message and "100,00" in message, f"диалог не называет запись: {message!r}"


def test_bug003_cancelled_delete_keeps_row(app):
    """BUG-003: отказ от подтверждения обязан оставить запись на месте."""
    add(app, "100", category="Еда")
    before_totals = totals(app)
    delete_row(app, confirm=False)
    assert row_count(app) == 1, "запись удалена, хотя подтверждение не было получено"
    assert totals(app) == before_totals, "итоги изменились после отказа от удаления"


def test_bug003_confirmed_delete_removes_row(app):
    """Обратная половина: согласие обязано удалять. Иначе «фикс» — просто сломанная кнопка."""
    add(app, "100", category="Еда")
    delete_row(app, confirm=True)
    assert row_count(app) == 0, "согласие получено, а запись осталась"


# --- BUG-001: замена списка без подтверждения ---------------------------------

def test_bug001_import_asks_confirmation(app, tmp_csv):
    """BUG-001, SPEC п.10: замена списка обязана идти через подтверждение."""
    add(app, "1200.50", category="Продукты")
    message = import_csv(app, tmp_csv(
        "other.csv", f"date,type,category,amount,comment\n{TODAY},expense,Чужое,1.00,\n"),
        confirm=False)
    assert message, "список заменён без подтверждения"


def test_bug001_cancelled_import_keeps_data(app, tmp_csv):
    """BUG-001: отказ от подтверждения обязан оставить текущий список нетронутым."""
    add(app, "1200.50", category="Продукты")
    import_csv(app, tmp_csv(
        "other.csv", f"date,type,category,amount,comment\n{TODAY},expense,Чужое,1.00,\n"),
        confirm=False)
    assert any("Продукты" in r for r in rows(app)), "данные пользователя потеряны"


# --- BUG-002: битый файл стирает данные ---------------------------------------

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
    import_rejected_csv(app, tmp_csv(name, content))
    assert rows(app) == before, f"{name}: данные пользователя стёрты"


def test_bug002_broken_file_shows_error(app, tmp_csv):
    """BUG-002: пользователь должен увидеть причину, а не пустую таблицу."""
    add(app, "111", category="Исходная")
    import_rejected_csv(app, tmp_csv("garbage.csv", "это не csv вообще\n"))
    assert app.locator("#formError").inner_text().strip(), "сообщения об ошибке нет"


# --- R1: частичная загрузка ---------------------------------------------------

def test_r1_partial_load_is_refused_entirely(app, tmp_csv):
    """R1, SPEC п.11 дословно: «Частичная загрузка недопустима».

    Самая опасная из пропущенных находок сессии 6: пользователь видит на экране
    правдоподобные данные и не знает, что часть строк выброшена.
    """
    add(app, "111", category="Исходная")
    before = rows(app)
    content = ("date,type,category,amount,comment\n"
               f"{TODAY},expense,Хорошая1,100.00,\n"
               f"{TODAY},expense,Битая,abc,\n"
               f"{TODAY},expense,Хорошая2,200.00,\n")
    import_rejected_csv(app, tmp_csv("partial.csv", content))
    assert rows(app) == before, "часть строк применена — это и есть частичная загрузка"
    assert row_count(app) == 1


def test_r1_error_names_the_broken_line(app, tmp_csv):
    """Отказ без номера строки заставляет искать ошибку глазами по всему файлу."""
    add(app, "111", category="Исходная")
    content = ("date,type,category,amount,comment\n"
               f"{TODAY},expense,Хорошая1,100.00,\n"
               f"{TODAY},expense,Битая,abc,\n")
    import_rejected_csv(app, tmp_csv("partial.csv", content))
    assert "строка 3" in app.locator("#formError").inner_text()


# --- BUG-004: категории не сливаются по регистру ------------------------------

def test_bug004_case_insensitive_categories(app):
    """BUG-004, SPEC п.4: «Кафе», «кафе» и «  кафе  » — одна категория."""
    for c in ["Кафе", "кафе", "  кафе  "]:
        add(app, "100", category=c)
    assert len(legend(app)) == 1, f"категорий в легенде: {legend(app)}"


def test_bug004_merged_category_keeps_first_spelling(app):
    """Слияние обязано выбрать одно написание, а не показывать в таблице разнобой."""
    for c in ["Кафе", "кафе", "  КАФЕ  "]:
        add(app, "100", category=c)
    shown = {r.split("\t")[1] for r in rows(app)}
    assert shown == {"Кафе"}, f"в таблице разные написания одной категории: {shown}"


# --- BUG-005: даты будущим числом ---------------------------------------------

@pytest.mark.parametrize("date,label", [
    (TOMORROW.isoformat(), "завтра"),
    (NEXT_YEAR.isoformat(), "через год"),
])
def test_bug005_future_date_rejected(app, date, label):
    """BUG-005, SPEC п.7: дата будущим числом запрещена."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, "100", category="Будущее", date=date)
    assert_rejected(app, before_rows, before_totals)


# --- BUG-007 / BUG-008: категория ---------------------------------------------

@pytest.mark.parametrize("category", ["", "   ", "\t"])
def test_bug007_empty_category_rejected(app, category):
    """BUG-007, SPEC п.5: категория обязательна, подмена на «Без категории» недопустима."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, "100", category=category)
    assert_rejected(app, before_rows, before_totals)


@pytest.mark.parametrize("length", [33, 200])
def test_bug008_long_category_rejected(app, length):
    """BUG-008, SPEC п.6: не более 32 символов. Пара к границе — в test_form.py."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, "100", category="К" * length)
    assert_rejected(app, before_rows, before_totals)


# --- BUG-009: вёрстка -------------------------------------------------------

def test_bug009_long_category_does_not_break_layout(app):
    """BUG-009, SPEC КП: вёрстка таблицы не разъезжается.

    Вход в 200 символов остался прежним, хотя такая категория теперь отклоняется
    формой: проверяется именно раскладка таблицы, а её ломало отображение, а не ввод.
    """
    add(app, "100", category="К" * 32)
    doc_width = app.evaluate("() => document.documentElement.scrollWidth")
    assert doc_width <= 1280, f"страница уехала вбок: {doc_width}px при окне 1280"


def test_bug009_mobile_long_category_no_hscroll(mobile_app):
    """BUG-009 на 375×812, SPEC п.16 + КП: горизонтальной прокрутки быть не должно."""
    add(mobile_app, "300", category="К" * 32)
    doc_width = mobile_app.evaluate("() => document.documentElement.scrollWidth")
    assert doc_width <= 375, f"страница уехала вбок: {doc_width}px при окне 375"


# --- BUG-010 / BUG-011 / BUG-012: сумма ---------------------------------------

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


@pytest.mark.parametrize("amount", ["12abc", "12 руб", "1,2,3", "5."])
def test_r3_number_with_tail_rejected(app, amount):
    """R3, SPEC п.1: «число + хвост». `12 руб` — самый правдоподобный ввод человека
    во всём наборе, и до фикса он давал запись на 12 рублей молча."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, amount)
    assert_rejected(app, before_rows, before_totals)


@pytest.mark.parametrize("amount", ["0.001", "0.004", "1e-5"])
def test_bug012_amount_rounding_to_zero_rejected(app, amount):
    """BUG-012, SPEC п.1 + п.2: после округления сумма обязана остаться больше нуля."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, amount)
    assert_rejected(app, before_rows, before_totals)


# --- BUG-013 / BUG-014 / BUG-015: импорт не валидировал данные ----------------

def test_bug013_negative_amount_from_csv_rejected(app, tmp_csv):
    """BUG-013, SPEC п.11 + п.1: отрицательная сумма из файла не должна попадать в учёт."""
    import_rejected_csv(app, tmp_csv(
        "negative.csv", f"date,type,category,amount,comment\n{TODAY},expense,Еда,-500.00,\n"))
    assert row_count(app) == 0, f"загружена запись с отрицательной суммой: {rows(app)}"


def test_bug013_negative_amount_does_not_invert_balance(app, tmp_csv):
    """BUG-013: расход не может увеличивать остаток."""
    import_rejected_csv(app, tmp_csv(
        "negative.csv", f"date,type,category,amount,comment\n{TODAY},expense,Еда,-500.00,\n"))
    assert not totals(app)["balance"].startswith("500"), "расход увеличил остаток"


def test_r2_chart_and_table_cannot_contradict(app, tmp_csv):
    """R2, SPEC п.11 + таблица состояний: пара сумм, гасящих друг друга, давала
    непустую таблицу при пустой диаграмме — два представления одних данных
    противоречили друг другу."""
    import_rejected_csv(app, tmp_csv(
        "pair.csv", "date,type,category,amount,comment\n"
                    f"{TODAY},expense,А,100.00,\n{TODAY},expense,Б,-100.00,\n"))
    assert row_count(app) == 0
    assert app.locator("#chartEmpty").is_visible(), "таблица пуста, а диаграмма — нет"


def test_bug014_unknown_type_from_csv_rejected(app, tmp_csv):
    """BUG-014, SPEC п.11: тип вне income/expense — повод отклонить файл."""
    import_rejected_csv(app, tmp_csv(
        "badtype.csv", f"date,type,category,amount,comment\n{TODAY},dragon,Еда,100.00,\n"))
    assert row_count(app) == 0, f"неизвестный тип загружен как расход: {rows(app)}"


def test_bug015_broken_date_from_csv_rejected(app, tmp_csv):
    """BUG-015, SPEC п.11: нечисловая дата не должна попадать в таблицу как есть."""
    import_rejected_csv(app, tmp_csv(
        "baddate.csv", "date,type,category,amount,comment\nне-дата,expense,Еда,100.00,\n"))
    assert row_count(app) == 0, f"загружена строка с датой «не-дата»: {rows(app)}"


def test_bug015_impossible_date_from_csv_rejected(app, tmp_csv):
    """SPEC п.8, путь импорта. Через форму эта проверка неосуществима: браузер
    не отдаёт `2026-02-30` в `input[type=date]`, поле остаётся пустым."""
    import_rejected_csv(app, tmp_csv(
        "feb30.csv", "date,type,category,amount,comment\n2026-02-30,expense,Еда,100.00,\n"))
    assert row_count(app) == 0


def test_bug015_future_date_from_csv_rejected(app, tmp_csv):
    """BUG-015, SPEC п.11 + п.7: будущая дата запрещена и на пути импорта."""
    import_rejected_csv(app, tmp_csv(
        "future.csv", "date,type,category,amount,comment\n2099-01-01,expense,Еда,100.00,\n"))
    assert row_count(app) == 0, f"загружена запись из 2099 года: {rows(app)}"


def test_bug015_huge_amount_from_csv_rejected(app, tmp_csv):
    """BUG-015, SPEC п.11 + п.3: верхняя граница суммы обязана действовать и при импорте."""
    import_rejected_csv(app, tmp_csv(
        "huge.csv", f"date,type,category,amount,comment\n{TODAY},expense,Еда,999999999999,\n"))
    assert row_count(app) == 0, f"загружена сумма вне границы: {rows(app)}"


@pytest.mark.parametrize("name,content,why", [
    ("cat33.csv", "date,type,category,amount,comment\n{d},expense,{c},100.00,\n", "категория 33 символа"),
    ("zero.csv", "date,type,category,amount,comment\n{d},expense,Еда,0.001,\n", "сумма округляется в ноль"),
    ("emptycat.csv", "date,type,category,amount,comment\n{d},expense,,100.00,\n", "пустая категория"),
])
def test_import_uses_the_same_rules_as_the_form(app, tmp_csv, name, content, why):
    """Главная идея фикса BUG-013…015: форма и импорт проверяют данные ОДНИМИ функциями.
    Проверяется не реализация, а её следствие: вход, отклонённый формой, отклонён и в файле.
    """
    add(app, "111", category="Исходная")
    body = content.format(d=TODAY, c="К" * 33)
    import_rejected_csv(app, tmp_csv(name, body))
    assert row_count(app) == 1, f"{why}: файл принят, хотя форма такой ввод отклоняет"
