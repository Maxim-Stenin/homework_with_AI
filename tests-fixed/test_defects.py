"""Дефекты, найденные на ИСПРАВЛЕННОЙ копии. ЭТИ ТЕСТЫ ОБЯЗАНЫ ПАДАТЬ.

Красный прогон здесь — требуемый результат и доказательство находки, а не поломка.
`xfail` не используется намеренно: он превратил бы красное в жёлтое и спрятал ровно то,
что сдаётся. Каждый тест сослан на номер RT-BUG-NNN из `retest-run/bugs.md`
и на пункт `SPEC.md`.

Если какой-то из этих тестов позеленел — значит объект изменили. Чинится тест
или уточняется ожидание, но НИКОГДА не объект: `app-fixed/index_refactor.html`
заморожен так же, как `app/index.html` (AGENTS.md).
"""
import pytest

from conftest import TODAY
from helpers import add, assert_rejected, import_csv, row_count, rows, totals


# --- RT-BUG-001: пробел внутри суммы вырезается до проверки -------------------

@pytest.mark.parametrize("amount,label", [
    ("1 2 0 0", "пробел между каждой цифрой"),
    ("1\t200", "табуляция внутри числа"),
    ("1 200", "неразрывный пробел внутри числа"),
    ("1 200.50", "пробел внутри дробного числа"),
])
def test_rtbug001_whitespace_inside_amount_rejected(app, amount, label):
    """RT-BUG-001, SPEC п.1: сумма — «обычная запись числа и ничего кроме».

    Фикс BUG-011 поставил белый список `^(0|[1-9]\\d*)([.,]\\d+)?$` — и тем закрыл
    `1e5`, `12abc`, `1_000`. Но перед проверкой сумма проходит `.replace(/\\s/g, '')`,
    то есть пробельные символы вырезаются ДО белого списка и до него не доходят.
    Белый список обойдён ровно тем же способом, каким его обходил `parseFloat`.
    """
    before_rows, before_totals = row_count(app), totals(app)
    add(app, amount)
    assert_rejected(app, before_rows, before_totals)


def test_rtbug001_whitespace_amount_is_not_silently_reinterpreted(app):
    """Худшее последствие: ввод не отвергается, а тихо превращается в другое число.
    Человек напечатал `1 2 0 0` (опечатка) — приложение записало 1 200,00 ₽ без слова."""
    add(app, "1 2 0 0", category="Опечатка")
    assert row_count(app) == 0, f"ввод молча переосмыслен: {rows(app)}"


def test_rtbug001_whitespace_amount_from_csv_rejected(app, tmp_csv):
    """Тот же вход по пути импорта: форма и файл валидируются одними функциями,
    поэтому дефект наследуется и там (SPEC п.11)."""
    import_csv(app, tmp_csv(
        "space.csv", f'date,type,category,amount,comment\n{TODAY},expense,Еда,"1 2 0 0",\n'))
    assert row_count(app) == 0, f"файл с суммой «1 2 0 0» принят: {rows(app)}"


# --- RT-BUG-002: две точки подряд в сообщении об ошибке импорта ---------------

def test_rtbug002_import_error_has_no_double_period(app, tmp_csv):
    """RT-BUG-002, SPEC КП (сообщения об ошибках понятны).

    Сообщение собирается как `'Файл не загружен: ' + error + '. Список не изменён.'`,
    а `error` уже заканчивается точкой. Получается «…например 1200 или 1200.50..».
    Косметика, но она на самом видном месте — в единственном сообщении, которое
    пользователь читает в момент потери данных.
    """
    add(app, "111", category="Исходная")
    app.on("dialog", lambda d: d.dismiss())
    app.set_input_files("#fileInput", tmp_csv(
        "bad.csv", f"date,type,category,amount,comment\n{TODAY},expense,Еда,abc,\n"))
    app.wait_for_selector("#formError:not(:empty)")
    text = app.locator("#formError").inner_text()
    assert ".." not in text, f"две точки подряд в сообщении: {text!r}"
