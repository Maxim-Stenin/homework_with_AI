"""Диаграмма, легенда и пустые состояния."""
from helpers import add, legend


def test_empty_chart_shows_hint(app):
    assert app.locator("#chartEmpty").is_visible()
    assert "добавьте запись" in app.locator("#chartEmpty").inner_text()
    assert legend(app) == []


def test_single_category_is_100_percent(app):
    add(app, "1500.75", category="Продукты")
    assert len(legend(app)) == 1
    assert "100%" in legend(app)[0].replace(" ", "")


def test_legend_shows_name_amount_and_share(app):
    add(app, "300", category="Продукты")
    add(app, "100", category="Кафе")
    first = legend(app)[0]
    assert "Продукты" in first and "₽" in first and "%" in first


def test_income_tab_switches_dataset(app):
    add(app, "100", category="Еда")
    add(app, "500", category="З/п", kind="income")
    app.click("#tabIncome")
    assert any("З/п" in item for item in legend(app))
    app.click("#tabExpense")
    assert any("Еда" in item for item in legend(app))


def test_expense_tab_empty_when_only_income(app):
    add(app, "500", category="З/п", kind="income")
    app.click("#tabExpense")
    assert legend(app) == []
    assert app.locator("#chartEmpty").is_visible()


def test_chart_returns_to_empty_after_deleting_last_row(app):
    add(app, "100", category="Еда")
    app.click("#tbody tr:first-child button")
    assert legend(app) == []
    assert app.locator("#chartEmpty").is_visible()
    assert app.locator("#donut *").count() == 0


def test_center_label_fits_the_ring(app):
    """Текст в центре кольца не должен вылезать за него на предельной сумме."""
    add(app, "99999999", category="Еда")
    width = app.evaluate("() => document.querySelector('#donut text').getBBox().width")
    assert width < 120


def test_table_empty_hint_after_deleting_everything(app):
    add(app, "10", category="Раз")
    app.click("#tbody tr:first-child button")
    assert app.locator("#tableEmpty").is_visible()
    assert "Записей пока нет" in app.locator("#tableEmpty").inner_text()
