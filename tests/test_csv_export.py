"""Выгрузка CSV — работающая часть обмена данными (SPEC п.9, п.12)."""
import pytest

from helpers import add


@pytest.fixture
def exported(app, tmp_path):
    def do():
        with app.expect_download() as info:
            app.click("#btnSave")
        path = tmp_path / "export.csv"
        info.value.save_as(str(path))
        return info.value, path.read_text(encoding="utf-8")
    return do


def test_download_has_expected_name(app, exported):
    add(app, "100", category="Еда")
    download, _ = exported()
    assert download.suggested_filename == "transactions.csv"


def test_header_row(app, exported):
    add(app, "100", category="Еда")
    _, text = exported()
    assert text.lstrip("﻿").splitlines()[0] == "date,type,category,amount,comment"


def test_utf8_bom_and_cyrillic(app, exported):
    add(app, "100", category="Продукты")
    _, text = exported()
    assert text.startswith("﻿"), "нет BOM — Excel прочитает кириллицу как мусор"
    assert "Продукты" in text


def test_comma_inside_value_is_quoted(app, exported):
    add(app, "100", category="Ка,фе")
    _, text = exported()
    assert '"Ка,фе"' in text


def test_quotes_are_doubled(app, exported):
    add(app, "100", category="Еда", comment='он сказал "привет"')
    _, text = exported()
    assert '"он сказал ""привет"""' in text


def test_amount_has_two_decimals(app, exported):
    add(app, "1200.5", category="Еда")
    _, text = exported()
    assert ",1200.50," in text


def test_income_and_expense_types(app, exported):
    add(app, "100", category="Еда")
    add(app, "200", category="З/п", kind="income")
    _, text = exported()
    assert ",expense," in text and ",income," in text
