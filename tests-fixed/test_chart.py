"""Диаграмма, легенда и пустые состояния.

Против `tests/test_chart.py` изменено:
- удаление строки идёт через `delete_row()`: в фиксе оно спрашивает подтверждение,
  и без явного согласия строка остаётся (SPEC п.13);
- порог в `test_center_label_fits_the_ring` пересчитан. Старый `assert width < 120`
  разобран в `review/results.md`, E3: он взят чуть выше наблюдённых 113 px, то есть
  подогнан под факт. Требование — подпись внутри ОТВЕРСТИЯ кольца, а его диаметр
  считается из геометрии: 2 × r − stroke = 2 × 70 − 34 = 106 px. Порог теперь берётся
  из разметки, а не из памяти о прошлом прогоне.
"""
from helpers import add, delete_row, legend

INNER_DIAMETER = 106   # 2 × 70 − 34, посчитано по атрибутам SVG, проверяется тестом ниже


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
    delete_row(app)
    assert legend(app) == []
    assert app.locator("#chartEmpty").is_visible()
    assert app.locator("#donut *").count() == 0


def test_ring_geometry_is_what_the_threshold_assumes(app):
    """Порог соседнего теста обязан выводиться из разметки, а не из наблюдения.

    Если фикс когда-нибудь изменит радиус или толщину кольца, упадёт этот тест —
    и станет видно, что порог протух, вместо того чтобы молча начать врать.
    """
    add(app, "100", category="Еда")
    r = float(app.get_attribute("#donut circle", "r"))
    stroke = float(app.evaluate(
        "() => getComputedStyle(document.querySelector('#donut circle')).strokeWidth.replace('px','')"))
    assert 2 * r - stroke == INNER_DIAMETER, f"геометрия кольца изменилась: r={r}, stroke={stroke}"


def test_center_label_fits_the_ring(app):
    """R4 / E3: подпись обязана помещаться в отверстие кольца, а не в его внешний габарит."""
    add(app, "99999999", category="Еда")
    width = app.evaluate("() => document.querySelector('#donut text').getBBox().width")
    assert width <= INNER_DIAMETER, (
        f"подпись {width:.1f}px шире отверстия {INNER_DIAMETER}px — текст лежит на кольце")


def test_table_empty_hint_after_deleting_everything(app):
    add(app, "10", category="Раз")
    delete_row(app)
    assert app.locator("#tableEmpty").is_visible()
    assert "Записей пока нет" in app.locator("#tableEmpty").inner_text()
