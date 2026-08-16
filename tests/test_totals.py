"""Арифметика итогов и инварианты данных."""
import pytest

from helpers import add, legend, money_to_float, row_count, rows, totals


def test_empty_state_shows_zeros(app):
    t = totals(app)
    assert t["income"].startswith("0,00")
    assert t["expense"].startswith("0,00")
    assert t["balance"].startswith("0,00")


def test_balance_is_income_minus_expense(app):
    add(app, "100", category="З/п", kind="income")
    add(app, "150.55", category="Еда")
    t = totals(app)
    assert money_to_float(t["balance"]) == pytest.approx(
        money_to_float(t["income"]) - money_to_float(t["expense"]), abs=0.005)
    assert money_to_float(t["balance"]) == pytest.approx(-50.55, abs=0.005)


def test_negative_balance_is_visually_distinct(app):
    add(app, "100", category="Еда")
    assert "neg" in app.locator("#sumBalance").get_attribute("class")
    add(app, "1000", category="З/п", kind="income")
    assert "neg" not in app.locator("#sumBalance").get_attribute("class")


def test_rounding_does_not_accumulate(app):
    """Три записи по 0.33 обязаны дать ровно 0,99, а не 0,98999…"""
    for _ in range(3):
        add(app, "0.33", category="Мелочь")
    assert money_to_float(totals(app)["expense"]) == pytest.approx(0.99, abs=0.005)


def test_invariant_rows_sum_equals_totals(app):
    """Инвариант: сумма строк таблицы = итог. Ловит дефекты, на которые нет отдельного теста."""
    add(app, "1200.50", category="Продукты")
    add(app, "300.25", category="Кафе")
    add(app, "40000", category="З/п", kind="income")
    expenses = sum(money_to_float(r.split("\t")[-2]) for r in rows(app) if "−" in r)
    assert abs(expenses) == pytest.approx(money_to_float(totals(app)["expense"]), abs=0.02)


def test_totals_recalculated_after_delete(app):
    add(app, "100", category="Еда")
    add(app, "200", category="Дом")
    app.click("#tbody tr:first-child button")
    assert money_to_float(totals(app)["expense"]) == pytest.approx(
        sum(abs(money_to_float(r.split("\t")[-2])) for r in rows(app)), abs=0.02)


def test_limit_amount_does_not_break_totals_layout(app):
    """SPEC КП: вёрстка итогов цела на 99 999 999."""
    add(app, "99999999", category="Еда")
    overflow = app.evaluate(
        "() => {const e = document.querySelector('#sumExpense'); return e.scrollWidth > e.clientWidth;}")
    assert overflow is False
    assert app.evaluate("() => document.documentElement.scrollWidth") == 1280


def test_legend_shares_sum_to_100(app):
    for i in range(30):
        add(app, str(i + 1), category=f"Кат{i:02d}")
    shares = [int(item.split("/")[-1].strip().rstrip("%")) for item in legend(app)]
    assert sum(shares) == 100
    assert len(shares) == 30


def test_row_count_changes_by_one(app):
    before = row_count(app)
    add(app, "10", category="Раз")
    assert row_count(app) == before + 1
