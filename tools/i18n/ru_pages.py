# -*- coding: utf-8 -*-
"""Складає російські версії сторінок окремими файлами.

Навіщо. Досі російська версія існувала лише в браузері: у розмітці лежить
українська, російська — в атрибутах `data-ru`, а підставляє її js/lang.js уже
після завантаження. Для читача без JS — GPTBot, ClaudeBot, PerplexityBot і
будь-хто, хто дивиться сирий HTML — `/tsiny?lang=ru` віддавав повністю
українську сторінку під українським `<title>`. Тобто російської версії для
індексації не існувало взагалі, хоч hreflang на неї й посилався.

У сусідній мережі («Мій комп'ютер») цю саму дірку закрив серверний рендер —
`server/i18n-ssr.js` застосовує applyLang('ru') до відправки сторінки. Тут
сервера немає: Hostinger віддає статику через Apache, а PHP працює тільки для
api/lead.php. Тому те саме робиться на етапі складання: поруч із `tsiny.html`
лягає `tsiny.ru.html`, а `.htaccess` віддає його на запит `/tsiny?lang=ru`.
Адреси, hreflang і перемикач мови не змінюються.

Це пост-процесор, а не окремий генератор: він бере вже зібраний український
файл і робить із ним рівно те, що зробив би js/lang.js. Один механізм на всі
три типи сторінок, і жодного другого джерела тексту, яке могло б розійтися з
першим.

Що застосовується:

  * data-ru               → текст вузла (сам атрибут із результату зникає)
  * data-ru-content       → content,      data-ru-alt         → alt
  * data-ru-aria          → aria-label,   data-ru-placeholder → placeholder
  * інлайновий скрипт підміни мета-тегів — виконується тут і з результату
    прибирається; невідома конструкція в ньому валить складання
  * <html lang>, canonical, og:url, og:locale, внутрішні посилання

Запуск:  python tools/i18n/ru_pages.py
Викликається також з tools/home/build.py і tools/landing/build.py.
"""
from __future__ import unicode_literals

import io
import os
import re
import sys

try:
    from html.parser import HTMLParser
except ImportError:                                    # Python 2
    from HTMLParser import HTMLParser

try:
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
except ImportError:                                    # Python 2
    from urlparse import urlsplit, urlunsplit, parse_qsl
    from urllib import urlencode

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

SITE = "https://fluent-fox.site"

# data-ru-* → атрибут, який бачить користувач. Дзеркало ATTR_MAP у js/lang.js:
# розійдуться — і російська версія почне відрізнятися від того, що бачить
# відвідувач, який усе-таки виконав скрипт.
ATTR_MAP = {
    "data-ru-content": "content",
    "data-ru-alt": "alt",
    "data-ru-aria": "aria-label",
    "data-ru-placeholder": "placeholder",
}

VOID = set("area base br col embed hr img input link meta param source track wbr".split())


# ── розбір документа на токени зі зсувами ────────────────────────────────────

class _Scanner(HTMLParser):
    """Ділить документ на токени й запам'ятовує, де кожен починається.

    Стандартний HTMLParser не віддає меж токена, а переписувати HTML регулярками
    по всьому файлу — це рано чи пізно зачепити `data-ru` всередині рядка в
    <script>. Тому позиція береться з getpos(), а кінець токена — це початок
    наступного: разом вони покривають файл без залишку."""

    def __init__(self, src):
        HTMLParser.__init__(self, convert_charrefs=False)
        self.src = src
        self.line_start = [0]
        for i, ch in enumerate(src):
            if ch == "\n":
                self.line_start.append(i + 1)
        self.toks = []
        self.feed(src)
        self.close()

    def _off(self):
        line, col = self.getpos()
        return self.line_start[line - 1] + col

    def _add(self, kind, tag=None, attrs=None):
        self.toks.append([self._off(), kind, tag, dict(attrs or [])])

    def handle_starttag(self, tag, attrs):
        self._add("void" if tag in VOID else "start", tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._add("void", tag, attrs)

    def handle_endtag(self, tag):
        self._add("end", tag)

    def handle_data(self, data):
        self._add("data")

    def handle_comment(self, data):
        self._add("comment")

    def handle_decl(self, decl):
        self._add("decl")

    def handle_pi(self, data):
        self._add("pi")

    def unknown_decl(self, data):
        self._add("decl")

    def handle_entityref(self, name):
        self._add("ref")

    def handle_charref(self, name):
        self._add("ref")


def esc_attr(s):
    return (s.replace("&", "&amp;").replace('"', "&quot;")
             .replace("<", "&lt;").replace(">", "&gt;"))


def esc_text(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Doc(object):
    """Документ, який правиться точковими замінами по зсувах."""

    def __init__(self, src, name):
        self.src = src
        self.name = name
        self.toks = _Scanner(src).toks
        for i, t in enumerate(self.toks):
            t.append(self.toks[i + 1][0] if i + 1 < len(self.toks) else len(src))
        self.edits = []
        self.tag_ops = {}

    # -- доступ ---------------------------------------------------------------

    def raw(self, i):
        return self.src[self.toks[i][0]:self.toks[i][4]]

    def find(self, sel):
        """Мінімальний селектор: `title`, `meta[name="description"]`."""
        m = re.match(r'^([a-z0-9]+)(?:\[([a-z-]+)="([^"]*)"\])?$', sel)
        if not m:
            raise SystemExit("%s: незрозумілий селектор %r" % (self.name, sel))
        tag, attr, val = m.group(1), m.group(2), m.group(3)
        for i, t in enumerate(self.toks):
            if t[1] in ("start", "void") and t[2] == tag:
                if attr is None or t[3].get(attr) == val:
                    return i
        return None

    def inner(self, i):
        """Межі вмісту елемента. Вкладені теги — помилка: js/lang.js на цьому
        місці робить textContent=..., тобто вкладену розмітку все одно знищив
        би, і мовчазна розбіжність між версіями гірша за падіння складання."""
        tag = self.toks[i][2]
        depth = 0
        for j in range(i + 1, len(self.toks)):
            kind, name = self.toks[j][1], self.toks[j][2]
            if kind == "start" and name == tag:
                depth += 1
            elif kind == "start":
                raise SystemExit("%s: усередині <%s data-ru> є <%s> — "
                                 "js/lang.js стер би цю розмітку"
                                 % (self.name, tag, name))
            elif kind == "end" and name == tag:
                if depth == 0:
                    return self.toks[i][4], self.toks[j][0]
                depth -= 1
        raise SystemExit("%s: не знайдено </%s>" % (self.name, tag))

    # -- правки ---------------------------------------------------------------

    def cut(self, start, end, text=""):
        self.edits.append((start, end, text))

    def set_text(self, i, text):
        a, b = self.inner(i)
        self.cut(a, b, esc_text(text))

    def retag(self, i, fn):
        """Переписує відкривальний тег функцією над його вихідним текстом.

        Правки копляться, а не пишуться одразу: той самий тег чіпають двічі —
        `<a data-ru="…" href="…">` спершу втрачає data-ru, потім отримує
        ?lang=ru у href. Дві окремі заміни того самого діапазону затерли б
        одна одну."""
        self.tag_ops.setdefault(i, []).append(fn)

    def render(self):
        for i, fns in self.tag_ops.items():
            start = self.toks[i][0]
            end = start + self.raw(i).index(">") + 1
            src = self.src[start:end]
            for fn in fns:
                src = fn(src)
            self.cut(start, end, src)

        out = self.src
        last = len(out) + 1
        for start, end, text in sorted(self.edits, reverse=True):
            if end > last:
                raise SystemExit("%s: правки перекриваються (%d..%d)"
                                 % (self.name, start, end))
            out = out[:start] + text + out[end:]
            last = start
        return out


# ── правка атрибутів у вихідному тексті тега ─────────────────────────────────

def _attr_re(name):
    return re.compile(r'\s+' + re.escape(name) + r'\s*=\s*"([^"]*)"', re.I)


def set_attr(tag_src, name, value):
    rx = _attr_re(name)
    if rx.search(tag_src):
        return rx.sub(lambda m: ' %s="%s"' % (name, esc_attr(value)), tag_src, count=1)
    # Новий атрибут дописуємо в кінець тега, а не на початок: порядок атрибутів
    # у зібраному HTML — не косметика, по ньому працюють точкові заміни в
    # генераторах.
    self_closing = tag_src.endswith("/>")
    head = tag_src[:-2 if self_closing else -1].rstrip()
    return '%s %s="%s"%s' % (head, name, esc_attr(value),
                             "/>" if self_closing else ">")


def del_attr(tag_src, name):
    return _attr_re(name).sub("", tag_src, count=1)


# ── крок 1: data-ru ──────────────────────────────────────────────────────────

def apply_data_ru(doc):
    n = 0
    for i, t in enumerate(doc.toks):
        if t[1] not in ("start", "void"):
            continue
        keys = [k for k in t[3] if k in ATTR_MAP or k == "data-ru"]
        if not keys:
            continue
        n += 1
        if "data-ru" in t[3]:
            if t[1] == "void":
                raise SystemExit("%s: data-ru на <%s> без вмісту"
                                 % (doc.name, t[2]))
            doc.set_text(i, t[3]["data-ru"])

        def clean(src, keys=keys, attrs=t[3]):
            for k in keys:
                if k != "data-ru":
                    src = set_attr(src, ATTR_MAP[k], attrs[k])
                src = del_attr(src, k)
            return src

        doc.retag(i, clean)
    return n


# ── крок 2: інлайновий скрипт підміни мета-тегів ─────────────────────────────
#
# Російські title і description живуть не в розмітці, а в скрипті, який
# спрацьовує до відмальовки (інакше в історії браузера й у метриці лишається
# український заголовок російської сторінки). Тут цей скрипт виконується на
# складанні, а з російського файлу прибирається — його робота вже зроблена.
#
# Розбір навмисно вузький: усе, що не збігається з відомою формою запису,
# валить складання. Тихо пропустити рядок означало б віддати російську
# сторінку з українським заголовком — рівно та біда, заради якої все це.

_STR = r"'((?:[^'\\]|\\.)*)'"
_SEL = r"'([^']*)'"

_GUARD = (r"^if\(new URLSearchParams\(location\.search\)\.get\('lang'\)"
          r"(?:!==|===)'ru'\)(?: return)?$")

_STATEMENTS = [
    (re.compile(r"^\(function\(\)$"), None),
    (re.compile(r"^\)\(\)$"), None),
    (re.compile(_GUARD), None),
    (re.compile(r"^document\.title=" + _STR + r"$"), ("title",)),
    (re.compile(r"^document\.documentElement\.lang=" + _STR + r"$"), ("lang",)),
    (re.compile(r"^(?:var\s+\w+=)?document\.querySelector\(" + _SEL
                + r"\)\.(textContent|content|href)=" + _STR + r"$"), ("sel",)),
    (re.compile(r"^var\s+(\w+)=document\.querySelector\(" + _SEL + r"\)$"), ("bind",)),
    (re.compile(r"^(?:if\(\w+\)\s*)?(\w+)\.(textContent|content|href)="
                + _STR + r"$"), ("var",)),
]

_PROP = {"textContent": "text", "content": "content", "href": "href"}


def _js_str(s):
    return (s.replace("\\'", "'").replace('\\"', '"')
             .replace("\\n", "\n").replace("\\\\", "\\"))


def _split_statements(js):
    """Ділить тіло скрипта на інструкції по ';', '{' і '}' поза рядками.

    Дужки блоку — теж межа: у головній підміна загорнута в `if(...){ … }`, і
    поділ лише по ';' склеїв би заголовок умови з першим присвоєнням.

    Коментарі знімаються тут же, одним проходом. Окремою регуляркою не можна:
    у рядку `'https://fluent-fox.site/?lang=ru'` є `//`, і регулярка на
    однорядковий коментар з'їдає половину адреси разом із кінцем інструкції."""
    out, cur, quote = [], [], None
    i, n = 0, len(js)
    while i < n:
        ch = js[i]
        if quote:
            cur.append(ch)
            if ch == "\\" and i + 1 < n:
                cur.append(js[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            cur.append(ch)
        elif js.startswith("//", i):
            i = js.find("\n", i)
            if i < 0:
                break
            continue
        elif js.startswith("/*", i):
            j = js.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        elif ch in ";{}":
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    out.append("".join(cur))
    return [re.sub(r"\s+", " ", s).strip() for s in out]


def read_meta_script(js, name):
    """Перетворює скрипт підміни мета-тегів на список операцій."""
    ops, bound = [], {}
    for st in _split_statements(js):
        if not st:
            continue
        for rx, kind in _STATEMENTS:
            m = rx.match(st)
            if not m:
                continue
            if kind is None:
                pass
            elif kind[0] == "title":
                ops.append(("text", "title", _js_str(m.group(1))))
            elif kind[0] == "lang":
                ops.append(("lang", None, _js_str(m.group(1))))
            elif kind[0] == "sel":
                ops.append((_PROP[m.group(2)], m.group(1), _js_str(m.group(3))))
            elif kind[0] == "bind":
                bound[m.group(1)] = m.group(2)
            elif kind[0] == "var":
                if m.group(1) not in bound:
                    raise SystemExit("%s: у скрипті мета-тегів змінна %s "
                                     "нізвідки" % (name, m.group(1)))
                ops.append((_PROP[m.group(2)], bound[m.group(1)],
                            _js_str(m.group(3))))
            break
        else:
            raise SystemExit("%s: у скрипті мета-тегів невідома інструкція:\n"
                             "  %s" % (name, st))
    return ops


def apply_meta_script(doc):
    """Знаходить скрипт підміни, застосовує його і прибирає з результату."""
    applied = 0
    for i, t in enumerate(doc.toks):
        if t[1] != "start" or t[2] != "script":
            continue
        a, b = doc.inner(i)
        js = doc.src[a:b]
        if "URLSearchParams" not in js or "'lang'" not in js:
            continue
        seen = {}
        for prop, sel, value in read_meta_script(js, doc.name):
            if prop == "lang":
                continue                      # виставляється окремо, для всіх
            seen[sel] = value
            j = doc.find(sel)
            if j is None:
                raise SystemExit("%s: скрипт мета-тегів звертається до %r, "
                                 "а такого елемента немає" % (doc.name, sel))
            if prop == "text":
                doc.set_text(j, value)
            else:
                doc.retag(j, lambda s, p=prop, v=value: set_attr(s, p, v))
        # Картка Twitter повторює og. У браузері вона лишалася українською: ні
        # цей скрипт, ні js/lang.js до twitter:* не доходять, бо клієнту вона
        # ні для чого. У статичному файлі виправити її нічого не коштує.
        for og, tw in (('meta[property="og:title"]', 'meta[name="twitter:title"]'),
                       ('meta[property="og:description"]',
                        'meta[name="twitter:description"]')):
            if og not in seen:
                continue
            j = doc.find(tw)
            if j is not None:
                doc.retag(j, lambda s, v=seen[og]: set_attr(s, "content", v))

        # прибираємо весь <script>…</script> разом із тегами
        end = doc.toks[i][0]
        for j in range(i + 1, len(doc.toks)):
            if doc.toks[j][1] == "end" and doc.toks[j][2] == "script":
                end = doc.toks[j][4]
                break
        doc.cut(doc.toks[i][0], end)
        applied += 1
    return applied


# ── крок 3: голова документа й посилання ─────────────────────────────────────

def with_lang(href, base=None):
    """Додає ?lang=ru, зберігаючи якір: половина посилань має #fragment, і
    дописаний у хвіст параметр опинився б усередині фрагмента."""
    u = urlsplit(href)
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
         if k != "lang"]
    q.append(("lang", "ru"))
    return urlunsplit((u.scheme, u.netloc, u.path, urlencode(q), u.fragment))


def is_internal(href):
    if not href or href.startswith("#"):
        return False
    if re.match(r"^(tel:|mailto:|javascript:)", href, re.I):
        return False
    u = urlsplit(href)
    if u.scheme and u.scheme not in ("http", "https"):
        return False
    if u.netloc:
        return u.netloc in ("fluent-fox.site", "www.fluent-fox.site")
    return True


def apply_head(doc):
    """Те саме, що робить applyRu() у js/lang.js для голови документа."""
    i = doc.find("html")
    if i is None:
        raise SystemExit("%s: немає <html>" % doc.name)
    doc.retag(i, lambda s: set_attr(s, "lang", "ru"))

    # Самопосилальні canonical і og:url. Без них російська версія каже Google
    # «канонічна — українська», і в російській видачі просто не з'являється.
    j = doc.find('link[rel="canonical"]')
    if j is not None:
        href = doc.toks[j][3].get("href", "")
        doc.retag(j, lambda s, h=href: set_attr(s, "href", with_lang(h)))
    j = doc.find('meta[property="og:url"]')
    if j is not None:
        url = doc.toks[j][3].get("content", "")
        doc.retag(j, lambda s, u=url: set_attr(s, "content", with_lang(u)))

    # ru_RU, а не ru_UA: месенджери розбирають лише перелік підтримуваних
    # локалей, і ru_UA у ньому немає — тег просто ігнорується.
    for sel, val in (('meta[property="og:locale"]', "ru_RU"),
                     ('meta[property="og:locale:alternate"]', "uk_UA")):
        j = doc.find(sel)
        if j is not None:
            doc.retag(j, lambda s, v=val: set_attr(s, "content", v))


def apply_links(doc):
    n = 0
    for i, t in enumerate(doc.toks):
        if t[1] not in ("start", "void") or t[2] != "a":
            continue
        href = t[3].get("href")
        if not is_internal(href):
            continue
        # Посилання, яке саме оголошує свою мову, не чіпаємо: це перемикач
        # мови. Дописати йому ?lang=ru означало б, що з російської сторінки
        # обидві кнопки ведуть на російську і повернутися нікуди.
        if "hreflang" in t[3]:
            continue
        # Перемикач мови — теж <a>, і саме йому ?lang=ru дописувати не можна:
        # кнопка «UA» веде на українську адресу й має нею лишитися. Дзеркало
        # тієї самої перевірки в applyRu() у js/lang.js.
        if "data-lang-btn" in t[3]:
            continue
        doc.retag(i, lambda s, h=href: set_attr(s, "href", with_lang(h)))
        n += 1
    return n


# ── складання ────────────────────────────────────────────────────────────────

def render(src, name):
    doc = Doc(src, name)
    stats = {
        "data-ru": apply_data_ru(doc),
        "скриптів мета": apply_meta_script(doc),
        "посилань": apply_links(doc),
    }
    apply_head(doc)
    out = doc.render()

    left = re.findall(r'\sdata-ru[a-z-]*="', out)
    if left:
        raise SystemExit("%s: у російській версії лишилося %d data-ru"
                         % (name, len(left)))
    return out, stats


def ru_path(path):
    return path[:-len(".html")] + ".ru.html"


def build(paths, quiet=False):
    for path in paths:
        name = os.path.relpath(path, ROOT).replace("\\", "/")
        src = io.open(path, encoding="utf-8").read()
        out, stats = render(src, name)
        dst = ru_path(path)
        io.open(dst, "w", encoding="utf-8", newline="\n").write(out)
        if not quiet:
            sys.stdout.write(
                "%-42s %6d байт  (%s)\n"
                % (os.path.relpath(dst, ROOT).replace("\\", "/"),
                   len(out.encode("utf-8")),
                   ", ".join("%s %d" % (k, v) for k, v in sorted(stats.items()))))


def site_pages():
    """Сторінки, у яких є російська версія. Слуги — з .htaccess, а не окремим
    списком: копія розходиться з оригіналом на першій же новій сторінці."""
    src = io.open(os.path.join(ROOT, ".htaccess"), encoding="utf-8").read()
    m = re.search(r"RewriteRule \^\(([^)]+)\)\$ \$1\.html", src)
    slugs = m.group(1).split("|") if m else []
    # Лістинг блогу теж тут: він єдиний у blog/, хто проходить через цей
    # пост-процесор. Статті складаються двома файлами в самому генераторі —
    # у них в абзацах є вкладена розмітка, а data-ru її не тримає.
    return ([os.path.join(ROOT, "index.html")]
            + [os.path.join(ROOT, s + ".html") for s in slugs]
            + [os.path.join(ROOT, "blog", "index.html")])


def main():
    build(site_pages())


if __name__ == "__main__":
    main()
