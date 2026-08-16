"""Селекторы и действия в одном месте.

Селекторы построены по РАЗМЕТКЕ, КОТОРАЯ ЕСТЬ. Дописывать в объект `data-testid`
запрещено (AGENTS.md), и на исправленную копию запрет действует так же, как
на оригинал. Разметка и `id` в фиксе сохранены — ни один селектор менять не пришлось,
и это само по себе результат: ретест меряет поведение, а не совместимость селекторов.

Новое против `tests/helpers.py` — `delete_row()` и `import_csv()`. В фиксе оба
действия проходят через `confirm()`, а Playwright по умолчанию диалог **отклоняет**.
Без явной работы с диалогом тест удаляет запись, видит её на месте и сообщает
о провале фикса — при том что фикс сработал ровно так, как требует SPEC п. 10 и 13.
Ожидания при этом не смягчены: где раньше проверялось «действие выполнено»,
теперь проверяется «действие выполнено ПОСЛЕ согласия», а отказ проверяется отдельно.
"""
from playwright.sync_api import expect

from conftest import TODAY

SEL = {
    "type": "#fType",
    "amount": "#fAmount",
    "category": "#fCategory",
    "date": "#fDate",
    "comment": "#fComment",
    "submit": "#addForm button[type=submit]",
    "error": "#formError",
    "rows": "#tbody tr",
    "income": "#sumIncome",
    "expense": "#sumExpense",
    "balance": "#sumBalance",
    "legend": "#legend li",
    "chart_empty": "#chartEmpty",
    "table_empty": "#tableEmpty",
    "save": "#btnSave",
    "file": "#fileInput",
    "tab_expense": "#tabExpense",
    "tab_income": "#tabIncome",
}


def add(page, amount, category="Кафе", date=None, kind="expense", comment=""):
    """Заполнить форму и отправить. Дата по умолчанию — сегодня, считается, а не константа."""
    page.select_option(SEL["type"], kind)
    page.fill(SEL["amount"], amount)
    page.fill(SEL["category"], category)
    set_date(page, date if date is not None else TODAY.isoformat())
    page.fill(SEL["comment"], comment)
    page.click(SEL["submit"])


def set_date(page, iso):
    """input[type=date] заполняется значением, а не набором текста: раскладка не влияет.

    ВНИМАНИЕ, граница метода: браузер не принимает в `input[type=date]` заведомо
    несуществующую дату (`2026-02-30`) — поле остаётся пустым, и приложение отвечает
    «Укажите дату». Проверка «несуществующая дата» через форму поэтому неосуществима
    и вынесена на путь импорта, где значение доходит до приложения как есть.
    """
    page.evaluate("d => document.querySelector('#fDate').value = d", iso)


def row_count(page):
    return page.locator(SEL["rows"]).count()


def rows(page):
    return page.locator(SEL["rows"]).all_inner_texts()


def error_text(page):
    return page.locator(SEL["error"]).inner_text()


def totals(page):
    return {
        "income": page.locator(SEL["income"]).inner_text(),
        "expense": page.locator(SEL["expense"]).inner_text(),
        "balance": page.locator(SEL["balance"]).inner_text(),
    }


def legend(page):
    return [t.replace("\n", " / ") for t in page.locator(SEL["legend"]).all_inner_texts()]


NBSP = " "   # разделитель разрядов, который ставит toLocaleString


def money_to_float(text):
    """'1 200,50 ₽' -> 1200.5 . Неразрывные пробелы и запятая — часть форматирования.

    Неразрывный пробел записан escape-последовательностью, а не самим символом:
    при переносе файла он неотличим от обычного пробела на глаз, и потерять его
    молча — вопрос одного копирования (что и случилось при сборке этого набора).
    """
    cleaned = (text.replace(NBSP, "").replace(" ", "")
               .replace("₽", "").replace("−", "-").replace(",", "."))
    return float(cleaned)


def storage(page):
    return page.evaluate("() => localStorage.getItem('finance.csv')")


def assert_rejected(page, rows_before, totals_before):
    """Проверка отказа состоит из трёх частей, и первые две обязательны."""
    assert row_count(page) == rows_before, "появилась строка, хотя форма должна была отказать"
    assert totals(page) == totals_before, "итоги изменились, хотя форма должна была отказать"
    assert error_text(page).strip(), "нет сообщения об ошибке"


# --- действия, проходящие через confirm() -------------------------------------

def _answer_next_dialog(page, confirm):
    """Подписать одноразовый ответ на следующий `confirm()` и вернуть копилку сообщений.

    Обработчик, а НЕ `page.expect_event("dialog")`. Разница обошлась этому набору
    в один упавший прогон: `confirm()` блокирует страницу, пока на него не ответили,
    поэтому клик, вызвавший диалог, не возвращается — а `expect_event` ждёт завершения
    именно этого клика. Получается взаимная блокировка и падение по таймауту, неотличимое
    в выводе от «фикс не работает». Обработчик отвечает на диалог сразу и клик отпускает.
    """
    seen = []

    def handler(dialog):
        seen.append(dialog.message)
        dialog.accept() if confirm else dialog.dismiss()

    page.once("dialog", handler)
    return seen


def _wait_for(page, predicate, what, timeout=5000, step=50):
    """Дождаться условия опросом с крайним сроком. Не `sleep`: ждём ровно до наступления
    события, а не фиксированное время, и при неудаче падаем с внятным текстом."""
    waited = 0
    while waited < timeout:
        if predicate():
            return
        page.wait_for_timeout(step)
        waited += step
    raise AssertionError(f"не дождались: {what} (ждали {timeout} мс)")


def _settle(page):
    """Барьер, а не пауза. Ответ на `confirm()` возобновляет JS страницы, и перерисовка
    идёт синхронно внутри того же вызова. Один круговой запрос в страницу встаёт
    в очередь ЗА этим вызовом, поэтому после него DOM гарантированно перерисован."""
    page.evaluate("() => document.readyState")


def delete_row(page, index=0, confirm=True):
    """Удалить строку, явно ответив на подтверждение. Возвращает текст диалога."""
    seen = _answer_next_dialog(page, confirm)
    page.locator(SEL["rows"]).nth(index).locator("button").click()
    _wait_for(page, lambda: bool(seen), "подтверждение удаления (SPEC п.13)")
    _settle(page)
    return seen[0]


def import_csv(page, path, confirm=True):
    """Загрузить файл, который приложение обязано принять к рассмотрению.

    Ожидание диалога здесь — часть проверки: если подтверждение не запрошено,
    ожидание не дождётся и тест упадёт (SPEC п.10). Диалог приходит не сразу:
    файл сначала читается `FileReader`, поэтому ждём по условию, а не по факту вызова.
    """
    seen = _answer_next_dialog(page, confirm)
    page.set_input_files(SEL["file"], path)
    _wait_for(page, lambda: bool(seen), "подтверждение замены списка (SPEC п.10)")
    _settle(page)
    return seen[0]


def import_rejected_csv(page, path):
    """Загрузить файл, который обязан быть отклонён ДО всякого подтверждения.

    Диалога быть не должно: спрашивать «заменить ли записи» по файлу, который
    всё равно не будет применён, — значит предлагать выбор, которого нет.
    Возвращает список показанных диалогов; тест проверяет, что он пуст.
    """
    seen = []
    page.on("dialog", lambda d: (seen.append(d.message), d.dismiss()))
    page.set_input_files(SEL["file"], path)
    expect(page.locator(SEL["error"])).to_contain_text("Файл не загружен")
    return seen
