"""Загрузка CSV — работающая часть. Провалы валидации — в test_defects.py."""
from helpers import add, row_count, rows, totals

GOOD = ("date,type,category,amount,comment\n"
        "2026-08-16,expense,Еда,100.00,обед\n"
        "2026-08-16,income,З/п,200.00,аванс\n")


def test_valid_csv_is_loaded(app, tmp_csv):
    app.set_input_files("#fileInput", tmp_csv("good.csv", GOOD))
    app.wait_for_selector("#tbody tr")
    assert row_count(app) == 2
    assert any("Еда" in r for r in rows(app))


def test_totals_match_loaded_rows(app, tmp_csv):
    app.set_input_files("#fileInput", tmp_csv("good.csv", GOOD))
    app.wait_for_selector("#tbody tr")
    t = totals(app)
    assert t["income"].startswith("200")
    assert t["expense"].startswith("100")


def test_crlf_line_endings_are_supported(app, tmp_csv):
    content = GOOD.replace("\n", "\r\n")
    app.set_input_files("#fileInput", tmp_csv("crlf.csv", content))
    app.wait_for_selector("#tbody tr")
    assert row_count(app) == 2


def test_quoted_values_survive_import(app, tmp_csv):
    content = ('date,type,category,amount,comment\n'
               '2026-08-16,expense,"Ка,фе",100.50,"он сказал ""привет"""\n')
    app.set_input_files("#fileInput", tmp_csv("quoted.csv", content))
    app.wait_for_selector("#tbody tr")
    assert "Ка,фе" in rows(app)[0]
    assert 'он сказал "привет"' in rows(app)[0]


def test_reimport_replaces_and_does_not_duplicate(app, tmp_csv):
    path = tmp_csv("good.csv", GOOD)
    app.set_input_files("#fileInput", path)
    app.wait_for_selector("#tbody tr")
    app.set_input_files("#fileInput", path)
    app.wait_for_timeout(200)
    assert row_count(app) == 2, "повторная загрузка того же файла продублировала записи"


def test_extra_column_is_ignored(app, tmp_csv):
    content = ("date,type,category,amount,comment,extra\n"
               "2026-08-16,expense,Еда,100.00,,мусор\n")
    app.set_input_files("#fileInput", tmp_csv("extra.csv", content))
    app.wait_for_selector("#tbody tr")
    assert row_count(app) == 1


def test_import_updates_chart(app, tmp_csv):
    from helpers import legend
    app.set_input_files("#fileInput", tmp_csv("good.csv", GOOD))
    app.wait_for_selector("#tbody tr")
    assert any("Еда" in item for item in legend(app))


def test_manual_row_then_import_replaces_it(app, tmp_csv):
    """Замена списка целиком — ожидаемая часть SPEC п.10; спорна только внезапность."""
    add(app, "777", category="Своё")
    app.set_input_files("#fileInput", tmp_csv("good.csv", GOOD))
    app.wait_for_timeout(200)
    assert all("Своё" not in r for r in rows(app))
