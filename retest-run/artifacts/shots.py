# -*- coding: utf-8 -*-
"""Снимки-доказательства для баг-репортов ретеста + версия браузера."""
import sys, io, datetime, tempfile, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8080/index_refactor.html"
OUT = os.path.join(os.getcwd(), "retest-run", "artifacts")
TODAY = datetime.date.today().isoformat()
tmp = tempfile.mkdtemp()

with sync_playwright() as p:
    b = p.chromium.launch()
    print("browser.version:", b.version)
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page(); pg.goto(URL); pg.evaluate("localStorage.clear()"); pg.reload()
    print("userAgent:", pg.evaluate("() => navigator.userAgent"))

    # RT-BUG-001: три записи из «мусорных» вводов, принятые как числа
    for a, c in [("1 2 0 0", "Пробел между цифрами"), ("1\t200", "Табуляция"), ("1 200", "Нераз. пробел")]:
        pg.fill("#fAmount", a); pg.fill("#fCategory", c)
        pg.evaluate("d => document.querySelector('#fDate').value = d", TODAY)
        pg.click("#addForm button[type=submit]")
    pg.screenshot(path=os.path.join(OUT, "RT-BUG-001-whitespace-amount.png"), full_page=True)
    print("строк:", pg.locator("#tbody tr").count(),
          "| итог расходов:", pg.locator("#sumExpense").inner_text())

    # RT-BUG-002: сообщение с двумя точками
    pg2 = ctx.new_page(); pg2.goto(URL); pg2.evaluate("localStorage.clear()"); pg2.reload()
    pg2.fill("#fAmount", "111"); pg2.fill("#fCategory", "Исходная")
    pg2.evaluate("d => document.querySelector('#fDate').value = d", TODAY)
    pg2.click("#addForm button[type=submit]")
    path = os.path.join(tmp, "bad.csv")
    open(path, "w", encoding="utf-8").write(
        f"date,type,category,amount,comment\n{TODAY},expense,Еда,abc,\n")
    pg2.on("dialog", lambda d: d.dismiss())
    pg2.set_input_files("#fileInput", path)
    pg2.wait_for_selector("#formError:not(:empty)")
    pg2.screenshot(path=os.path.join(OUT, "RT-BUG-002-double-period.png"), clip={"x": 0, "y": 0, "width": 1280, "height": 420})
    print("сообщение:", repr(pg2.locator("#formError").inner_text()))

    # OK-снимок: основной сценарий на исправленной копии
    pg3 = ctx.new_page(); pg3.goto(URL); pg3.evaluate("localStorage.clear()"); pg3.reload()
    for a, c, k, cm in [("1500.75", "Продукты", "expense", "магазин у дома"),
                        ("40000", "З/п", "income", "аванс"),
                        ("320", "Кафе", "expense", "обед"),
                        ("980", "кафе", "expense", "ужин, тот же регистр иначе")]:
        pg3.select_option("#fType", k); pg3.fill("#fAmount", a); pg3.fill("#fCategory", c)
        pg3.evaluate("d => document.querySelector('#fDate').value = d", TODAY)
        pg3.fill("#fComment", cm); pg3.click("#addForm button[type=submit]")
    pg3.screenshot(path=os.path.join(OUT, "OK-main-scenario-fixed.png"), full_page=True)
    print("легенда:", [t.replace("\n", " / ") for t in pg3.locator("#legend li").all_inner_texts()])

    # OK-снимок: отказ формы на «12 руб» (было R3)
    pg3.fill("#fAmount", "12 руб"); pg3.fill("#fCategory", "Проба")
    pg3.click("#addForm button[type=submit]")
    pg3.screenshot(path=os.path.join(OUT, "OK-R3-rejected.png"), clip={"x": 0, "y": 0, "width": 1280, "height": 460})
    print("ошибка:", repr(pg3.locator("#formError").inner_text()))

    # OK-снимок: мобильная ширина
    mctx = b.new_context(viewport={"width": 375, "height": 812})
    m = mctx.new_page(); m.goto(URL); m.evaluate("localStorage.clear()"); m.reload()
    for a, c in [("1500.75", "К" * 32), ("300", "Еда")]:
        m.fill("#fAmount", a); m.fill("#fCategory", c)
        m.evaluate("d => document.querySelector('#fDate').value = d", TODAY)
        m.click("#addForm button[type=submit]")
    m.screenshot(path=os.path.join(OUT, "OK-mobile-375-fixed.png"), full_page=True)
    print("мобильный scrollWidth:", m.evaluate("() => document.documentElement.scrollWidth"))

    ctx.close(); mctx.close(); b.close()
print("СНИМКИ ГОТОВЫ")
