# -*- coding: utf-8 -*-
"""Разведка-2: границы находки «пробел внутри суммы» и сопутствующее."""
import sys, io, datetime, tempfile, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8080/index_refactor.html"
TODAY = datetime.date.today().isoformat()
tmp = tempfile.mkdtemp()

def csv(name, content):
    p = os.path.join(tmp, name); open(p, "w", encoding="utf-8").write(content); return p

with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1280, "height": 800})

    def fresh():
        pg = ctx.new_page(); pg.goto(URL); pg.evaluate("localStorage.clear()"); pg.reload(); return pg

    def add(pg, amount, category="Проба", date=None, kind="expense", comment=""):
        pg.select_option("#fType", kind); pg.fill("#fAmount", amount); pg.fill("#fCategory", category)
        pg.evaluate("d => document.querySelector('#fDate').value = d", date or TODAY)
        pg.fill("#fComment", comment); pg.click("#addForm button[type=submit]")

    def rows(pg): return pg.locator("#tbody tr").all_inner_texts()
    def err(pg): return pg.locator("#formError").inner_text().strip()

    print("=== A. Пробелы ВНУТРИ суммы (форма) ===")
    for a in ["1 200", "1 2 0 0", "1 200", "1\t200", "1 200.50", "1 200,50", "9 9 9 9 9 9 9 9 9",
              "1 e 5", "1 2 abc"]:
        pg = fresh(); add(pg, a)
        r = rows(pg)
        print(f"  {a!r:22} -> {'ПРИНЯТО: ' + r[0].split(chr(9))[3] if r else 'отказ: ' + err(pg)}")
        pg.close()

    print("\n=== B. Тот же вход через CSV ===")
    for name, amt in [("sp.csv", "1 200"), ("sp2.csv", "1 2 0 0"), ("sp3.csv", "9 9 9 9 9 9 9 9 9")]:
        pg = fresh(); pg.on("dialog", lambda d: d.accept())
        pg.set_input_files("#fileInput", csv(name,
            f'date,type,category,amount,comment\n{TODAY},expense,Еда,"{amt}",\n'))
        pg.wait_for_timeout(400)
        r = rows(pg)
        print(f"  {amt!r:22} -> строк {len(r)} | {r[0].split(chr(9))[3] if r else err(pg)}")
        pg.close()

    print("\n=== C. Верхняя граница через пробел: 99 999 999 и 100 000 000 ===")
    for a in ["99999999", "100000000", "9 9 9 9 9 9 9 9 9 9"]:
        pg = fresh(); add(pg, a); r = rows(pg)
        print(f"  {a!r:22} -> {'ПРИНЯТО: ' + r[0].split(chr(9))[3] if r else 'отказ: ' + err(pg)}")
        pg.close()

    print("\n=== D. Текст ошибки импорта: две точки подряд? ===")
    pg = fresh(); pg.on("dialog", lambda d: d.accept())
    pg.set_input_files("#fileInput", csv("bad.csv", f"date,type,category,amount,comment\n{TODAY},expense,Еда,abc,\n"))
    pg.wait_for_timeout(400)
    e = err(pg); print("  ", repr(e), "| '..' внутри:", ".." in e)
    pg.close()

    print("\n=== E. Несуществующая дата и дата из CSV ===")
    for d in ["2026-02-30", "2026-13-01", "0000-01-01"]:
        pg = fresh(); add(pg, "100", date=d); r = rows(pg)
        print(f"  {d} -> {'ПРИНЯТО' if r else 'отказ: ' + err(pg)}")
        pg.close()

    print("\n=== F. Комментарий 500 символов переживает round-trip ===")
    pg = fresh(); add(pg, "100", category="Еда", comment="Я" * 500)
    before = rows(pg)
    with pg.expect_download() as info: pg.click("#btnSave")
    path = os.path.join(tmp, "c.csv"); info.value.save_as(path)
    pg.evaluate("localStorage.clear()"); pg.reload(); pg.on("dialog", lambda d: d.accept())
    pg.set_input_files("#fileInput", path); pg.wait_for_timeout(500)
    print("  дословно:", rows(pg) == before, "| scrollWidth:", pg.evaluate("()=>document.documentElement.scrollWidth"))
    pg.close()

    print("\n=== G. Номер битой строки при CRLF и при ошибке в последней строке ===")
    pg = fresh(); pg.on("dialog", lambda d: d.accept())
    pg.set_input_files("#fileInput", csv("crlf.csv",
        f"date,type,category,amount,comment\r\n{TODAY},expense,А,100.00,\r\n{TODAY},expense,Б,abc,\r\n"))
    pg.wait_for_timeout(400); print("  CRLF:", repr(err(pg))); pg.close()

    print("\n=== H. Тип вне income/expense и пустая категория в CSV ===")
    for name, content in [("type.csv", f"date,type,category,amount,comment\n{TODAY},dragon,Еда,100.00,\n"),
                          ("cat.csv", f"date,type,category,amount,comment\n{TODAY},expense,,100.00,\n"),
                          ("neg.csv", f"date,type,category,amount,comment\n{TODAY},expense,Еда,-500.00,\n")]:
        pg = fresh(); pg.on("dialog", lambda d: d.accept())
        pg.set_input_files("#fileInput", csv(name, content)); pg.wait_for_timeout(400)
        print(f"  {name:10} строк: {len(rows(pg))} | {err(pg)!r}"); pg.close()

    ctx.close(); b.close()
print("\nГОТОВО-2")
