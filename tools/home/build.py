# -*- coding: utf-8 -*-
"""Складає index.html зі статичним текстом обома мовами.

Навіщо. До цього головна була єдиною сторінкою сайту, вміст якої існував лише
після запуску JS: текст лежав в об'єкті TRANS, а розмітка складалася з
`x-text` і 32 циклів `x-for`. У самому HTML статичного тексту було 4,5 тис.
знаків — переважно меню й підвал. Був ще `<noscript>` на 15,5 тис. знаків, але
Google індексує відмальований DOM, а в ньому `noscript` уже немає: цей блок
працював на GPTBot і ClaudeBot, а для Google не рахувався.

Наслідок було видно в Search Console: покази йшли на посадкові сторінки, де
текст лежить у розмітці, і майже не йшли на головну, яка бореться за найбільш
частотні запити.

Що робить цей скрипт. Бере `tools/home/template.html` — ту саму розмітку, що
й була, з тими самими класами — і розгортає її в статичний HTML:

  * `x-text="t.hero.title"`     → український текст у вузлі + `data-ru` з російським
  * `<template x-for=...>`      → готові вузли для кожного елемента масиву
  * `:class="COND ? 'a' : 'b'"` → обчислений клас для початкового стану
  * `x-show`, `@click`          → `data-*`-гачки, які підхоплює js/home.js

Контракт на виході той самий, що в посадкових сторінках: українська текстом,
російська в `data-ru`, перемикає js/lang.js. Alpine на сторінці більше немає.

Джерело тексту — tools/home/trans.json, витягнутий з колишнього об'єкта TRANS.

Запуск:  python tools/home/build.py
"""
from __future__ import unicode_literals

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

TEMPLATE = os.path.join(HERE, "template.html")
TRANS_JSON = os.path.join(HERE, "trans.json")
OUT = os.path.join(ROOT, "index.html")

# Версія в query до style.css і до скриптів. Піднімати руками разом зі
# складанням CSS — інакше повернені відвідувачі отримають старий файл.
ASSET_VERSION = "20260906e"

LANGS = ("uk", "ru")


# ── дрібні помічники ─────────────────────────────────────────────────────────

def esc_attr(s):
    return (s.replace("&", "&amp;").replace('"', "&quot;")
             .replace("<", "&lt;").replace(">", "&gt;"))


def esc_text(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Ctx(object):
    """Пара контекстів — український і російський — які йдуть разом.

    Кожен вираз обчислюється двічі, по разу на мову: з результатів виходить
    видимий текст і значення `data-ru`. Тримати їх окремо не можна — у циклах
    індекс має збігатися, інакше третій відгук отримає переклад четвертого.
    """

    def __init__(self, scopes):
        self.scopes = scopes            # {"uk": {...}, "ru": {...}}

    def child(self, values):
        """values: {"uk": {ім'я: значення}, "ru": {...}}"""
        out = {}
        for lang in LANGS:
            d = dict(self.scopes[lang])
            d.update(values[lang])
            out[lang] = d
        return Ctx(out)

    def get(self, lang):
        return self.scopes[lang]


# ── обчислення виразів Alpine ────────────────────────────────────────────────
#
# Вирази в шаблоні прості й перелічувані: доступ до поля, потрійний оператор,
# конкатенація рядків, порівняння. Замість повноцінного інтерпретатора JS тут
# переклад у Python — але з жорстким правилом: усе, чого перекладач не знає,
# валить складання. Мовчки залишити невідомий вираз означало б отримати
# сторінку, де замість тексту стоїть шматок коду.

_TERNARY_SPLIT = re.compile(r"^(?P<cond>.+?)\s*\?\s*(?P<yes>.+)$", re.S)


def _split_ternary(expr):
    """Ділить `A ? B : C` на три частини з урахуванням лапок і дужок."""
    depth = 0
    quote = None
    qmark = -1
    i = 0
    while i < len(expr):
        ch = expr[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "?" and depth == 0:
            qmark = i
            break
        i += 1
    if qmark < 0:
        return None

    depth = 0
    quote = None
    j = qmark + 1
    while j < len(expr):
        ch = expr[j]
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == ":" and depth == 0:
            return expr[:qmark], expr[qmark + 1:j], expr[j + 1:]
        j += 1
    raise ValueError("потрійний оператор без гілки else: " + expr)


class Dot(dict):
    """Словник із доступом через крапку — щоб `t.hero.title` працював як є.

    Перевизначено саме `__getattribute__`, а не `__getattr__`: у даних є ключ
    `items` (перелік того, що входить у віковий курс), і при звичайному
    `__getattr__` він програвав би однойменному методу словника — вираз
    `item in age.items` повертав би метод замість списку.
    """

    def __getattribute__(self, name):
        try:
            v = dict.__getitem__(self, name)
        except KeyError:
            return dict.__getattribute__(self, name)
        return wrap(v)

    def __getitem__(self, key):
        # Індексний доступ теж має повертати обгортку: у шаблоні є
        # `t.prog[tab.key].modules` — вибір програми за ключем вкладки.
        return wrap(dict.__getitem__(self, key))


class Num(int):
    """Число, яке при складанні з рядком поводиться як у JS.

    У шаблоні є `tab.total + '+ ' + t.prog.lessonsLabel` — JavaScript тихо
    зводить число до рядка, Python на цьому падає. Замість того щоб правити
    шаблон, зводимо самі.
    """

    def __add__(self, other):
        if isinstance(other, str):
            return str(int(self)) + other
        return Num(int(self) + other)

    def __radd__(self, other):
        if isinstance(other, str):
            return other + str(int(self))
        return Num(other + int(self))


def wrap(v):
    if isinstance(v, dict):
        return Dot(v)
    if isinstance(v, list):
        return [wrap(x) for x in v]
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return Num(v)
    return v


_KNOWN_FUNCS = {
    # Єдина функція шаблону, яку доводиться рахувати під час складання:
    # скільки сторінок виходить із відгуків по два на сторінку.
    "reviewPageCount()": lambda scope: (len(scope["t"]["reviews"]["list"]) + 1) // 2,
}


def _paren_span(e):
    """Межі першої групи в круглих дужках верхнього рівня, або None."""
    depth = 0
    quote = None
    start = -1
    for i, ch in enumerate(e):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == "(":
            if depth == 0:
                start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return start, i
    return None


def _to_python(expr):
    """Перекладає підмножину JS у Python. Невідоме — виняток."""
    e = expr.strip()

    tern = _split_ternary(e)
    if tern:
        cond, yes, no = tern
        return "((%s) if (%s) else (%s))" % (_to_python(yes), _to_python(cond),
                                             _to_python(no))

    # String(mi+1).padStart(2,'0') — єдине місце з форматуванням числа.
    m = re.match(r"^String\((.+?)\)\.padStart\((\d+),\s*'(.)'\)$", e)
    if m:
        return "str(%s).rjust(%s, '%s')" % (_to_python(m.group(1)),
                                            m.group(2), m.group(3))

    # Потрійний оператор усередині дужок: `(lang==='uk' ? 'A' : 'B') + ' →'`.
    # Верхній рівень тут без `?`, тому переклад робимо для вмісту дужок окремо.
    inner = _paren_span(e)
    if inner:
        start, end = inner
        if _split_ternary(e[start + 1:end]):
            return (_to_python(e[:start]) if e[:start].strip() else "") + \
                   "(" + _to_python(e[start + 1:end]) + ")" + \
                   (_to_python(e[end + 1:]) if e[end + 1:].strip() else "")

    for js, py in (("===", "=="), ("!==", "!="), ("&&", " and "), ("||", " or ")):
        e = e.replace(js, py)
    e = re.sub(r"([A-Za-z_][\w\.]*)\.length\b", r"len(\1)", e)
    e = re.sub(r"(?<![\w<>=!])!(?=[A-Za-z_(])", " not ", e)

    forbidden = re.search(r"=>|function|window\.|\{", e)
    if forbidden:
        raise ValueError("вираз поза підтримуваною підмножиною: " + expr)
    return e


def evaluate(expr, ctx, lang):
    scope = ctx.get(lang)
    key = expr.strip()
    if key in _KNOWN_FUNCS:
        return _KNOWN_FUNCS[key](scope)

    env = {k: wrap(v) for k, v in scope.items()}
    env["true"], env["false"], env["null"] = True, False, None
    try:
        return eval(_to_python(key), {"__builtins__": {"len": len, "str": str}}, env)
    except Exception as exc:                      # noqa: BLE001 — треба саме все
        raise ValueError("не обчислився вираз %r: %s" % (expr, exc))


def both(expr, ctx):
    """Значення виразу обома мовами."""
    return evaluate(expr, ctx, "uk"), evaluate(expr, ctx, "ru")


# ── таблиця інтерактиву ──────────────────────────────────────────────────────
#
# Кожен стан, який на сторінці змінюється кліком, описаний тут явно. Правило
# жорстке: вираз, що згадує будь-яку зі змінних стану, зобов'язаний бути в
# таблиці. Якщо ні — складання падає. Інакше живий перемикач тихо застигнув би
# у початковому положенні, і помітили б це вже відвідувачі.

STATE_VARS = ("scrolled", "menuOpen", "openFaq", "progTab", "openMod",
              "currentReview", "reviewPage", "modalOpen", "formData",
              "formErrors", "formLoading", "formSuccess", "formError")

_STATE_RE = re.compile(r"\b(%s)\b" % "|".join(STATE_VARS))


def mentions_state(expr):
    return bool(_STATE_RE.search(expr))


# @click → атрибут-гачок. Значення None означає «просто прибрати».
CLICK_HOOKS = {
    "setLang('uk')": ' data-lang-btn="uk"',
    "setLang('ru')": ' data-lang-btn="ru"',
    "modalOpen=true": ' data-modal="open"',
    "modalOpen=false": ' data-modal="close"',
    "modalOpen=false; formSuccess=false": ' data-modal="close" data-form-reset',
    "menuOpen=!menuOpen": ' data-menu="toggle"',
    "menuOpen=false": ' data-menu="close"',
    "menuOpen=false; modalOpen=true": ' data-menu="close" data-modal="open"',
    "prevReviewPage()": ' data-review="prev"',
    "nextReviewPage()": ' data-review="next"',
    "submitForm()": ' data-lead-form',
}

# x-show → (початковий стан, гачок). Стан: True — показати, False — сховати.
SHOW_HOOKS = {
    # Обидва стани меню позначені одним атрибутом із різним значенням:
    # закритим станом керує іконка-бургер, відкритим — і хрестик, і сама панель.
    "!menuOpen": (True, ' data-menu-when="closed"'),
    "menuOpen": (False, ' data-menu-when="open"'),
    "modalOpen": (False, ' data-modal-panel'),
    "formSuccess": (False, ' data-form-success'),
    "!formSuccess": (True, ' data-form-body'),
    "formErrors.name": (False, ' data-form-error-for="name"'),
    "formErrors.phone": (False, ' data-form-error-for="phone"'),
    "formError": (False, ' data-form-failed'),
    "formLoading": (False, ' data-submit-spinner'),
    "!formLoading": (True, ' data-submit-label'),
    "reviewPageCount() > 1": (True, ""),
}

# :class із участю стану → (яку гілку взяти на старті, гачок).
CLASS_HOOKS = {
    "(scrolled || menuOpen) ? 'shadow-md bg-white/95 backdrop-blur-sm' : 'bg-transparent'":
        ("no", ' data-header'),
    "lang==='uk' ? 'bg-white shadow text-fox-600' : 'text-gray-400 hover:text-gray-600'":
        ("yes", ""),
    "lang==='ru' ? 'bg-white shadow text-fox-600' : 'text-gray-400 hover:text-gray-600'":
        ("no", ""),
    "formErrors.name ? 'border-red-400 bg-red-50' : 'border-gray-200 bg-gray-50'":
        ("no", ' data-form-input="name"'),
    "formErrors.phone ? 'border-red-400 bg-red-50' : 'border-gray-200 bg-gray-50'":
        ("no", ' data-form-input="phone"'),
}

# Гачки, що залежать від змінної циклу: обчислюються під час розгортання.
# Ключ — вираз, значення — функція (ctx) → (показувати?, рядок атрибутів).
LOOP_SHOW = {
    "progTab===tab.key": lambda c: (evaluate("tab.key", c, "uk") == "age6",
                                    ' data-prog-panel="%s"' % evaluate("tab.key", c, "uk")),
    "openMod===mi": lambda c: (evaluate("mi", c, "uk") == 0,
                               ' data-mod-panel="%d"' % evaluate("mi", c, "uk")),
    "openFaq===i": lambda c: (False, ' data-faq-panel="%d"' % evaluate("i", c, "uk")),
}

LOOP_CLASS = {
    "progTab===tab.key ? 'bg-fox-500 text-white shadow-fox-sm' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-50'":
        lambda c: (evaluate("tab.key", c, "uk") == "age6",
                   ' data-prog-tab="%s"' % evaluate("tab.key", c, "uk")),
    "openMod===mi ? 'border-fox-300 shadow-fox-sm' : 'border-gray-200 hover:border-gray-300'":
        lambda c: (evaluate("mi", c, "uk") == 0, ' data-mod-card="%d"' % evaluate("mi", c, "uk")),
    "openMod===mi ? 'bg-fox-50' : 'hover:bg-gray-50'":
        lambda c: (evaluate("mi", c, "uk") == 0, ' data-mod-head="%d"' % evaluate("mi", c, "uk")),
    "openMod===mi ? 'bg-fox-500 shadow-fox-sm' : 'bg-gray-100'":
        lambda c: (evaluate("mi", c, "uk") == 0, ' data-mod-badge="%d"' % evaluate("mi", c, "uk")),
    "openMod===mi ? 'text-white' : 'text-gray-500'":
        lambda c: (evaluate("mi", c, "uk") == 0, ' data-mod-num="%d"' % evaluate("mi", c, "uk")),
    "openMod===mi ? 'text-gray-900' : 'text-gray-700'":
        lambda c: (evaluate("mi", c, "uk") == 0, ' data-mod-title="%d"' % evaluate("mi", c, "uk")),
    "openMod===mi ? 'rotate-180 text-fox-500' : 'text-gray-400'":
        lambda c: (evaluate("mi", c, "uk") == 0, ' data-mod-chevron="%d"' % evaluate("mi", c, "uk")),
    "openFaq===i ? 'rotate-45' : ''":
        lambda c: (False, ' data-faq-icon="%d"' % evaluate("i", c, "uk")),
    "reviewPage === i-1 ? 'bg-fox-500 w-5' : 'bg-gray-200 w-2'":
        lambda c: (evaluate("i", c, "uk") == 1,
                   ' data-review-dot="%d"' % (evaluate("i", c, "uk") - 1)),
}

LOOP_CLICK = {
    "progTab=tab.key; openMod=(window.innerWidth < 768 ? null : 0)":
        lambda c: ' data-prog-tab-btn="%s"' % evaluate("tab.key", c, "uk"),
    "openMod = openMod===mi ? null : mi":
        lambda c: ' data-mod-toggle="%d"' % evaluate("mi", c, "uk"),
    "openFaq = openFaq===i ? null : i":
        lambda c: ' data-faq-toggle="%d"' % evaluate("i", c, "uk"),
    "reviewPage = i - 1":
        lambda c: ' data-review-page="%d"' % (evaluate("i", c, "uk") - 1),
}

LOOP_DISABLED = {
    "reviewPage === 0": lambda c: True,
    "reviewPage >= reviewPageCount() - 1": lambda c: False,
    "formLoading": lambda c: False,
}


# ── розгортання циклів ───────────────────────────────────────────────────────

TEMPLATE_OPEN = re.compile(r"<template\b[^>]*>", re.S)
FOR_ATTR = re.compile(r'x-for="([^"]+)"')
LOOP_HEAD = re.compile(r"^\(?\s*([A-Za-z_]\w*)\s*(?:,\s*([A-Za-z_]\w*)\s*)?\)?\s+in\s+(.+)$",
                       re.S)


def find_template(s, start=0):
    """Знаходить перший <template> і його пару з урахуванням вкладеності."""
    m = TEMPLATE_OPEN.search(s, start)
    if not m:
        return None
    depth = 1
    i = m.end()
    while depth:
        nxt_open = s.find("<template", i)
        nxt_close = s.find("</template>", i)
        if nxt_close < 0:
            raise ValueError("незакритий <template>")
        if 0 <= nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 9
        else:
            depth -= 1
            i = nxt_close + 11
    return m.start(), m.end(), i - 11, i


def loop_items(expr, ctx):
    """Повертає список пар контекстів для кожної ітерації.

    `n in 5` і `_ in [1,2]` — суто декоративні повтори (зірочки рейтингу,
    дублювання стрічки для нескінченної анімації), значення там не потрібне.
    """
    e = expr.strip()
    if re.match(r"^\d+$", e):
        n = int(e)
        return [({"uk": i + 1, "ru": i + 1}) for i in range(n)]
    if re.match(r"^\[[\d,\s]+\]$", e):
        vals = json.loads(e)
        return [{"uk": v, "ru": v} for v in vals]
    if e == "reviewPageCount()":
        n = evaluate(e, ctx, "uk")
        return [{"uk": i + 1, "ru": i + 1} for i in range(n)]
    if e == "reviewSlice()":
        # На старті показано першу сторінку — два перші відгуки. Решта
        # сторінок живе в даних і підставляється скриптом.
        out = []
        for i in range(2):
            out.append({lang: evaluate("t.reviews.list", ctx, lang)[i] for lang in LANGS})
        return out

    uk = evaluate(e, ctx, "uk")
    ru = evaluate(e, ctx, "ru")
    if isinstance(uk, int) and not isinstance(uk, bool):
        # `s in review.stars` — число зірок у відгуку. Alpine на числі робить
        # прохід від 1 до n, значення при цьому не використовується.
        return [{"uk": i + 1, "ru": i + 1} for i in range(int(uk))]
    if len(uk) != len(ru):
        raise ValueError("різна довжина списків uk/ru у циклі: " + expr)
    return [{"uk": uk[i], "ru": ru[i]} for i in range(len(uk))]


def expand(s, ctx):
    """Рекурсивно розгортає цикли й обробляє атрибути в решті розмітки."""
    out = []
    pos = 0
    while True:
        found = find_template(s, pos)
        if not found:
            out.append(resolve(s[pos:], ctx))
            break
        o_start, o_end, c_start, c_end = found
        out.append(resolve(s[pos:o_start], ctx))

        tag = s[o_start:o_end]
        inner = s[o_end:c_start]
        m = FOR_ATTR.search(tag)
        if not m:
            raise ValueError("<template> без x-for: " + tag[:80])
        head = LOOP_HEAD.match(m.group(1).strip())
        if not head:
            raise ValueError("не розібрався заголовок циклу: " + m.group(1))
        var, idx, src = head.group(1), head.group(2), head.group(3)

        for n, item in enumerate(loop_items(src, ctx)):
            values = {lang: {var: item[lang]} for lang in LANGS}
            if idx:
                for lang in LANGS:
                    values[lang][idx] = n
            out.append(expand(inner, ctx.child(values)))
        pos = c_end
    return "".join(out)


# ── обробка атрибутів ────────────────────────────────────────────────────────

TAG_RE = re.compile(r"<([a-zA-Z][\w-]*)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)(/?)>", re.S)
ATTR_RE = re.compile(r"""\s+([:@]?[\w.:\-]+)(?:="([^"]*)")?""")

DROP_ATTRS = ("x-data", "x-cloak", "x-init", "x-effect", "x-ref", ":key",
              "x-transition")

# Порожні елементи HTML: у них немає вмісту, отже x-text до них не приходить.
VOID = {"br", "img", "input", "hr", "meta", "link", "path", "polygon", "circle",
        "rect", "use", "stop", "source", "area", "col", "embed", "track", "wbr"}


ANY_TAG_RE = re.compile(
    r"<(/)?([a-zA-Z][\w-]*)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)(/?)>", re.S)


def resolve(fragment, ctx):
    """Прибирає директиви Alpine з тегів і вписує текст обома мовами.

    Вміст елемента з `x-text` викидається: Alpine так само затирав його своїм
    значенням, тож у розмітці там лежала лише українська заглушка. Тепер на її
    місце стає обчислений текст, а російський їде в `data-ru`.
    """
    out = []
    pos = 0
    skip_tag = None         # ім'я тега, вміст якого викидаємо
    skip_depth = 0

    for m in ANY_TAG_RE.finditer(fragment):
        closing, name, attrs, selfclose = (m.group(1), m.group(2),
                                           m.group(3), m.group(4))

        if skip_tag is not None:
            # Усе між відкриттям і закриттям елемента з x-text пропускаємо.
            if name == skip_tag and not selfclose and name not in VOID:
                skip_depth += -1 if closing else 1
                if skip_depth == 0:
                    out.append("</%s>" % name)
                    skip_tag = None
            pos = m.end()
            continue

        out.append(fragment[pos:m.start()])
        pos = m.end()

        if closing:
            out.append("</%s>" % name)
            continue

        new_attrs, text = process_attrs(attrs, ctx)
        out.append("<%s%s%s>" % (name, new_attrs, "/" if selfclose else ""))

        if text is not None:
            if name in VOID or selfclose:
                raise ValueError("x-text на порожньому елементі <%s>" % name)
            out.append(esc_text(text[0]))
            skip_tag = name
            skip_depth = 1

    if skip_tag is not None:
        raise ValueError("не закрився елемент із x-text: <%s>" % skip_tag)
    out.append(fragment[pos:])
    return "".join(out)


def process_attrs(attrs, ctx):
    """Повертає (рядок атрибутів, текст або None)."""
    parts = []
    text = None
    classes = []
    base_class = None
    hooks = ""

    for m in ATTR_RE.finditer(attrs):
        name, value = m.group(1), m.group(2)
        if value is None:
            value = ""

        if any(name == d or name.startswith(d) for d in DROP_ATTRS):
            continue

        if name == "class":
            base_class = value
            continue

        if name == "x-text":
            uk, ru = both(value, ctx)
            text = (str(uk), str(ru))
            continue

        if name == "x-model":
            parts.append(' name="%s"' % value.split(".")[-1])
            continue

        if name == "x-show":
            show, hook = _resolve_show(value, ctx)
            hooks += hook
            if not show:
                parts.append(" hidden")
            continue

        if name == ":class":
            cls, hook = _resolve_class(value, ctx)
            classes.append(cls)
            hooks += hook
            continue

        if name == ":disabled":
            if _resolve_disabled(value, ctx):
                parts.append(" disabled")
            continue

        if name == ":style":
            # Єдине :style у шаблоні — паралакс декоративних деталей у герої.
            # Множники переїжджають у data-атрибут, зсув рахує js/home.js.
            mm = re.match(r"^`transform:translate\(\$\{px \* (-?\d+)\}px, "
                          r"\$\{py \* (-?\d+)\}px\)`$", value.strip())
            if mm:
                hooks += ' data-parallax-xy="%s,%s"' % (mm.group(1), mm.group(2))
                continue
            # Решта :style не залежить від стану — рахуємо одразу.
            uk, _ru = both(value, ctx)
            parts.append(' style="%s"' % esc_attr(str(uk)))
            continue

        if name == ":href":
            uk, _ru = both(value, ctx)
            parts.append(' href="%s"' % esc_attr(str(uk)))
            continue

        if name.startswith("@"):
            hooks += _resolve_click(name, value, ctx)
            continue

        if name.startswith(":"):
            uk, ru = both(value, ctx)
            plain = name[1:]
            parts.append(' %s="%s"' % (plain, esc_attr(str(uk))))
            if str(ru) != str(uk):
                parts.append(' data-ru-%s="%s"' % (plain, esc_attr(str(ru))))
            continue

        if value:
            parts.append(' %s="%s"' % (name, value))
        else:
            parts.append(" " + name)

    if base_class is not None or classes:
        merged = " ".join(x for x in ([base_class] if base_class else []) + classes if x)
        parts.insert(0, ' class="%s"' % merged)

    if text is not None and text[0] != text[1]:
        parts.append(' data-ru="%s"' % esc_attr(text[1]))

    return "".join(parts) + hooks, text


def _resolve_show(expr, ctx):
    e = expr.strip()
    if e in LOOP_SHOW:
        return LOOP_SHOW[e](ctx)
    if e in SHOW_HOOKS:
        return SHOW_HOOKS[e]
    if mentions_state(e):
        raise ValueError("x-show зі станом поза таблицею: " + e)
    return bool(evaluate(e, ctx, "uk")), ""


def _resolve_class(expr, ctx):
    e = expr.strip()
    if e in LOOP_CLASS:
        take_yes, hook = LOOP_CLASS[e](ctx)
        yes, no = _branches(e)
        return (yes if take_yes else no), hook
    if e in CLASS_HOOKS:
        which, hook = CLASS_HOOKS[e]
        yes, no = _branches(e)
        return (yes if which == "yes" else no), hook
    if mentions_state(e):
        raise ValueError(":class зі станом поза таблицею: " + e)
    value = evaluate(e, ctx, "uk")
    return (value or ""), ""


def _branches(expr):
    cond, yes, no = _split_ternary(expr)
    return _literal(yes), _literal(no)


def _literal(part):
    p = part.strip()
    if (p.startswith("'") and p.endswith("'")) or (p.startswith('"') and p.endswith('"')):
        return p[1:-1]
    raise ValueError("очікувався рядковий літерал у гілці: " + part)


def _resolve_disabled(expr, ctx):
    e = expr.strip()
    if e in LOOP_DISABLED:
        return LOOP_DISABLED[e](ctx)
    if mentions_state(e):
        raise ValueError(":disabled зі станом поза таблицею: " + e)
    return bool(evaluate(e, ctx, "uk"))


def _resolve_click(name, value, ctx):
    if name.startswith("@click.self"):
        return ' data-modal-backdrop' if value.strip() == "modalOpen=false" else ""
    if name == "@click.stop":
        return ""
    if name.startswith("@mousemove"):
        # Паралакс у герої: сам обробник живе в js/home.js, тут лишається лише
        # позначка контейнера, відносно якого рахується зсув.
        return ' data-parallax'
    if name.startswith("@input"):
        # Підсвітку помилки знімає js/home.js за data-form-input — окремий
        # обробник на кожне поле не потрібен.
        return ""
    if name.startswith("@submit"):
        if value.strip() != "submitForm()":
            raise ValueError("несподіваний обробник submit: " + value)
        return ' data-lead-form'
    v = value.strip()
    if v in LOOP_CLICK:
        return LOOP_CLICK[v](ctx)
    if v in CLICK_HOOKS:
        return CLICK_HOOKS[v]
    raise ValueError("обробник кліку поза таблицею: " + v)


# ── збирання сторінки ────────────────────────────────────────────────────────

def strip_alpine_runtime(head):
    """Прибирає з <head> усе, що стосувалося Alpine."""
    head = re.sub(
        r'\s*<!-- ═══ Alpine\.js CDN ═══ -->\s*<script defer src="https://unpkg\.com/alpinejs[^"]*"></script>',
        "", head)
    # Запобіжник на випадок ненавантаженого Alpine більше не потрібен: текст
    # тепер лежить у розмітці й видно його без жодного скрипта.
    head = re.sub(r"\s*<script>\s*/\* Запобіжник.*?</script>", "", head, flags=re.S)
    head = head.replace('href="/css/style.css?v=20260826"',
                        'href="/css/style.css?v=%s"' % ASSET_VERSION)
    return head


def main():
    src = io.open(TEMPLATE, encoding="utf-8").read()
    trans = json.load(io.open(TRANS_JSON, encoding="utf-8"))

    ctx = Ctx({lang: {"t": trans[lang], "lang": lang} for lang in LANGS})

    # Саме за x-data, а не за першим `<body`: у коментарі в <head> згадується
    # `<body>` текстом, і пошук по голому тегу різав файл на сто рядків раніше.
    m = re.search(r"<body\s[^>]*x-data[^>]*>", src)
    if not m:
        raise SystemExit("у шаблоні не знайдено <body x-data=...>")
    head = src[:m.start()]
    body = src[m.end():src.rindex("</body>")]

    # Прибираємо блок зі скриптом TRANS + app(): даних у розмітці тепер
    # достатньо, а поведінку взяв на себе js/home.js.
    body = re.sub(r"<script>\s*/\* ─+\s*TRANSLATIONS.*?</script>", "", body,
                  flags=re.S)
    # Дублікат тексту в <noscript> більше не потрібен — увесь вміст сторінки
    # і так статичний. GTM-iframe у власному <noscript> лишається.
    body = re.sub(r"<noscript>\s*<main .*?</noscript>", "", body, flags=re.S)

    rendered = expand(body, ctx)

    left = re.findall(r"x-(?:text|for|show|data|model)=|@click|:class=", rendered)
    if left:
        raise SystemExit("у результаті лишилися директиви Alpine: %s"
                         % sorted(set(left)))

    head = strip_alpine_runtime(head)
    scripts = ('\n<script src="/js/lang.js?v=%s" defer></script>'
               '\n<script src="/js/home.js?v=%s" defer></script>\n'
               % (ASSET_VERSION, ASSET_VERSION))

    out = ('%s<body class="font-sans antialiased text-gray-800 bg-cream">%s%s</body>\n</html>\n'
           % (head, rendered.rstrip(), scripts))

    io.open(OUT, "w", encoding="utf-8", newline="\n").write(out)

    static = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "",
                                            out, flags=re.S))
    static = re.sub(r"\s+", " ", static).strip()
    sys.stdout.write("index.html: %d байт, статичного тексту %d знаків, "
                     "data-ru %d\n"
                     % (len(out.encode("utf-8")), len(static),
                        out.count("data-ru=")))

    # Російська версія — окремим файлом, одразу тут: складати її окремою
    # командою означає рано чи пізно лишити на сайті вчорашню.
    sys.path.insert(0, os.path.join(ROOT, "tools", "i18n"))
    import ru_pages
    ru_pages.build([OUT])

    # Дата головної в карті сайту. Модуль проходить усю карту, крім статей
    # блогу — у тих дата береться з джерела статті і має власного господаря
    # (site_index.update_sitemap). Переставляє тільки те, де змінився вміст.
    sys.path.insert(0, os.path.join(ROOT, "tools", "sitemap"))
    import lastmod
    lastmod.refresh()


if __name__ == "__main__":
    main()
