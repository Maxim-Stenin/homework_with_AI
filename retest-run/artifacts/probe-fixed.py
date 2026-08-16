# -*- coding: utf-8 -*-
"""Разведка по app-fixed/index_refactor.html. Ничего не правит, только измеряет."""
import sys, io, datetime, tempfile, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8080/index_refactor.html"
TODAY = datetime.date.today().isoformat()
tmp = tempfile.mkdtemp()

def csv(name, content):
    p = os.path.join(tmp, name)
    open(p, "w", encoding="utf-8").write(content)
    return p

def fresh(ctx):
    pg = ctx.new_page()
    pg.goto(URL); pg.evaluate("localStorage.clear()"); pg.reload()
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(f"pageerror {e}"))
    pg.errs = errs
    return pg

def add(pg, amount, category="Кафе", date=None, kind="expense", comment=""):
    pg.select_option("#fType", kind)
    pg.fill("#fAmount", amount)
    pg.fill("#fCategory", category)
    pg.evaluate("d => document.querySelector('#fDate').value = d", date or TODAY)
    pg.fill("#fComment", comment)
    pg.click("#addForm button[type=submit]")

def rows(pg): return pg.locator("#tbody tr").all_inner_texts()
def err(pg): return pg.locator("#formError").inner_text().strip()
def legend(pg): return [t.replace("\n", " / ") for t in pg.locator("#legend li").all_inner_texts()]
def totals(pg): return [pg.locator(s).inner_text() for s in ("#sumIncome", "#sumExpense", "#sumBalance")]

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 800})

    print("=== 1. Длинный комментарий 500 символов (E1: раньше рвал вёрстку) ===")
    pg = fresh(ctx)
    add(pg, "100", category="Еда", comment="Я" * 500)
    print("строк:", len(rows(pg)),
          "| scrollWidth:", pg.evaluate("()=>document.documentElement.scrollWidth"),
          "| текст цел:", ("Я" * 500) in rows(pg)[0])
    print("консоль:", pg.errs); pg.close()

    print("\n=== 2. R4: подпись в центре кольца против отверстия 106 px ===")
    pg = fresh(ctx)
    add(pg, "99999999", category="Еда")
    w = pg.evaluate("()=>document.querySelector('#donut text').getBBox().width")
    fs = pg.evaluate("()=>getComputedStyle(document.querySelector('#donut text')).fontSize")
    print(f"bbox width: {w:.2f} при отверстии 106 | font-size: {fs} | текст: {pg.locator('#donut text').text_content()}")
    pg.close()

    print("\n=== 3. R3: число + мусор ===")
    pg = fresh(ctx)
    for a in ["12abc", "12 руб", "1,2,3", "5.", "0x10", "1 200", "1 2 0 0", "007", ".5", "1e5"]:
        before = len(rows(pg))
        add(pg, a, category="Проба")
        after = len(rows(pg))
        print(f"  {a!r:12} -> строк {before}->{after} | {'ПРИНЯТО: ' + rows(pg)[0].replace(chr(9),' | ') if after > before else 'отказ: ' + err(pg)}")
        if after > before:
            pg.evaluate("localStorage.clear()"); pg.reload()
    print("консоль:", pg.errs); pg.close()

    print("\n=== 4. R1: частичная загрузка (одна битая строка из трёх) ===")
    pg = fresh(ctx)
    add(pg, "111", category="Исходная")
    pg.on("dialog", lambda d: d.accept())
    pg.set_input_files("#fileInput", csv("partial.csv",
        "date,type,category,amount,comment\n"
        f"{TODAY},expense,Хорошая1,100.00,\n"
        f"{TODAY},expense,Битая,abc,\n"
        f"{TODAY},expense,Хорошая2,200.00,\n"))
    pg.wait_for_timeout(500)
    print("строк после:", len(rows(pg)), "| ошибка:", repr(err(pg)))
    print("строки:", [r.replace(chr(9), " | ") for r in rows(pg)]); pg.close()

    print("\n=== 5. R2: отрицательные суммы из CSV / противоречие диаграммы и таблицы ===")
    pg = fresh(ctx)
    pg.on("dialog", lambda d: d.accept())
    pg.set_input_files("#fileInput", csv("neg.csv",
        f"date,type,category,amount,comment\n{TODAY},expense,А,100.00,\n{TODAY},expense,Б,-100.00,\n"))
    pg.wait_for_timeout(400)
    print("строк:", len(rows(pg)), "| легенда:", legend(pg), "| итоги:", totals(pg))
    print("пустое состояние диаграммы видно:", pg.locator("#chartEmpty").is_visible(), "| ошибка:", repr(err(pg)))
    pg.close()

    print("\n=== 6. Подтверждение импорта на ПУСТОМ списке (шум или защита?) ===")
    pg = fresh(ctx)
    msgs = []
    pg.on("dialog", lambda d: (msgs.append(d.message), d.accept()))
    pg.set_input_files("#fileInput", csv("good.csv",
        f"date,type,category,amount,comment\n{TODAY},expense,Еда,100.00,\n"))
    pg.wait_for_timeout(400)
    print("диалогов:", len(msgs), "| текст:", repr(msgs[0] if msgs else None))
    print("строк:", len(rows(pg))); pg.close()

    print("\n=== 7. Отказ от подтверждения импорта ===")
    pg = fresh(ctx)
    add(pg, "111", category="Исходная")
    pg.on("dialog", lambda d: d.dismiss())
    pg.set_input_files("#fileInput", csv("good.csv",
        f"date,type,category,amount,comment\n{TODAY},expense,Еда,100.00,\n"))
    pg.wait_for_timeout(400)
    print("строк:", len(rows(pg)), "| ошибка:", repr(err(pg))); pg.close()

    print("\n=== 8. Удаление: текст подтверждения и отказ ===")
    pg = fresh(ctx)
    add(pg, "100", category="Еда")
    msgs = []
    pg.on("dialog", lambda d: (msgs.append(d.message), d.dismiss()))
    pg.click("#tbody tr:first-child button"); pg.wait_for_timeout(300)
    print("диалог:", repr(msgs[0] if msgs else None), "| строк после отказа:", len(rows(pg)))
    pg.close()

    print("\n=== 9. Длинная категория 32 символа + вёрстка, текст не потерян ===")
    pg = fresh(ctx)
    add(pg, "100", category="К" * 32)
    print("строк:", len(rows(pg)), "| scrollWidth:", pg.evaluate("()=>document.documentElement.scrollWidth"))
    print("текст цел в таблице:", ("К" * 32) in rows(pg)[0], "| в легенде:", legend(pg))
    print("clientHeight строки:", pg.evaluate("()=>document.querySelector('#tbody tr').getBoundingClientRect().height"))
    pg.close()

    print("\n=== 10. Слияние категорий по регистру: что видно в таблице ===")
    pg = fresh(ctx)
    for c in ["Кафе", "кафе", "  КАФЕ  "]:
        add(pg, "100", category=c)
    print("строк:", len(rows(pg)), "| легенда:", legend(pg))
    print("категории в таблице:", [r.split("\t")[1] for r in rows(pg)]); pg.close()

    print("\n=== 11. Round-trip на грязных значениях ===")
    pg = fresh(ctx)
    for a, c, k, cm in [("1200.50", "Ка,фе", "expense", 'кофе "тройной"'),
                        ("40000", "З/п", "income", "аванс, первая часть"),
                        ("0.01", "Мелочь", "expense", "копейка")]:
        add(pg, a, category=c, kind=k, comment=cm)
    before, tb = rows(pg), totals(pg)
    with pg.expect_download() as info:
        pg.click("#btnSave")
    path = os.path.join(tmp, "rt.csv"); info.value.save_as(path)
    pg.evaluate("localStorage.clear()"); pg.reload()
    pg.on("dialog", lambda d: d.accept())
    pg.set_input_files("#fileInput", path); pg.wait_for_timeout(500)
    print("совпало дословно:", rows(pg) == before, "| итоги совпали:", totals(pg) == tb)
    if rows(pg) != before:
        print(" было:", before); print(" стало:", rows(pg))
    print("ошибка:", repr(err(pg))); pg.close()

    print("\n=== 12. Импорт: категория 33 символа и сумма вне границы ===")
    for name, content in [("cat33.csv", f"date,type,category,amount,comment\n{TODAY},expense,{'К'*33},100.00,\n"),
                          ("huge.csv", f"date,type,category,amount,comment\n{TODAY},expense,Еда,100000000,\n"),
                          ("zero.csv", f"date,type,category,amount,comment\n{TODAY},expense,Еда,0.001,\n"),
                          ("onlyheader.csv", "date,type,category,amount,comment\n")]:
        pg = fresh(ctx)
        add(pg, "111", category="Исходная")
        pg.on("dialog", lambda d: d.accept())
        pg.set_input_files("#fileInput", csv(name, content)); pg.wait_for_timeout(400)
        print(f"  {name:16} строк: {len(rows(pg))} | ошибка: {err(pg)!r}")
        pg.close()

    print("\n=== 13. Мобильная ширина 375: длинная категория и длинный комментарий ===")
    mctx = b.new_context(viewport={"width": 375, "height": 812})
    pg = mctx.new_page(); pg.goto(URL); pg.evaluate("localStorage.clear()"); pg.reload()
    add(pg, "300", category="К" * 32, comment="Я" * 300)
    print("строк:", len(rows(pg)), "| scrollWidth:", pg.evaluate("()=>document.documentElement.scrollWidth"))
    pg.close(); mctx.close()

    print("\n=== 14. Пустое состояние после удаления последней записи ===")
    pg = fresh(ctx)
    add(pg, "10", category="Раз")
    pg.on("dialog", lambda d: d.accept())
    pg.click("#tbody tr:first-child button"); pg.wait_for_timeout(300)
    print("строк:", len(rows(pg)), "| tableEmpty:", pg.locator("#tableEmpty").is_visible(),
          "| chartEmpty:", pg.locator("#chartEmpty").is_visible(),
          "| donut детей:", pg.locator("#donut *").count())
    print("консоль:", pg.errs); pg.close()

    print("\n=== 15. 30 категорий: доли легенды ===")
    pg = fresh(ctx)
    for i in range(30):
        add(pg, str(i + 1), category=f"Кат{i:02d}")
    shares = [int(x.split("/")[-1].strip().rstrip("%")) for x in legend(pg)]
    print("категорий:", len(shares), "| сумма долей:", sum(shares))
    print("консоль:", pg.errs); pg.close()

    ctx.close(); b.close()
print("\nГОТОВО")
