# -*- coding: utf-8 -*-
"""Проставляє <lastmod> у sitemap.xml за вмістом сторінки, а не за годинником.

Навіщо. Дати в карті відстали від сайту: `/pro-shkolu` втратив блок «Наші
вчителі» 06.09, а карта на нього казала 26.08. Google бере `lastmod` як
підказку, коли переобходити адресу, тож застаріла дата означає, що свіжа
правка доїде до індексу пізніше, ніж могла б.

Чому не «дата складання». Найпростіше було б писати сьогоднішнє число під час
кожної збірки — і саме це зіпсувало б карту остаточно. Складання запускається
після будь-якої дрібниці: підняли `CSS_VERSION`, додали російські файли, змінили
підвал. Якби кожен такий запуск переставляв усі чотирнадцять дат на сьогодні,
карта щоразу заявляла б «усі сторінки щойно змінилися», Google швидко навчився б
їй не вірити, і `lastmod` перестав би працювати взагалі. Ті самі граблі, через
які дата статті колись їхала від годинника складання, а не від джерела.

Тому дата тут прив'язана до вмісту. Для кожної адреси рахується відбиток
видимого тексту (плюс title, description і російські `data-ru`) і зберігається
у `state.json` поруч із датою. Наступне складання рахує відбиток заново: збігся
— дата лишається як була, скільки б разів не перескладали; розійшовся — дата
стає сьогоднішньою. Розмітка, версії ассетів і порядок атрибутів у відбиток не
входять, тож перекладання верстки дату не зрушить.

Межі відповідальності. Статті блогу сюди не входять: у них дата вже береться
з джерела статті (`site_index.update_sitemap`, поле `modified`), і другий
механізм на ту саму адресу означав би дві правди. Цей модуль займається всім
іншим у карті — головною, посадковими і лістингом `/blog/`.

Викликається з `tools/home/build.py` і `tools/landing/build.py`; обидва
оновлюють усю свою половину карти, тому досить будь-якого з них.

Запуск окремо (нічого не складає, лише звіряє):  python tools/sitemap/lastmod.py
"""
from __future__ import unicode_literals

import datetime
import hashlib
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
STATE_PATH = os.path.join(HERE, "state.json")
SITEMAP_PATH = os.path.join(ROOT, "sitemap.xml")

BASE = "https://fluent-fox.site"

# Стаття блогу — адреса виду /blog/<щось>.html. Сам лістинг /blog/ під це
# правило не підпадає і лишається за цим модулем.
ARTICLE = re.compile(r"^/blog/[^/]+\.html$")


# ── відбиток вмісту ──────────────────────────────────────────────────────────

def content_hash(html):
    """Відбиток того, що читає людина, без розмітки й версій ассетів.

    Береться чотири речі: title, meta description, український видимий текст і
    всі російські рядки з `data-ru*`. Російські важливі окремо, бо в розмітці
    вони живуть атрибутами й після зняття тегів зникли б — а це половина
    сторінки.
    """
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S)
    desc = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html, re.S)

    # data-ru, data-ru-content, data-ru-alt, data-ru-aria, data-ru-placeholder
    ru = re.findall(r'\sdata-ru(?:-[a-z]+)?="([^"]*)"', html)

    body = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    body = re.sub(r"<script.*?</script>", " ", body, flags=re.S)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S)
    body = re.sub(r"<svg.*?</svg>", " ", body, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)

    parts = [title.group(1) if title else "",
             desc.group(1) if desc else "",
             body,
             "\n".join(ru)]
    text = re.sub(r"\s+", " ", "\n".join(parts)).strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── карта адрес на файли ─────────────────────────────────────────────────────

def file_for(loc):
    """Локальний файл, з якого віддається ця адреса, або None."""
    path = loc[len(BASE):] if loc.startswith(BASE) else loc
    if path == "/":
        rel = "index.html"
    elif path == "/blog/":
        rel = os.path.join("blog", "index.html")
    elif path.endswith(".html"):
        rel = path.lstrip("/").replace("/", os.sep)
    else:
        # Посадкові стоять у карті без розширення — .htaccess віддає файл.
        rel = path.lstrip("/") + ".html"
    full = os.path.join(ROOT, rel)
    return full if os.path.exists(full) else None


def sitemap_locs(xml):
    """Адреси карти, крім статей блогу — ті веде site_index.update_sitemap.

    Коментарі знімаються першими: шапка карти пояснює, чому російська версія
    більше не стоїть окремим `<loc>`, і згадує цей тег дослівно. Без зняття
    коментарів пошук ліз через усю шапку до першого справжнього `</loc>` і
    з'їдав головну сторінку разом із поясненням.
    """
    body = re.sub(r"<!--.*?-->", " ", xml, flags=re.S)
    out = []
    for loc in re.findall(r"<loc>([^<]*)</loc>", body):
        loc = loc.strip()
        if not loc.startswith(BASE):
            raise ValueError("у sitemap.xml адреса не з нашого домену: %r" % loc)
        if not ARTICLE.match(loc[len(BASE):]):
            out.append(loc)
    return out


# ── стан ─────────────────────────────────────────────────────────────────────

def load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    with io.open(STATE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def save_state(state):
    with io.open(STATE_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(state, ensure_ascii=False, indent=2,
                            sort_keys=True))
        fh.write("\n")


# ── основна робота ───────────────────────────────────────────────────────────

def _set_lastmod(xml, loc, date):
    """Замінює <lastmod> у блоці <url> саме цієї адреси."""
    pattern = re.compile(
        r"(<loc>" + re.escape(loc) + r"</loc>\s*\n\s*<lastmod>)([^<]*)(</lastmod>)")
    new, n = pattern.subn(lambda m: m.group(1) + date + m.group(3), xml, count=1)
    if n != 1:
        raise ValueError("у sitemap.xml не знайдено <lastmod> для %s — "
                         "формат карти змінився, складання зупинено" % loc)
    return new


def _current_lastmod(xml, loc):
    m = re.search(r"<loc>" + re.escape(loc) + r"</loc>\s*\n\s*<lastmod>([^<]*)</lastmod>",
                  xml)
    return m.group(1).strip() if m else None


def refresh(today=None, quiet=False, dry_run=False):
    """Звіряє відбитки й переставляє дати тим адресам, де вміст змінився.

    Адреса, якої ще немає в state.json, дати не отримує: беремо ту, що вже
    стоїть у карті, і лише запам'ятовуємо відбиток. Інакше видалений state.json
    означав би, що наступне складання оголосить усі сторінки сайту зміненими
    сьогодні — рівно та брехня, заради якої цей модуль і писався. Так само
    поводиться щойно додана вручну адреса: дата лишається та, яку поставила
    людина, а стежити за нею починаємо з наступної правки.
    """
    today = today or datetime.date.today().isoformat()
    xml = io.open(SITEMAP_PATH, encoding="utf-8").read()
    state = load_state()

    changed, adopted, missing = [], [], []
    for loc in sitemap_locs(xml):
        path = file_for(loc)
        if path is None:
            missing.append(loc)
            continue
        digest = content_hash(io.open(path, encoding="utf-8").read())
        known = state.get(loc)
        if known is None:
            state[loc] = {"hash": digest,
                          "lastmod": _current_lastmod(xml, loc) or today}
            adopted.append(loc)
            continue
        if known.get("hash") == digest:
            continue
        state[loc] = {"hash": digest, "lastmod": today}
        xml = _set_lastmod(xml, loc, today)
        changed.append(loc)

    if missing:
        raise ValueError("у карті є адреси без файлу: %s" % ", ".join(missing))

    if (changed or adopted) and not dry_run:
        if changed:
            io.open(SITEMAP_PATH, "w", encoding="utf-8", newline="\n").write(xml)
        save_state(state)

    if not quiet:
        short = lambda l: l[len(BASE):] or "/"          # noqa: E731
        if adopted:
            print("lastmod: узято під нагляд без зміни дати (%d): %s"
                  % (len(adopted), ", ".join(short(l) for l in adopted)))
        if changed:
            print("lastmod оновлено (%d): %s"
                  % (len(changed), ", ".join(short(l) for l in changed)))
        elif not adopted:
            print("lastmod: вміст не змінювався, дати лишилися як були")
    return changed


if __name__ == "__main__":
    refresh(dry_run=True)
