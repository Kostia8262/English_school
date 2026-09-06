# -*- coding: utf-8 -*-
"""Списки, у яких стаття має з'явитися після складання.

Сама стаття — це файл `blog/<slug>.html` (читач бачить її за адресою
без розширення, /blog/<slug>), і його робить build.py. Але сторінка,
на яку ніхто не посилається, для пошуку не існує: посилання й свіжа карта сайту —
весь важіль, який у нас є. Тому кожну статтю треба вписати ще у чотири місця, і
всі чотири лежать не там, де текст:

  * `blog/index.html` → картки статей у розмітці (раніше це був масив, по
    якому Alpine малював їх уже в браузері, плюс дубль у `<noscript>` для тих,
    хто скриптів не виконує; тепер картки просто лежать у сторінці);
  * `blog/index.ru.html` → те саме російською, збирається пост-процесором;
  * `blog/index.html` → JSON-LD: `blogPost` у CollectionPage і `itemListElement`
    у ItemList;
  * `sitemap.xml` → свій `<url>` з hreflang uk/ru/x-default.

Руками це чотири правки на статтю, і саме тому перша ж стаття, написана
конвеєром без цього модуля, стала б сиротою: файл на сервері є, а прийти на нього
нема звідки. Джерело правди — `listing.json`, звичайний список карток у тому ж
порядку, в якому вони на сторінці. Новий запис стає першим, наявний оновлюється
на місці — порядок старих статей ручний і навмисний, тож перетрушувати його
складання не має права.

Модуль нічого не робить сам: build.py збирає статті, оновлює `listing.json` і
кличе `apply(entries)`.
"""
from __future__ import unicode_literals

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
LISTING = os.path.join(HERE, "listing.json")

BASE = "https://fluent-fox.site"
BLOG = BASE + "/blog/"

# Ключі категорій, які розуміє перемикач на лістингу. Стаття з чужим ключем
# просто не потрапила б у жодну вкладку, окрім «Усі», — тому ключ звіряється, а
# не приймається на віру.
CATEGORY_KEYS = ("methods", "age", "exams", "format", "motivation", "choice")


def load_entries():
    return json.loads(io.open(LISTING, encoding="utf-8").read())


def save_entries(entries):
    io.open(LISTING, "w", encoding="utf-8", newline="\n").write(
        json.dumps(entries, ensure_ascii=False, indent=1) + "\n")


def upsert(entries, entry):
    """Новий запис — на початок, наявний — оновити на місці."""
    for i, e in enumerate(entries):
        if e["slug"] == entry["slug"]:
            entries[i] = entry
            return entries
    return [entry] + entries


# ── blog/index.html ──────────────────────────────────────────────────────────

CARD = """      <a href="/blog/%(slug)s" data-card-cat="%(cat_key)s" class="card-lift bg-white rounded-3xl overflow-hidden flex flex-col shadow-lg shadow-black/20">
        <div class="h-2 w-full bg-gradient-to-r %(accent)s"></div>
        <div class="p-6 flex flex-col flex-1">
          <div class="flex items-start justify-between mb-4">
            <span class="text-3xl leading-none" aria-hidden="true">%(emoji)s</span>
            <span class="bg-fox-50 text-fox-600 font-bold text-xs px-3 py-1 rounded-full"%(cat_ru)s>%(cat)s</span>
          </div>
          <h2 class="text-base font-black text-gray-900 leading-tight mb-3 flex-1"%(title_ru)s>%(title)s</h2>
          <p class="text-sm text-gray-500 leading-relaxed mb-4"%(excerpt_ru)s>%(excerpt)s</p>
          <div class="flex items-center justify-between pt-4 border-t border-gray-100 mt-auto">
            <div class="flex items-center gap-2 text-xs text-gray-400">
              <span%(date_ru)s>%(date)s</span>
              <span>·</span>
              <span%(read_ru)s>%(read)s</span>
            </div>
            <span class="text-fox-500 font-bold text-xs" data-ru="Читать →">Читати →</span>
          </div>
        </div>
      </a>"""


def _pair(uk, ru):
    """Український текст плюс `data-ru`, якщо російський відрізняється."""
    return (' data-ru="%s"' % _esc(ru)) if ru and ru != uk else ""


def render_cards(entries):
    """Картки статей готовою розміткою.

    Доти вони малювалися циклом Alpine по масиву `articles` у кінці файлу.
    Через це в лістингу не було жодного заголовка статті: ні для краулера без
    JS, ні для Google, який виконує скрипти, але спершу читає порожній HTML.
    Двадцять одна картка в розмітці коштує 12 КБ — дешевше, ніж масив, який
    вони заміняють."""
    out = []
    for e in entries:
        out.append(CARD % {
            "slug": e["slug"],
            "cat_key": e["catKey"],
            "accent": ("from-fox-500 to-fox-600" if e["accent"] == "fox"
                       else "from-violet-500 to-violet-600"),
            "emoji": e["emoji"],
            "cat": _esc(e["category"]), "cat_ru": _pair(e["category"], e["categoryRu"]),
            "title": _esc(e["title"]), "title_ru": _pair(e["title"], e["titleRu"]),
            "excerpt": _esc(e["excerpt"]),
            "excerpt_ru": _pair(e["excerpt"], e["excerptRu"]),
            "date": _esc(e["date"]), "date_ru": _pair(e["date"], e["dateRu"]),
            "read": _esc(e["readTime"]), "read_ru": _pair(e["readTime"], e["readTimeRu"]),
        })
    return "\n".join(out)


def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def render_jsonld(raw, entries):
    """Оновлює у графі лістингу тільки два вузли — перелік статей.

    Решта графа (CollectionPage, BreadcrumbList, описи) правиться руками і
    складанням не чіпається: тут міняються рівно ті місця, які залежать від
    складу блогу.
    """
    data = json.loads(raw)
    for node in data["@graph"]:
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if "Blog" in types or "CollectionPage" in types:
            node["blogPost"] = [
                {"@id": "%s%s#article" % (BLOG, e["slug"])} for e in entries]
        if "ItemList" in types:
            node["numberOfItems"] = len(entries)
            node["itemListElement"] = [
                {"@type": "ListItem", "position": n + 1,
                 "url": BLOG + e["slug"], "name": e["title"]}
                for n, e in enumerate(entries)]
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _replace_once(text, pattern, replacement, what):
    new, n = re.subn(pattern, lambda m: replacement, text, count=1, flags=re.S)
    if n != 1:
        raise ValueError("не знайдено рівно один блок для заміни: " + what)
    return new


def update_index(entries):
    path = os.path.join(ROOT, "blog", "index.html")
    html = io.open(path, encoding="utf-8").read()

    html = _replace_once(html, r"<!-- КАРТКИ -->.*?<!-- /КАРТКИ -->",
                         "<!-- КАРТКИ -->\n%s\n<!-- /КАРТКИ -->"
                         % render_cards(entries), "картки статей")

    m = re.search(r'<script type="application/ld\+json">(\{.*?"@type":\["CollectionPage".*?\})</script>',
                  html, re.S)
    if not m:
        raise ValueError("не знайдено JSON-LD лістингу")
    html = html[:m.start(1)] + render_jsonld(m.group(1), entries) + html[m.end(1):]

    io.open(path, "w", encoding="utf-8", newline="\n").write(html)

    # Російська версія лістингу — окремим файлом, тим самим пост-процесором, що
    # й для головної та посадкових.
    sys.path.insert(0, os.path.join(ROOT, "tools", "i18n"))
    import ru_pages
    ru_pages.build([path], quiet=True)


# ── sitemap.xml ──────────────────────────────────────────────────────────────

URL_TPL = """  <url>
    <loc>%(url)s</loc>
    <lastmod>%(mod)s</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
    <xhtml:link rel="alternate" hreflang="uk" href="%(url)s"/>
    <xhtml:link rel="alternate" hreflang="ru" href="%(url)s?lang=ru"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="%(url)s"/>
  </url>
"""


def update_sitemap(entries):
    """Переписує тільки блоки статей блогу, решту карти лишає як є."""
    path = os.path.join(ROOT, "sitemap.xml")
    xml = io.open(path, encoding="utf-8").read()

    # Адреса самого лістингу (/blog/) — не стаття, її не чіпаємо.
    article_url = re.compile(
        r"  <url>\s*\n\s*<loc>" + re.escape(BLOG) + r"[^<]+</loc>.*?</url>\n",
        re.S)
    xml, removed = article_url.subn("", xml)
    if not removed:
        raise ValueError("у sitemap.xml не знайдено жодної статті блогу — "
                         "формат змінився, складання зупинено")

    block = "".join(URL_TPL % {"url": BLOG + e["slug"],
                               "mod": e.get("modified") or e["published"]}
                    for e in entries)
    xml = _replace_once(xml, r"\n*</urlset>", "\n" + block + "\n</urlset>",
                        "</urlset>")
    io.open(path, "w", encoding="utf-8", newline="\n").write(xml)


# ── blog/articles.json ───────────────────────────────────────────────────────

def update_articles_json(entries):
    """Публічний перелік статей у тому ж вигляді, що й /api/articles у мережі.

    Потрібен не сайту, а конвеєру: щоденний знімок
    (`.github/workflows/refresh-content-snapshot.yml` у репозиторії
    my_computer_new) читає його, щоб знати дати публікацій і не давати агенту
    писати те, що вже є. Node-сайти мережі віддають те саме своїм API, у
    статичного сайту API немає — тож перелік просто лежить файлом.
    """
    path = os.path.join(ROOT, "blog", "articles.json")
    payload = {"articles": [{
        "slug": e["slug"],
        "title": e["title"],
        "title_ru": e["titleRu"],
        "excerpt": e["excerpt"],
        "category": e["category"],
        "publishedAt": e["published"],
        "url": BLOG + e["slug"],
    } for e in entries]}
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n")


# ── llms.txt ─────────────────────────────────────────────────────────────────

def update_llms(entries):
    """Перелік статей для ІІ-краулерів.

    GPTBot, ClaudeBot і PerplexityBot читають llms.txt раніше, ніж карту сайту,
    і саме звідси беруть, про що на сайті взагалі є текст. Заголовок і опис тут
    коротші за ті, що на картці: у статей, написаних руками, вони підібрані
    окремо і лежать у listing.json (`llmsTitle`, `llmsDesc`) — стаття з черги
    їх не має, тож бере власний заголовок і анонс.
    """
    path = os.path.join(ROOT, "llms.txt")
    txt = io.open(path, encoding="utf-8").read()
    lines = "\n".join(
        "- [%s](%s%s): %s" % (e.get("llmsTitle") or e["title"], BLOG, e["slug"],
                              e.get("llmsDesc") or e["excerpt"])
        for e in entries)
    new = re.sub(r"(## Статті блогу\n\n).*?(\n\n## )",
                 lambda m: m.group(1) + lines + m.group(2), txt, count=1, flags=re.S)
    if new == txt and lines not in txt:
        raise ValueError("не знайдено розділ «Статті блогу» в llms.txt")
    io.open(path, "w", encoding="utf-8", newline="\n").write(new)


def apply(entries):
    update_index(entries)
    update_sitemap(entries)
    update_articles_json(entries)
    update_llms(entries)
