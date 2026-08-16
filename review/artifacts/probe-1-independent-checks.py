"""Независимая проверка ревьюера: то, чего может не быть в тест-плане агента."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8080/index.html"
TMP = os.path.dirname(os.path.abspath(__file__))

def mkfile(name, content, enc="utf-8"):
    p = os.path.join(TMP, name)
    with open(p, "w", encoding=enc, newline="") as f:
        f.write(content)
    return p

def rows(pg):
    return pg.locator("#tbody tr").all_inner_texts()

def legend(pg):
    return pg.locator("#legend li").all_inner_texts()

def totals(pg):
    return [pg.locator(s).inner_text() for s in ("#sumIncome", "#sumExpense", "#sumBalance")]

def add(pg, amount, category="Кафе", date="2026-08-16", kind="expense", comment=""):
    pg.select_option("#fType", kind)
    pg.fill("#fAmount", amount)
    pg.fill("#fCategory", category)
    pg.evaluate("d => document.querySelector('#fDate').value = d", date)
    pg.fill("#fComment", comment)
    pg.click("#addForm button[type=submit]")

def fresh(pg):
    pg.goto(URL); pg.evaluate("localStorage.clear()"); pg.reload()

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)

    print("=== R1. ЧАСТИЧНАЯ ЗАГРУЗКА: хороший файл с одной битой строкой ===")
    fresh(pg)
    add(pg, "111", category="Исходная")
    f = mkfile("mixed.csv",
               "date,type,category,amount,comment\n"
               "2026-08-16,expense,Хорошая1,100.00,\n"
               "2026-08-16,expense,Битая,abc,\n"
               "2026-08-16,expense,Хорошая2,200.00,\n")
    pg.set_input_files("#fileInput", f); pg.wait_for_timeout(400)
    print("строк после:", len(rows(pg)), "| ошибка:", repr(pg.locator("#formError").inner_text()))
    print("строки:", [r.replace("\t", " | ") for r in rows(pg)])

    print("\n=== R2. localStorage: переживает ли перезагрузку (вне объёма у агента) ===")
    fresh(pg)
    add(pg, "1234.56", category="Продукты", comment='кома, и "кавычка"')
    before = rows(pg)
    pg.reload(); pg.wait_for_timeout(200)
    after = rows(pg)
    print("до перезагрузки:", before)
    print("после:", after)
    print("совпало:", before == after)

    print("\n=== R3. localStorage: порча хранилища ===")
    fresh(pg)
    add(pg, "100", category="Еда")
    pg.evaluate("localStorage.setItem('finance.csv', 'полный мусор\\nне csv;;;')")
    pg.reload(); pg.wait_for_timeout(200)
    print("строк после порчи хранилища:", len(rows(pg)), "| итоги:", totals(pg))

    print("\n=== R4. Порядок строк при одинаковой дате ===")
    fresh(pg)
    for i in range(1, 6):
        add(pg, str(i * 10), category=f"Кат{i}", date="2026-08-10")
    print("порядок:", [r.split("\t")[1] for r in rows(pg)])

    print("\n=== R5. Отрицательная сумма из CSV: что с диаграммой ===")
    fresh(pg)
    f = mkfile("neg.csv", "date,type,category,amount,comment\n2026-08-16,expense,Минус,-500.00,\n")
    pg.set_input_files("#fileInput", f); pg.wait_for_timeout(400)
    print("итоги:", totals(pg))
    print("легенда:", legend(pg))
    print("сегментов в svg:", pg.locator("#donut circle").count())
    print("dasharray:", pg.eval_on_selector_all("#donut circle", "els=>els.map(e=>e.getAttribute('stroke-dasharray'))"))
    print("пустое состояние диаграммы видно:", pg.locator("#chartEmpty").is_visible())

    print("\n=== R6. Смешанные знаки: категория с +100 и -100 даёт total=0 ===")
    fresh(pg)
    f = mkfile("zero.csv", "date,type,category,amount,comment\n"
                           "2026-08-16,expense,А,100.00,\n"
                           "2026-08-16,expense,Б,-100.00,\n")
    pg.set_input_files("#fileInput", f); pg.wait_for_timeout(400)
    print("строк:", len(rows(pg)), "| легенда:", legend(pg), "| пустая диаграмма:", pg.locator("#chartEmpty").is_visible())
    print("итоги:", totals(pg))

    print("\n=== R7. Round-trip комментария с переводом строки (приходит из CSV) ===")
    fresh(pg)
    f = mkfile("multiline.csv", 'date,type,category,amount,comment\n2026-08-16,expense,Еда,100.00,"первая\nвторая"\n')
    pg.set_input_files("#fileInput", f); pg.wait_for_timeout(400)
    print("строк:", len(rows(pg)), "| строка:", [r.replace("\t", " | ").replace("\n", "\\n") for r in rows(pg)])
    with pg.expect_download() as d:
        pg.click("#btnSave")
    out = os.path.join(TMP, "rt.csv"); d.value.save_as(out)
    txt = open(out, encoding="utf-8").read()
    print("выгружено:", repr(txt))
    pg.evaluate("localStorage.clear()"); pg.reload()
    pg.set_input_files("#fileInput", out); pg.wait_for_timeout(400)
    print("после round-trip:", [r.replace("\t", " | ").replace("\n", "\\n") for r in rows(pg)])

    print("\n=== R8. CSV-инъекция формулы в выгрузке ===")
    fresh(pg)
    add(pg, "100", category="=1+1", comment="@SUM(A1)")
    with pg.expect_download() as d:
        pg.click("#btnSave")
    out2 = os.path.join(TMP, "inj.csv"); d.value.save_as(out2)
    print(repr(open(out2, encoding="utf-8").read()))

    print("\n=== R9. Категория из CSV длиной 200 (после «починки» формы дефект остался бы) ===")
    fresh(pg)
    f = mkfile("longcat.csv", "date,type,category,amount,comment\n2026-08-16,expense," + "К" * 200 + ",100.00,\n")
    pg.set_input_files("#fileInput", f); pg.wait_for_timeout(400)
    print("scrollWidth:", pg.evaluate("()=>document.documentElement.scrollWidth"))

    print("\n=== R10. Две вкладки: расходятся ли данные ===")
    fresh(pg)
    add(pg, "100", category="Первая")
    pg2 = ctx.new_page(); pg2.goto(URL); pg2.wait_for_timeout(200)
    add(pg2, "200", category="Вторая")
    pg.reload(); pg.wait_for_timeout(200)
    print("вкладка1 после reload:", [r.split('\t')[1] for r in rows(pg)])
    print("вкладка2:", [r.split('\t')[1] for r in rows(pg2)])
    pg2.close()

    print("\n=== R11. Дата вне календаря / странные значения через форму ===")
    fresh(pg)
    for d_ in ["2026-02-30", "0000-01-01", "99999-01-01"]:
        n0 = len(rows(pg))
        add(pg, "100", category=f"Д{d_}", date=d_)
        print(f"  {d_!r}: строк {n0}->{len(rows(pg))} err={pg.locator('#formError').inner_text()!r}")

    print("\n=== R12. Сумма 99999999.99 и вёрстка итогов ===")
    fresh(pg)
    add(pg, "99999999.99", category="Много")
    print("итоги:", totals(pg), "| scrollWidth:", pg.evaluate("()=>document.documentElement.scrollWidth"))

    print("\n=== R13. Заголовок в середине файла / регистр заголовка ===")
    fresh(pg)
    f = mkfile("hdr.csv", "DATE,TYPE,CATEGORY,AMOUNT,COMMENT\n2026-08-16,expense,Еда,100.00,\n")
    pg.set_input_files("#fileInput", f); pg.wait_for_timeout(400)
    print("заголовок в верхнем регистре, строк:", len(rows(pg)), [r.split('\t')[1] for r in rows(pg)])

    print("\n=== R14. Ошибка формы не сбрасывается после успеха? ===")
    fresh(pg)
    add(pg, "abc", category="Ошибка")
    e1 = pg.locator("#formError").inner_text()
    add(pg, "100", category="Норм")
    e2 = pg.locator("#formError").inner_text()
    print("после ошибки:", repr(e1), "| после успеха:", repr(e2))

    print("\n=== КОНСОЛЬ ЗА ВЕСЬ ПРОГОН ===")
    print(errs if errs else "ошибок нет")
    b.close()
