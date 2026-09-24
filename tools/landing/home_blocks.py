# -*- coding: utf-8 -*-
"""Блоки головної, які стоять і на посадкових: контакти з формою, статті, модалка.

Власник попросив перенести їх «один в один». Найгірший спосіб це зробити —
скопіювати розмітку сюди: тоді той самий блок живе у двох файлах, і перша ж
правка на головній розійдеться з посадковими. Так уже було з FAQ, і саме тому
в проєкті правило «одне джерело на один текст».

Тому тут не копія, а витяг: модуль читає **зібраний** `index.html` і вирізає з
нього ті самі вузли за їхніми якорями. Головна лишається джерелом правди —
змінилося щось там, наступне складання посадкових підхопить зміну саму.

Через це порядок складання має значення: `tools/home/build.py` іде **перед**
`tools/landing/build.py`. Якщо `index.html` немає або якір не знайдено —
складання падає, а не тихо віддає сторінку без блоку.

Чого ми не тягнемо: геро, вікові картки, ціни, відгуки — у посадкових свої.
"""
from __future__ import unicode_literals

import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HOME = os.path.join(ROOT, "index.html")


def _read_home():
    # Аварійний клапан для роботи в кілька вкладок: якщо в робочій теці лежить
    # чужий незакомічений index.html, складати посадкові з нього не можна —
    # чужа правка поїде на прод раніше за автора. Тоді сюди підставляють
    # еталон, наприклад витягнутий із HEAD:
    #   git show HEAD:index.html > /tmp/head-index.html
    #   FLUENTFOX_HOME_HTML=/tmp/head-index.html python tools/landing/build.py
    override = os.environ.get("FLUENTFOX_HOME_HTML")
    if override:
        if not os.path.exists(override):
            raise SystemExit("FLUENTFOX_HOME_HTML вказує в нікуди: " + override)
        return io.open(override, encoding="utf-8").read()
    if not os.path.exists(HOME):
        raise SystemExit(
            "немає index.html — спершу `python tools/home/build.py`, "
            "бо посадкові беруть блок контактів, статей і модалку з нього")
    return io.open(HOME, encoding="utf-8").read()


def _slice_tag(html, start, tag):
    """Від позиції `start` до закриття тега, з урахуванням вкладених таких же."""
    open_t, close_t = "<" + tag, "</" + tag + ">"
    depth = 0
    pos = start
    while True:
        nxt_open = html.find(open_t, pos + 1)
        nxt_close = html.find(close_t, pos + 1)
        if nxt_close == -1:
            raise SystemExit("незакритий <%s> у index.html" % tag)
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            pos = nxt_open
        else:
            if depth == 0:
                return html[start:nxt_close + len(close_t)]
            depth -= 1
            pos = nxt_close


def _section_with(html, needle, tag="section"):
    """Вузол `tag`, усередині якого трапляється `needle`."""
    i = html.find(needle)
    if i == -1:
        raise SystemExit(
            "у index.html не знайдено «%s» — якір блоку змінився, "
            "полагодьте tools/landing/home_blocks.py" % needle[:60])
    start = html.rfind("<" + tag, 0, i)
    if start == -1:
        raise SystemExit("не знайдено початок <%s> для «%s»" % (tag, needle[:40]))
    return _slice_tag(html, start, tag)


_home = _read_home()

# Контакти з формою заявки. Форма тут справжня, а не посилання на /#form:
# так попросив власник. Наслідок, про який варто знати, — заявка тепер може
# прийти з будь-якої сторінки, і в CRM її відрізняє поле `page`, яке додає
# js/lead.js.
CONTACTS = _section_with(_home, 'id="contacts"')

# «Поради батькам від наших вчителів» — три статті й кнопка «Усі статті».
# Картки статичні, свого скрипта не мають; на головній їх складає
# tools/home/build.py з trans.json, тож і тут вони оновлюються самі.
ARTICLES = _section_with(_home, 'data-ru="Полезные статьи"')

# Модалка з другою копією форми: кнопка «Пробний урок» у шапці відкриває її
# замість переходу на /probnyi-urok. Поведінка — js/lead.js.
MODAL = _slice_tag(_home, _home.index('<div class="fixed inset-0 z-[100]'), "div")


# Три блоки, які на головній ідуть одразу за геро, — власник попросив
# поставити їх у тому ж порядку й на посадкових (24.09.2026).
#
# Смуга з цифрами й лондонська смуга — обидві на червоному тлі прапора
# (`bg-british`), тому шукаємо не за класом, а за текстом усередині.
STATS = _section_with(_home, 'учнів навчаються')
HOWITWORKS = _section_with(_home, 'Почніть навчання онлайн за 4 кроки')
# Лондонська смуга — не <section>, а <div class="bg-british"> між секціями,
# тому ріжемо її як div: _section_with знайшов би секцію вище й віддав зовсім
# інший блок (перевірено — віддавав «як це працює»).
_strip_i = _home.index('Speak the Language of the World')
STRIP = _slice_tag(_home, _home.rfind('<div class="bg-british', 0, _strip_i), "div")
