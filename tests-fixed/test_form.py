"""Валидация формы на исправленной копии.

Против `tests/test_form.py` изменено:
- ничего не ослаблено: все прежние ожидания остались как были и остались зелёными;
- добавлены пары к границам, которых в старом наборе не было (32/33 символа стояли
  в разных файлах, теперь рядом; `99999999`/`100000000` — тоже);
- добавлен класс входов «число + мусор» (R3): в старом наборе он существовал только
  как дефект, теперь это обычная негативная проверка.
Дефекты, найденные на самом фиксе, лежат в `test_defects.py` и падают.
"""
import pytest

from conftest import TODAY, YESTERDAY
from helpers import NBSP, add, assert_rejected, error_text, row_count, rows, totals

# --- позитивные: суммы, которые обязаны проходить -----------------------------

@pytest.mark.parametrize("amount,shown", [
    ("5", "5,00"),
    ("1200.50", "1 200,50"),
    ("12.5", "12,50"),
    ("1,5", "1,50"),
    ("10,50", "10,50"),
    ("  100  ", "100,00"),
    ("99999999", "99 999 999,00"),   # последнее проходящее по SPEC п.3
])
def test_amount_accepted(app, amount, shown):
    add(app, amount)
    assert row_count(app) == 1
    assert shown.replace(" ", NBSP) in rows(app)[0]


# --- негативные: отказ должен быть отказом, а не только сообщением -------------

@pytest.mark.parametrize("amount", [
    "", "   ", "0", "-100", "abc", "٣", "Infinity", "1e309",
    # ниже — то, что до фикса принималось (BUG-011, BUG-012, R3).
    "1e5", "1e2", "1_000", "1..2", "+50", ".5", "007",
    "12abc", "12 руб", "1,2,3", "5.", "0x10",
    "0.001", "0.004", "1e-5",
])
def test_amount_rejected(app, amount):
    before_rows, before_totals = row_count(app), totals(app)
    add(app, amount)
    assert_rejected(app, before_rows, before_totals)


def test_rejected_form_keeps_entered_values(app):
    """Состояние «Ошибка ввода»: ранее введённые поля не сбрасываются."""
    add(app, "abc", category="Подарок", kind="income", comment="коммент")
    assert app.input_value("#fAmount") == "abc"
    assert app.input_value("#fCategory") == "Подарок"
    assert app.input_value("#fComment") == "коммент"
    assert app.input_value("#fType") == "income"


def test_error_message_is_visible(app):
    add(app, "0")
    assert "больше нуля" in error_text(app)


def test_error_message_names_the_format(app):
    """Отказ по формату обязан объяснять формат, а не просто ругаться (SPEC КП)."""
    add(app, "abc")
    assert "цифрами" in error_text(app)


# --- границы суммы парами (SPEC п.3) ------------------------------------------

@pytest.mark.parametrize("amount,accepted", [
    ("99999999", True),     # последнее проходящее
    ("100000000", False),   # первое отклоняемое
    ("0.01", True),         # последнее проходящее снизу
    ("0.004", False),       # первое отклоняемое снизу: округляется в ноль
])
def test_amount_boundaries(app, amount, accepted):
    before_rows, before_totals = row_count(app), totals(app)
    add(app, amount)
    if accepted:
        assert row_count(app) == before_rows + 1, f"{amount} обязана проходить"
    else:
        assert_rejected(app, before_rows, before_totals)


# --- округление до двух знаков (SPEC п.2) -------------------------------------

@pytest.mark.parametrize("amount,shown", [
    ("10.567", "10,57"),
    ("0.005", "0,01"),
    ("1.005", "1,00"),
])
def test_amount_rounding(app, amount, shown):
    add(app, amount)
    assert shown in rows(app)[0]


# --- категория ----------------------------------------------------------------

@pytest.mark.parametrize("category", ["Кафе", "Кафе 🍔", "Ка,фе", 'Ка"фе', "К" * 32])
def test_category_accepted(app, category):
    add(app, "100", category=category)
    assert row_count(app) == 1
    assert category in rows(app)[0]


@pytest.mark.parametrize("length,accepted", [(32, True), (33, False)])
def test_category_length_boundary(app, length, accepted):
    """SPEC п.6, граница парой значений в одном месте."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, "100", category="К" * length)
    if accepted:
        assert row_count(app) == before_rows + 1
    else:
        assert_rejected(app, before_rows, before_totals)


def test_category_trims_spaces(app):
    """SPEC п.4."""
    add(app, "100", category="   кафе   ")
    assert "кафе" in rows(app)[0]
    assert "   кафе" not in rows(app)[0]


def test_same_category_twice_merges(app):
    from helpers import legend
    add(app, "100", category="Кафе")
    add(app, "100", category="Кафе")
    assert len(legend(app)) == 1
    assert "200,00" in legend(app)[0]


def test_markup_in_category_is_not_executed(app):
    add(app, "100", category="<b>x</b>")
    assert "<b>x</b>" in rows(app)[0]
    assert app.locator("#tbody b").count() == 0


def test_datalist_suggests_used_categories(app):
    add(app, "100", category="Кафе")
    add(app, "100", category="Продукты")
    options = app.eval_on_selector_all("#catList option", "els => els.map(e => e.value)")
    assert set(options) == {"Кафе", "Продукты"}


# --- дата ---------------------------------------------------------------------

def test_date_prefilled_with_today(app):
    assert app.input_value("#fDate") == TODAY.isoformat()


def test_date_input_has_max_of_today(app):
    """Фикс BUG-005 закрыл будущее и на уровне календаря, а не только проверкой."""
    assert app.get_attribute("#fDate", "max") == TODAY.isoformat()


@pytest.mark.parametrize("date", [YESTERDAY.isoformat(), TODAY.isoformat(), "1999-01-01"])
def test_past_and_today_accepted(app, date):
    add(app, "100", date=date)
    assert row_count(app) == 1


def test_empty_date_is_rejected(app):
    """SPEC п.8."""
    before_rows, before_totals = row_count(app), totals(app)
    add(app, "100", category="БезДаты", date="")
    assert_rejected(app, before_rows, before_totals)
    assert "дату" in error_text(app)


# --- тип записи и комментарий -------------------------------------------------

def test_income_is_added_with_plus(app):
    add(app, "40000", category="З/п", kind="income")
    assert "+" in rows(app)[0]
    assert totals(app)["income"].startswith("40")


def test_expense_is_default_type(app):
    assert app.input_value("#fType") == "expense"


def test_comment_is_optional(app):
    add(app, "100", comment="")
    assert row_count(app) == 1


def test_long_comment_is_kept(app):
    add(app, "100", comment="Я" * 500)
    assert "Я" * 500 in rows(app)[0]


def test_long_comment_does_not_break_layout(app):
    """E1 из review/results.md: раньше 500 символов комментария давали scrollWidth 4910
    при окне 1280, и старый тест этого не замечал — он смотрел только на текст."""
    add(app, "100", comment="Я" * 500)
    width = app.evaluate("() => document.documentElement.scrollWidth")
    assert width <= 1280, f"страница уехала вбок: {width}px при окне 1280"


def test_form_is_cleared_after_success(app):
    add(app, "50", category="Дубль")
    assert app.input_value("#fAmount") == ""
    assert app.input_value("#fCategory") == ""


def test_second_submit_on_empty_form_adds_nothing(app):
    add(app, "50", category="Дубль")
    app.click("#addForm button[type=submit]")
    assert row_count(app) == 1
