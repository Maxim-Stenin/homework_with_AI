"""Цикл «сохранить → загрузить» на грязных значениях (SPEC п.12, КП).

Против `tests/test_roundtrip.py` изменено:
- загрузка идёт через `import_csv()` с подтверждением;
- `test_roundtrip_keeps_empty_list_empty` переписан. В старом виде он проверял
  «после загрузки пустого файла строк нет» — и на исправленной копии проходил
  БЕЗ ВСЯКОЙ ЗАГРУЗКИ: Playwright отклонял подтверждение, файл не применялся,
  таблица оставалась пустой, тест зеленел. Зелёный тест, ничего не проверивший,
  хуже отсутствующего, поэтому проверка перестроена: сначала в таблице есть запись,
  и только загрузка пустого файла обязана её убрать.
"""
from helpers import add, import_csv, rows, totals

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

    import_csv(app, str(path))
    app.wait_for_selector("#tbody tr")

    assert rows(app) == before, "набор вернулся не дословно"
    assert totals(app) == totals_before


def test_roundtrip_keeps_empty_list_empty(app, tmp_path):
    """Выгрузка пустого списка обязана быть загружаемой обратно (обратимость)."""
    with app.expect_download() as info:
        app.click("#btnSave")
    path = tmp_path / "empty.csv"
    info.value.save_as(str(path))

    add(app, "100", category="Помеха")
    assert len(rows(app)) == 1, "предусловие теста не выполнено"

    import_csv(app, str(path))
    assert rows(app) == [], "выгрузка пустого списка не загружается обратно как пустой список"


def test_roundtrip_survives_long_comment(app, tmp_path):
    """Комментарий на 500 символов — тот самый вход, что раньше рвал вёрстку (E1)."""
    add(app, "100", category="Еда", comment="Я" * 500)
    before = rows(app)
    with app.expect_download() as info:
        app.click("#btnSave")
    path = tmp_path / "long.csv"
    info.value.save_as(str(path))
    app.evaluate("localStorage.clear()")
    app.reload()
    import_csv(app, str(path))
    app.wait_for_selector("#tbody tr")
    assert rows(app) == before
    assert app.evaluate("() => document.documentElement.scrollWidth") <= 1280
