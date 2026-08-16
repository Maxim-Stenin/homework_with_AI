"""Селекторы и действия в одном месте.

Селекторы построены по РАЗМЕТКЕ, КОТОРАЯ ЕСТЬ. Дописывать в объект `data-testid`
запрещено (AGENTS.md), поэтому используются существующие id и текст кнопок.
Неудобство разметки записано замечанием NOTE-05 в qa/bugs.md, а не «починено».
"""
from conftest import TODAY

SEL = {
    "type": "#fType",
    "amount": "#fAmount",
    "category": "#fCategory",
    "date": "#fDate",
    "comment": "#fComment",
    "submit": "#addForm button[type=submit]",
    "error": "#formError",
    "rows": "#tbody tr",
    "income": "#sumIncome",
    "expense": "#sumExpense",
    "balance": "#sumBalance",
    "legend": "#legend li",
    "chart_empty": "#chartEmpty",
    "table_empty": "#tableEmpty",
    "save": "#btnSave",
    "file": "#fileInput",
    "tab_expense": "#tabExpense",
    "tab_income": "#tabIncome",
}


def add(page, amount, category="Кафе", date=None, kind="expense", comment=""):
    """Заполнить форму и отправить. Дата по умолчанию — сегодня, считается, а не константа."""
    page.select_option(SEL["type"], kind)
    page.fill(SEL["amount"], amount)
    page.fill(SEL["category"], category)
    set_date(page, date if date is not None else TODAY.isoformat())
    page.fill(SEL["comment"], comment)
    page.click(SEL["submit"])


def set_date(page, iso):
    """input[type=date] заполняется значением, а не набором текста: раскладка не влияет."""
    page.evaluate("d => document.querySelector('#fDate').value = d", iso)


def row_count(page):
    return page.locator(SEL["rows"]).count()


def rows(page):
    return page.locator(SEL["rows"]).all_inner_texts()


def error_text(page):
    return page.locator(SEL["error"]).inner_text()


def totals(page):
    return {
        "income": page.locator(SEL["income"]).inner_text(),
        "expense": page.locator(SEL["expense"]).inner_text(),
        "balance": page.locator(SEL["balance"]).inner_text(),
    }


def legend(page):
    return [t.replace("\n", " / ") for t in page.locator(SEL["legend"]).all_inner_texts()]


def money_to_float(text):
    """'1 200,50 ₽' -> 1200.5 . Неразрывные пробелы и запятая — часть форматирования."""
    cleaned = (text.replace(" ", "").replace(" ", "")
               .replace("₽", "").replace("−", "-").replace(",", "."))
    return float(cleaned)


def storage(page):
    return page.evaluate("() => localStorage.getItem('finance.csv')")


def assert_rejected(page, rows_before, totals_before):
    """Проверка отказа состоит из трёх частей, и первые две обязательны."""
    assert row_count(page) == rows_before, "появилась строка, хотя форма должна была отказать"
    assert totals(page) == totals_before, "итоги изменились, хотя форма должна была отказать"
    assert error_text(page).strip(), "нет сообщения об ошибке"
