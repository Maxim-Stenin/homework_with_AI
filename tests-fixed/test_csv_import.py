"""Загрузка CSV на исправленной копии.

Против `tests/test_csv_import.py` изменено главное: каждая загрузка теперь проходит
через `confirm()` (SPEC п.10, фикс BUG-001). Старые тесты этого не знали, Playwright
по умолчанию диалог отклонял, файл не применялся — и восемь тестов падали по таймауту
`wait_for_selector("#tbody tr")`. Это было устаревание тестов, а не провал фикса:
разбор — `retest-run/README.md`, раздел «Разделение падений».

Ожидания при этом не смягчены. Наоборот, к каждому «файл загрузился» добавилось
«и подтверждение было запрошено», а отказ от подтверждения проверяется отдельно.
"""
from helpers import add, import_csv, import_rejected_csv, legend, row_count, rows, totals

GOOD = ("date,type,category,amount,comment\n"
        "2026-08-16,expense,Еда,100.00,обед\n"
        "2026-08-16,income,З/п,200.00,аванс\n")


def test_valid_csv_is_loaded(app, tmp_csv):
    import_csv(app, tmp_csv("good.csv", GOOD))
    app.wait_for_selector("#tbody tr")
    assert row_count(app) == 2
    assert any("Еда" in r for r in rows(app))


def test_import_asks_before_replacing(app, tmp_csv):
    """SPEC п.10: замена списка — потеря данных, она идёт через подтверждение."""
    add(app, "1200.50", category="Продукты")
    message = import_csv(app, tmp_csv("good.csv", GOOD))
    assert "Продолжить" in message
    assert "2" in message, f"в вопросе не названо, сколько записей придёт: {message!r}"


def test_cancelled_import_keeps_current_list(app, tmp_csv):
    """Отказ обязан не изменить НИЧЕГО, а не «примерно ничего»."""
    add(app, "1200.50", category="Продукты")
    before, before_totals = rows(app), totals(app)
    import_csv(app, tmp_csv("good.csv", GOOD), confirm=False)
    assert rows(app) == before, "список изменился после отказа от загрузки"
    assert totals(app) == before_totals, "итоги изменились после отказа от загрузки"
    assert "отменена" in app.locator("#formError").inner_text()


def test_totals_match_loaded_rows(app, tmp_csv):
    import_csv(app, tmp_csv("good.csv", GOOD))
    app.wait_for_selector("#tbody tr")
    t = totals(app)
    assert t["income"].startswith("200")
    assert t["expense"].startswith("100")


def test_crlf_line_endings_are_supported(app, tmp_csv):
    import_csv(app, tmp_csv("crlf.csv", GOOD.replace("\n", "\r\n")))
    app.wait_for_selector("#tbody tr")
    assert row_count(app) == 2


def test_quoted_values_survive_import(app, tmp_csv):
    content = ('date,type,category,amount,comment\n'
               '2026-08-16,expense,"Ка,фе",100.50,"он сказал ""привет"""\n')
    import_csv(app, tmp_csv("quoted.csv", content))
    app.wait_for_selector("#tbody tr")
    assert "Ка,фе" in rows(app)[0]
    assert 'он сказал "привет"' in rows(app)[0]


def test_reimport_replaces_and_does_not_duplicate(app, tmp_csv):
    path = tmp_csv("good.csv", GOOD)
    import_csv(app, path)
    app.wait_for_selector("#tbody tr")
    import_csv(app, path)
    assert row_count(app) == 2, "повторная загрузка того же файла продублировала записи"


def test_extra_column_is_ignored(app, tmp_csv):
    content = ("date,type,category,amount,comment,extra\n"
               "2026-08-16,expense,Еда,100.00,,мусор\n")
    import_csv(app, tmp_csv("extra.csv", content))
    app.wait_for_selector("#tbody tr")
    assert row_count(app) == 1


def test_import_updates_chart(app, tmp_csv):
    import_csv(app, tmp_csv("good.csv", GOOD))
    app.wait_for_selector("#tbody tr")
    assert any("Еда" in item for item in legend(app))


def test_manual_row_then_import_replaces_it(app, tmp_csv):
    """Замена списка целиком — ожидаемая часть SPEC п.10, но только после согласия."""
    add(app, "777", category="Своё")
    import_csv(app, tmp_csv("good.csv", GOOD))
    app.wait_for_selector("#tbody tr")
    assert all("Своё" not in r for r in rows(app))


def test_header_only_file_empties_the_list(app, tmp_csv):
    """Файл из одной шапки — законный «пустой список», а не битый файл:
    именно такой файл отдаёт выгрузка при пустой таблице (обратимость, SPEC п.12)."""
    add(app, "100", category="Еда")
    import_csv(app, tmp_csv("onlyheader.csv", "date,type,category,amount,comment\n"))
    assert row_count(app) == 0


def test_rejected_file_does_not_even_ask(app, tmp_csv):
    """Файл, который всё равно не применится, не должен спрашивать «заменить ли записи»:
    это предложение выбора, которого нет."""
    add(app, "111", category="Исходная")
    seen = import_rejected_csv(app, tmp_csv("bad.csv", "мусор\nникакой не csv\n"))
    assert seen == [], f"по заведомо отклонённому файлу запрошено подтверждение: {seen}"
    assert row_count(app) == 1
