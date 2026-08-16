# -*- coding: utf-8 -*-
"""Дымовой прогон исправленной копии. НЕ ретест: это проверка Автора, что код работает.
Полный прогон тест-плана и pytest — работа сессии 9."""
import datetime
import os
import sys
import tempfile

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8080/index_refactor.html"
TODAY = datetime.date.today().isoformat()
TOMORROW = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

TMP = tempfile.mkdtemp(prefix="smoke-csv-")
ok_count = 0
fail = []


def norm(v):
    """ru-RU разделяет разряды неразрывным пробелом — сравниваем по обычному."""
    if isinstance(v, str):
        return v.replace(" ", " ").replace(" ", " ")
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, tuple):
        return tuple(norm(x) for x in v)
    return v


def check(name, got, want):
    global ok_count
    got, want = norm(got), norm(want)
    if got == want:
        ok_count += 1
        print(f"  OK   {name}: {got!r}")
    else:
        fail.append(name)
        print(f"  FAIL {name}: получено {got!r}, ожидалось {want!r}")


def csv_file(name, content):
    p = os.path.join(TMP, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return p


def add(page, amount, category="Кафе", date=None, kind="expense", comment=""):
    page.select_option("#fType", kind)
    page.fill("#fAmount", amount)
    page.fill("#fCategory", category)
    # date=None -> сегодня, date="" -> ИМЕННО пустая дата. `date or TODAY` здесь
    # подставлял бы сегодня вместо пустой строки: на этом в сессии 6 родился BUG-006.
    page.evaluate("d => document.querySelector('#fDate').value = d",
                  TODAY if date is None else date)
    page.fill("#fComment", comment)
    page.click("#addForm button[type=submit]")


def rows(page):
    return page.locator("#tbody tr").count()


def err(page):
    return page.locator("#formError").inner_text().strip()


def reset(page):
    page.evaluate("() => localStorage.clear()")
    page.reload()


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    console = []
    page.on("console", lambda m: console.append(f"{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
    page.goto(URL)
    reset(page)

    print("\n[1] Основной сценарий")
    add(page, "1200.50", "Продукты")
    add(page, "40000", "З/п", kind="income")
    check("строк в таблице", rows(page), 2)
    check("доходы", page.locator("#sumIncome").inner_text(), "40 000,00 ₽")
    check("расходы", page.locator("#sumExpense").inner_text(), "1 200,50 ₽")
    check("остаток", page.locator("#sumBalance").inner_text(), "38 799,50 ₽")

    print("\n[2] BUG-011 / R3 — строгий разбор суммы")
    reset(page)
    for bad in ["1e5", "1_000", "1..2", "+50", ".5", "007", "12abc", "12 руб", "1,2,3", "0", "-5", "abc"]:
        before = rows(page)
        add(page, bad, "Мусор")
        check(f"отказ на {bad!r}", (rows(page), bool(err(page))), (before, True))

    print("\n[3] BUG-010 / BUG-012 — границы суммы")
    reset(page)
    add(page, "99999999", "Граница")
    check("99999999 принято", rows(page), 1)
    add(page, "100000000", "Перебор")
    check("100000000 отклонено", rows(page), 1)
    add(page, "0.001", "Копейка")
    check("0.001 отклонено", rows(page), 1)
    add(page, "0.005", "Копейка2")
    check("0.005 принято", rows(page), 2)

    print("\n[4] BUG-007 / BUG-008 — категория")
    reset(page)
    add(page, "100", "")
    check("пустая категория отклонена", rows(page), 0)
    add(page, "100", "   ")
    check("пробелы отклонены", rows(page), 0)
    add(page, "100", "К" * 32)
    check("32 символа приняты", rows(page), 1)
    # 33 символа задаются через DOM: page.fill упирался бы в ограничение поля,
    # если бы оно там стояло, и проверка измеряла бы разметку вместо кода.
    page.select_option("#fType", "expense")
    page.fill("#fAmount", "100")
    page.evaluate("v => document.querySelector('#fCategory').value = v", "К" * 33)
    page.evaluate("d => document.querySelector('#fDate').value = d", TODAY)
    page.click("#addForm button[type=submit]")
    check("33 символа отклонены", (rows(page), err(page)), (1, "Категория не длиннее 32 символов."))

    print("\n[5] BUG-004 — регистр категории")
    reset(page)
    add(page, "100", "Кафе")
    add(page, "100", "кафе")
    add(page, "100", "  кафе  ")
    legend = [t.replace("\n", " / ") for t in page.locator("#legend li").all_inner_texts()]
    check("сегментов в легенде", len(legend), 1)
    check("легенда", legend, ["Кафе / 300,00 ₽ / 100%"])

    print("\n[6] BUG-005 — будущая дата")
    reset(page)
    add(page, "100", "Будущее", date=TOMORROW)
    check("завтра отклонено", rows(page), 0)
    check("max у поля даты", page.get_attribute("#fDate", "max"), TODAY)
    add(page, "100", "БезДаты", date="")
    check("пустая дата отклонена", rows(page), 0)

    print("\n[7] BUG-009 — вёрстка при длинной категории из CSV")
    reset(page)
    long_cat = "Д" * 32
    # Только `once`: постоянный обработчик перехватывал бы диалоги следующих разделов
    # раньше одноразовых и незаметно ломал проверки подтверждения.
    page.once("dialog", lambda d: d.accept())
    page.set_input_files("#fileInput", csv_file(
        "long.csv",
        f"date,type,category,amount,comment\n{TODAY},expense,{long_cat},100.00,{'к' * 300}\n"))
    page.wait_for_timeout(200)
    check("длинная строка загружена", rows(page), 1)
    width = page.evaluate("() => document.documentElement.scrollWidth")
    check("ширина документа <= 1280", width <= 1280, True)

    print("\n[8] BUG-003 — подтверждение удаления")
    reset(page)
    add(page, "100", "Удаляемая")
    add(page, "200", "Остаётся")
    page.once("dialog", lambda d: d.dismiss())
    page.locator("#tbody .del").first.click()
    check("отказ от подтверждения — запись на месте", rows(page), 2)
    page.once("dialog", lambda d: d.accept())
    page.locator("#tbody .del").first.click()
    check("согласие — запись удалена", rows(page), 1)

    print("\n[9] BUG-001 — подтверждение импорта")
    reset(page)
    add(page, "111", "Исходная")
    good = csv_file("good.csv", f"date,type,category,amount,comment\n{TODAY},expense,ИзФайла,100.00,\n")
    page.once("dialog", lambda d: d.dismiss())
    page.set_input_files("#fileInput", good)
    page.wait_for_timeout(200)
    check("отказ — список не изменён", rows(page), 1)
    check("сообщение об отмене", "отменена" in err(page), True)
    page.once("dialog", lambda d: d.accept())
    page.set_input_files("#fileInput", good)
    page.wait_for_timeout(200)
    check("согласие — список заменён", rows(page), 1)
    check("данные из файла", "ИзФайла" in page.locator("#tbody").inner_text(), True)

    print("\n[10] BUG-002 / R1 — битый файл и частичная загрузка")
    reset(page)
    add(page, "111", "Исходная")
    cases = {
        "мусор": "это не csv вообще\nпросто текст;;;",
        "пустой": "",
        "чужой заголовок": "a,b,c\n1,2,3",
        "только заголовок и битая строка": f"date,type,category,amount,comment\n{TODAY},expense,Битая,abc,\n",
        "частичная (R1)": (f"date,type,category,amount,comment\n"
                           f"{TODAY},expense,Хорошая1,100.00,\n"
                           f"{TODAY},expense,Битая,abc,\n"
                           f"{TODAY},expense,Хорошая2,200.00,\n"),
        "отрицательная (BUG-013)": f"date,type,category,amount,comment\n{TODAY},expense,Минус,-500.00,\n",
        "неизвестный тип (BUG-014)": f"date,type,category,amount,comment\n{TODAY},dragon,Тип,100.00,\n",
        "не-дата (BUG-015)": "date,type,category,amount,comment\nне-дата,expense,БитаяДата,100.00,\n",
        "будущая дата (BUG-015)": "date,type,category,amount,comment\n2099-01-01,expense,ИзБудущего,100.00,\n",
        "огромная сумма": f"date,type,category,amount,comment\n{TODAY},expense,Огромная,999999999999,\n",
        "мало столбцов": f"date,type,category,amount,comment\n{TODAY},expense,Мало\n",
    }
    for name, content in cases.items():
        page.set_input_files("#fileInput", csv_file(f"bad-{abs(hash(name))}.csv", content))
        page.wait_for_timeout(120)
        check(f"{name}: список цел + ошибка", (rows(page), err(page).startswith("Файл не загружен")), (1, True))

    print("\n[11] R2 — диаграмма и таблица не противоречат друг другу")
    check("легенда не пуста при непустой таблице", len(page.locator("#legend li").all_inner_texts()) > 0, True)
    check("пустое состояние диаграммы скрыто", page.locator("#chartEmpty").is_hidden(), True)

    print("\n[12] SPEC п.12 — round-trip с запятыми и кавычками")
    reset(page)
    tricky = f'''date,type,category,amount,comment
{TODAY},expense,"Кафе, бар",100.00,"он сказал ""да"""
{TODAY},income,З/п,40000.00,обычный
{TODAY},expense,Продукты,1200.50,"строка, с запятой"
{TODAY},expense,Такси,300.00,
{TODAY},income,Премия,5000.00,"кавычки ""внутри"" текста"
'''
    page.once("dialog", lambda d: d.accept())
    page.set_input_files("#fileInput", csv_file("tricky.csv", tricky))
    page.wait_for_timeout(200)
    check("загружено 5 строк", rows(page), 5)
    stored = page.evaluate("() => localStorage.getItem('finance.csv')")
    check("CSV в хранилище совпадает дословно", stored.strip(), tricky.strip())

    print("\n[13] R4 — подпись помещается в отверстие кольца")
    reset(page)
    page.once("dialog", lambda d: d.accept())
    page.set_input_files("#fileInput", csv_file(
        "big.csv",
        "date,type,category,amount,comment\n"
        + "".join(f"{TODAY},expense,К{i},99999999.00,\n" for i in range(9))))
    page.wait_for_timeout(200)
    bbox = page.evaluate("() => { const t = document.querySelector('#donut text'); return t ? t.getBBox().width : -1; }")
    print(f"       ширина подписи: {bbox:.2f} px, отверстие кольца: 106 px")
    check("подпись уже отверстия", bbox <= 106, True)

    print("\n[14] Пустое состояние")
    reset(page)
    check("подсказка таблицы видна", page.locator("#tableEmpty").is_visible(), True)
    check("пустое состояние диаграммы видно", page.locator("#chartEmpty").is_visible(), True)
    check("итоги нулевые", page.locator("#sumIncome").inner_text(), "0,00 ₽")

    print("\n[15] Мобильная ширина 375×812")
    mob = browser.new_context(viewport={"width": 375, "height": 812})
    mp = mob.new_page()
    mp.goto(URL)
    mp.evaluate("() => localStorage.clear()")
    mp.reload()
    mp.select_option("#fType", "expense")
    mp.fill("#fAmount", "100")
    mp.fill("#fCategory", "Д" * 32)
    mp.evaluate("d => document.querySelector('#fDate').value = d", TODAY)
    mp.click("#addForm button[type=submit]")
    check("строка добавлена", mp.locator("#tbody tr").count(), 1)
    w = mp.evaluate("() => document.documentElement.scrollWidth")
    print(f"       ширина документа: {w} px при окне 375")
    check("нет горизонтальной прокрутки", w <= 375, True)
    mob.close()

    print("\n[16] Ошибки в консоли за весь прогон")
    check("консоль чиста", console, [])

    browser.close()

print("\n" + "=" * 60)
print(f"Проверок пройдено: {ok_count}, провалено: {len(fail)}")
if fail:
    print("Провалы:")
    for f in fail:
        print(f"  - {f}")
sys.exit(1 if fail else 0)
