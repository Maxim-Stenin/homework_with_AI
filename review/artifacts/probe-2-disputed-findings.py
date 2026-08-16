"""Проверка спорных мест: кто прав — наивный прогон или прогон со скиллами."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8080/index.html"
TMP = os.path.dirname(os.path.abspath(__file__))

def rows(pg): return pg.locator("#tbody tr").all_inner_texts()
def add(pg, amount, category="Кафе", date="2026-08-16", kind="expense", comment=""):
    pg.select_option("#fType", kind); pg.fill("#fAmount", amount)
    pg.fill("#fCategory", category)
    pg.evaluate("d => document.querySelector('#fDate').value = d", date)
    pg.fill("#fComment", comment); pg.click("#addForm button[type=submit]")
def fresh(pg): pg.goto(URL); pg.evaluate("localStorage.clear()"); pg.reload()

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()

    print("=== V1. Enter отправляет форму? (naive-2 BUG-005) ===")
    fresh(pg)
    pg.click("#fCategory"); pg.keyboard.type("EnterTest")
    pg.click("#fAmount"); pg.keyboard.type("42")
    submits = pg.evaluate("() => { window.__s=0; document.getElementById('addForm')"
                          ".addEventListener('submit',()=>window.__s++); return 'ok'; }")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(300)
    print("строк после Enter:", len(rows(pg)),
          "| submit-событий:", pg.evaluate("() => window.__s"),
          "| активный:", pg.evaluate("() => document.activeElement.id"))
    print("клик по кнопке после этого:", end=" ")
    pg.click("#addForm button[type=submit]"); pg.wait_for_timeout(200)
    print("строк:", len(rows(pg)))

    print("\n=== V2. Дата предзаполнена при первом открытии? (naive-2 BUG-013) ===")
    ctx2 = b.new_context(viewport={"width": 1280, "height": 800})
    pgc = ctx2.new_page(); pgc.goto(URL)
    print("значение #fDate:", repr(pgc.input_value("#fDate")))
    print("после успешной записи дата:", end=" ")
    add(pgc, "100", category="X", date="2026-01-05")
    print(repr(pgc.input_value("#fDate")), "| сумма:", repr(pgc.input_value("#fAmount")))
    ctx2.close()

    print("\n=== V3. BOM в выгруженном файле? (naive-2 BUG-006 п.1) ===")
    fresh(pg); add(pg, "100", category="Продукты")
    with pg.expect_download() as d:
        pg.click("#btnSave")
    out = os.path.join(TMP, "bom.csv"); d.value.save_as(out)
    raw = open(out, "rb").read()
    print("первые байты:", raw[:6], "| BOM есть:", raw.startswith(b"\xef\xbb\xbf"))

    print("\n=== V4. Длинный КОММЕНТАРИЙ ломает вёрстку? (naive-1 BUG-007; skilled TC-065 = ✅) ===")
    fresh(pg)
    add(pg, "100", category="Еда", comment="Я" * 240)
    print("scrollWidth:", pg.evaluate("()=>document.documentElement.scrollWidth"), "при окне 1280")
    add(pg, "100", category="Еда2", comment="Я" * 500)
    print("с 500 символами scrollWidth:", pg.evaluate("()=>document.documentElement.scrollWidth"))

    print("\n=== V5. Кто именно распирает страницу на длинной КАТЕГОРИИ? ===")
    fresh(pg)
    add(pg, "100", category="К" * 200)
    print("scrollWidth:", pg.evaluate("()=>document.documentElement.scrollWidth"))
    print(pg.evaluate("""() => {
      const W = document.documentElement.clientWidth, out = [];
      document.querySelectorAll('*').forEach(e => {
        const r = e.getBoundingClientRect();
        if (r.right > W + 1) out.push(e.tagName + (e.id?'#'+e.id:'') +
            (e.className && typeof e.className==='string' ? '.'+e.className.trim().split(/\\s+/).join('.') : '') +
            ' right=' + Math.round(r.right) + ' w=' + Math.round(r.width));
      });
      return out;
    }"""))

    print("\n=== V6. `12abc` в сумме (naive-1 BUG-003; в тест-плане skilled его нет) ===")
    fresh(pg)
    for v in ["12abc", "5.", "0x10", "12 руб", "1,2,3"]:
        n0 = len(rows(pg))
        add(pg, v, category=f"C{v}")
        n1 = len(rows(pg))
        last = rows(pg)[0].replace("\t", " | ") if n1 > n0 else "-"
        print(f"  {v!r}: строк {n0}->{n1}  err={pg.locator('#formError').inner_text()!r}  {last}")

    print("\n=== V7. Потеря точности на огромной сумме (naive-2 BUG-008) ===")
    fresh(pg)
    add(pg, "999999999999999999999", category="Огромная")
    print("в хранилище:", pg.evaluate("()=>localStorage.getItem('finance.csv')"))
    print("scrollWidth:", pg.evaluate("()=>document.documentElement.scrollWidth"))

    print("\n=== V8. Центральная подпись кольца на огромной сумме (naive-1 BUG-012) ===")
    print("bbox width:", pg.evaluate("()=>document.querySelector('#donut text').getBBox().width"),
          "| внутренний диаметр ≈ 2*70-34 =", 2*70-34)

    b.close()
