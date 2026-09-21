# -*- coding: utf-8 -*-
"""Перевіряє розмітку Schema.org на всіх сторінках.

Ловить те, що Google мовчки ігнорує, а ми не бачимо: зламаний JSON, посилання
@id у нікуди, обов'язкові поля без значень, розбіжність між canonical сторінки
та url у графі. Все це не дає помилки в браузері — сторінка просто не отримує
розширений сніпет, і зрозуміти чому без інструменту важко.

Запуск:  python tools/audit/schema.py
Код виходу: 1, якщо знайдено помилки.
"""
from __future__ import unicode_literals

import io
import json
import os
import re
import sys

try:
    from html import unescape
except ImportError:                                # Python 2
    from HTMLParser import HTMLParser
    unescape = HTMLParser().unescape

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BASE = "https://fluent-fox.site"

LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]+)"')

# Мінімум, без якого тип не має сенсу для пошуковика.
REQUIRED = {
    "Course": ["name", "description", "provider"],
    "Article": ["headline", "author", "datePublished", "publisher"],
    "FAQPage": ["mainEntity"],
    "BreadcrumbList": ["itemListElement"],
    "Person": ["name"],
    "WebPage": ["url", "name"],
    "Organization": ["name", "url"],
    "EducationalOrganization": ["name", "url"],
    "LocalBusiness": ["name", "address"],
    "Offer": ["price", "priceCurrency"],
    "ItemList": ["itemListElement"],
    "OfferCatalog": ["itemListElement"],
}


SCRIPTS_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
# Рядкові теги прибираємо без сліду, решту — з пробілом замість тега. Інакше
# «<em>teach</em>,» дає «teach ,», а в розмітці стоїть «teach,», і перевірка
# лається на розбіжність, якої насправді немає.
INLINE_RE = re.compile(r"</?(?:strong|em|b|i|span|a|small|sup|sub)\b[^>]*>", re.I)


def visible_text(html):
    """Текст, який бачить читач: без скриптів, тегів і значень атрибутів.

    `data-ru` зникає разом із тегом — і це навмисно. На українській сторінці
    видимий текст український, на російській російський, і питання FAQ має
    збігатися саме з тим, що на цій сторінці показано.
    """
    body = html[html.find("<body"):]
    body = SCRIPTS_RE.sub(" ", body)
    body = INLINE_RE.sub("", body)
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub(" ", body)))


def check_faq(rel, graph, html, errors):
    """Питання й відповіді в розмітці мають бути на сторінці слово в слово.

    Навіщо окрема перевірка. 21.09.2026 виявилося, що на головній FAQ жив у
    двох місцях — видимий текст у trans.json, ld+json руками в шаблоні, — і
    копії розійшлися: чотири відповіді з шести казали в розмітці одне, а на
    сторінці інше, в обох мовах. Google таку розмітку відкидає, а попередня
    перевірка бачила тільки те, що `mainEntity` не порожній.
    """
    faqs = [n for n in graph if "FAQPage" in types_of(n)]
    if len(faqs) > 1:
        errors.append((rel, "%d вузлів FAQPage — має бути один" % len(faqs)))
    if not faqs:
        return

    text = visible_text(html)
    ids = set(re.findall(r'\bid="([^"]+)"', html))

    for node in faqs:
        for q in node.get("mainEntity", []):
            name = re.sub(r"\s+", " ", q.get("name", "")).strip()
            answer = re.sub(r"\s+", " ",
                            (q.get("acceptedAnswer") or {}).get("text", "")).strip()
            if name and name not in text:
                errors.append((rel, "питання з розмітки немає у видимому тексті: «%s»"
                               % name[:70]))
            if answer and answer not in text:
                errors.append((rel, "відповідь у розмітці не збігається з текстом "
                                    "сторінки: «%s»" % name[:60]))
            url = q.get("url", "")
            anchor = url.partition("#")[2]
            if anchor and anchor not in ids:
                errors.append((rel, "url питання веде на якір, якого немає: #%s"
                               % anchor))


def types_of(node):
    t = node.get("@type")
    if isinstance(t, list):
        return t
    return [t] if t else []


def walk(node, fn, path="$"):
    if isinstance(node, dict):
        fn(node, path)
        for k, v in node.items():
            walk(v, fn, path + "." + k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, fn, "%s[%d]" % (path, i))


def collect_files():
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in (".git", "node_modules", "tools", "src", "__pycache__")]
        for f in files:
            if not f.endswith(".html") or f.startswith("_"):
                continue
            # .ru.html перевіряються нарівні з українськими: з 06.09.2026
            # у кожної російської сторінки власний граф — свої `@id` із
            # ?lang=ru, назви російською і inLanguage: ru. Доти вони несли
            # український граф, і перевірку «url = canonical» доводилося
            # на них не пускати.
            out.append(os.path.join(base, f))
    return sorted(out)


def main():
    files = collect_files()
    errors = []
    stats = {"pages": 0, "nodes": 0, "with_schema": 0}

    # Спершу збираємо всі оголошені @id по всьому сайту: посилання з однієї
    # сторінки на сутність з іншої (наприклад, вчитель у статті на вчителя
    # з головної) — це нормально й саме заради цього граф і робився.
    declared = set()
    parsed = {}
    for p in files:
        s = io.open(p, encoding="utf-8").read()
        blocks = LD_RE.findall(s)
        if not blocks:
            continue
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        parsed[rel] = []
        for b in blocks:
            try:
                data = json.loads(b)
            except ValueError as e:
                errors.append((rel, "JSON не розбирається: %s" % e))
                continue
            parsed[rel].append(data)
            for node in data.get("@graph", [data]):
                walk(node, lambda n, _: declared.add(n["@id"]) if "@id" in n else None)

    for rel, datas in sorted(parsed.items()):
        stats["pages"] += 1
        stats["with_schema"] += 1
        s = io.open(os.path.join(ROOT, rel), encoding="utf-8").read()
        canon = CANON_RE.search(s)
        canon = canon.group(1) if canon else None

        if len(datas) > 1:
            errors.append((rel, "%d окремих блоків ld+json — має бути один @graph"
                           % len(datas)))

        for data in datas:
            graph = data.get("@graph")
            if graph is None:
                errors.append((rel, "немає @graph — розмітка плоска"))
                graph = [data]
            if "@context" not in data:
                errors.append((rel, "немає @context"))

            for node in graph:
                stats["nodes"] += 1
                tps = types_of(node)
                if not tps:
                    errors.append((rel, "вузол без @type"))
                for t in tps:
                    for field in REQUIRED.get(t, []):
                        if not node.get(field):
                            errors.append((rel, "%s: немає обов'язкового поля «%s»"
                                           % (t, field)))

            # Посилання виду {"@id": "..."} мають кудись вести.
            def check_ref(n, path):
                if set(n.keys()) == {"@id"} and n["@id"] not in declared:
                    errors.append((rel, "посилання @id у нікуди: %s" % n["@id"]))
            for node in graph:
                walk(node, check_ref)

            check_faq(rel, graph, s, errors)

            # url сторінки в графі має збігатися з canonical.
            page = next((n for n in graph if "WebPage" in types_of(n)
                         or "CollectionPage" in types_of(n)), None)
            if page and canon and page.get("url") and page["url"] != canon:
                errors.append((rel, "url у WebPage (%s) не збігається з canonical (%s)"
                               % (page["url"], canon)))

    print("сторінок з розміткою: %d | вузлів: %d" % (stats["with_schema"], stats["nodes"]))

    pages_without = [os.path.relpath(p, ROOT).replace(os.sep, "/")
                     for p in files
                     if os.path.relpath(p, ROOT).replace(os.sep, "/") not in parsed]
    if pages_without:
        print("\nбез розмітки (може бути нормально — сторінки помилок, юридичні):")
        for f in pages_without:
            print("  ", f)

    if errors:
        print("\nПОМИЛКИ (%d):" % len(errors))
        for f, msg in errors:
            print("  %-46s %s" % (f, msg))
        return 1
    print("\nпомилок у розмітці немає")
    return 0


if __name__ == "__main__":
    sys.exit(main())
