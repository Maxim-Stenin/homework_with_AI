"""Цикл «сохранить → загрузить» на грязных значениях (SPEC п.12, КП)."""
from helpers import add, rows, totals

DATA = [
    ("1200.50", "Ка,фе", "expense", 'кофе "тройной"'),
    ("40000", "З/п", "income", "аванс, первая часть"),
    ("99999999", "Ипотека", "expense", ""),
    ("0.01", "Мелочь", "expense", "копейка"),
    ("15.99", 'Кино"IMAX"', "expense", "билет"),
    ("500", "Подарки", "income", "день рождения"),
]


def test_roundtrip_returns_set_verbatim(app, tmp_path):
    for amount, category, kind, comment in DATA:
        add(app, amount, category=category, kind=kind, comment=comment)
    before = rows(app)
    totals_before = totals(app)

    with app.expect_download() as info:
        app.click("#btnSave")
    path = tmp_path / "roundtrip.csv"
    info.value.save_as(str(path))

    app.evaluate("localStorage.clear()")
    app.reload()
    assert rows(app) == []

    app.set_input_files("#fileInput", str(path))
    app.wait_for_selector("#tbody tr")

    assert rows(app) == before, "набор вернулся не дословно"
    assert totals(app) == totals_before


def test_roundtrip_keeps_empty_list_empty(app, tmp_path):
    with app.expect_download() as info:
        app.click("#btnSave")
    path = tmp_path / "empty.csv"
    info.value.save_as(str(path))
    app.set_input_files("#fileInput", str(path))
    app.wait_for_timeout(200)
    assert rows(app) == []
