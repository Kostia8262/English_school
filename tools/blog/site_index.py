# -*- coding: utf-8 -*-
"""Списки, у яких стаття має з'явитися після складання.

Сама стаття — це файл `blog/<slug>.html`, і його робить build.py. Але сторінка,
на яку ніхто не посилається, для пошуку не існує: посилання й свіжа карта сайту —
весь важіль, який у нас є. Тому кожну статтю треба вписати ще у чотири місця, і
всі чотири лежать не там, де текст:

  * `blog/index.html` → `const articles` (картки, які малює Alpine);
  * `blog/index.html` → `<noscript>` (той самий список для тих, хто не виконує JS,
    а це саме GPTBot, ClaudeBot і PerplexityBot);
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

def _js(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def render_articles_js(entries):
    out = ["const articles = ["]
    for e in entries:
        out.append("  {")
        out.append("    slug: '%s'," % _js(e["slug"]))
        out.append("    emoji: '%s', accent: '%s', catKey: '%s',"
                   % (_js(e["emoji"]), _js(e["accent"]), _js(e["catKey"])))
        out.append("    date: '%s', dateRu: '%s',"
                   % (_js(e["date"]), _js(e["dateRu"])))
        out.append("    readTime: '%s', readTimeRu: '%s',"
                   % (_js(e["readTime"]), _js(e["readTimeRu"])))
        out.append("    category: '%s', categoryRu: '%s',"
                   % (_js(e["category"]), _js(e["categoryRu"])))
        out.append("    title: '%s'," % _js(e["title"]))
        out.append("    titleRu: '%s'," % _js(e["titleRu"]))
        out.append("    excerpt: '%s'," % _js(e["excerpt"]))
        out.append("    excerptRu: '%s'," % _js(e["excerptRu"]))
        out.append("  },")
    out.append("];")
    return "\n".join(out)


def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def render_noscript_list(entries):
    items = "\n".join(
        '    <li><a href="%s">%s</a></li>' % (e["slug"], _esc(e["title"]))
        for e in entries)
    return "  <ul>\n%s\n  </ul>" % items


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

    html = _replace_once(html, r"const articles = \[.*?\n\];",
                         render_articles_js(entries), "const articles")
    html = _replace_once(html, r"  <ul>\n(?:    <li><a href=\"[^\"]+\.html\">.*?\n)+  </ul>",
                         render_noscript_list(entries), "noscript <ul>")

    m = re.search(r'<script type="application/ld\+json">(\{.*?"@type":\["CollectionPage".*?\})</script>',
                  html, re.S)
    if not m:
        raise ValueError("не знайдено JSON-LD лістингу")
    html = html[:m.start(1)] + render_jsonld(m.group(1), entries) + html[m.end(1):]

    io.open(path, "w", encoding="utf-8", newline="\n").write(html)


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
        r"  <url>\s*\n\s*<loc>" + re.escape(BLOG) + r"[^<]+\.html</loc>.*?</url>\n",
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
        "slug": e["slug"][:-5] if e["slug"].endswith(".html") else e["slug"],
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
