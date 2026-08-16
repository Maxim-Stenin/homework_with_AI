"""Ширина 375×812 (SPEC п.16). Находки этой области помечены явно как мобильные."""
from helpers import add, row_count, rows


def test_main_scenario_without_horizontal_scroll(mobile_app):
    add(mobile_app, "1500.75", category="Продукты", comment="магазин у дома")
    add(mobile_app, "40000", category="З/п", kind="income")
    assert row_count(mobile_app) == 2
    assert mobile_app.evaluate("() => document.documentElement.scrollWidth") == 375


def test_table_is_readable_on_mobile(mobile_app):
    add(mobile_app, "1500.75", category="Продукты", comment="магазин у дома")
    assert "Продукты" in rows(mobile_app)[0]
    assert mobile_app.locator("#donut").is_visible()


def test_form_and_totals_visible_on_mobile(mobile_app):
    assert mobile_app.locator("#fAmount").is_visible()
    assert mobile_app.locator("#sumBalance").is_visible()
    assert mobile_app.locator("#addForm button[type=submit]").is_visible()


def test_chart_and_legend_visible_on_mobile(mobile_app):
    add(mobile_app, "300", category="Еда")
    assert mobile_app.locator("#legend li").count() == 1
    assert mobile_app.locator("#donut").is_visible()
