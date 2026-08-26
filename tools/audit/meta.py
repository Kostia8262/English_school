# -*- coding: utf-8 -*-
"""Повнота мета-тегів і мовних пар на кожній сторінці.

Перевіряє те, що видно пошуковику ще до розбору вмісту: title, description,
canonical, hreflang, Open Graph, robots. Окремо — чи існує російський варіант
метаданих: сторінка, у якої hreflang обіцяє ru, а title лишається українським,
для пошуковика не має російської версії взагалі.

Саме така помилка була в десяти старих статтях блогу й у лістингу: видимий
текст перемикався, метадані — ні.

Запуск:  python tools/audit/meta.py
Код виходу: 1, якщо знайдено проблему.
"""
from __future__ import unicode_literals

import io
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BASE = "https://fluent-fox.site"

# Межі, у яких заголовок і опис не обрізаються у видачі.
TITLE_MAX = 62
DESC_MIN, DESC_MAX = 70, 175

# Сторінки, від яких метаданих не вимагаємо: вони під noindex.
NOINDEX_OK = {"404.html", "500.html", "503.html", "privacy.html", "offer.html",
              "terms.html", "returns.html", "cookies.html"}

problems = []
checked = 0


def meta(s, pat):
    m = re.search(pat, s)
    return m.group(1) if m else None


def check(path, rel):
    global checked
    s = io.open(path, encoding="utf-8").read()
    add = lambda msg: problems.append((rel, msg))

    robots = meta(s, r'<meta name="robots" content="([^"]*)"')
    if rel in NOINDEX_OK:
        if not robots or "noindex" not in robots:
            add("службова сторінка без noindex")
        return
    checked += 1

    title = meta(s, r"<title>(.*?)</title>")
    if not title:
        add("немає <title>")
    elif len(title) > TITLE_MAX:
        add("title %d знаків — обріжеться у видачі: «%s…»" % (len(title), title[:48]))

    desc = meta(s, r'<meta name="description" content="([^"]*)"')
    if not desc:
        add("немає description")
    elif not (DESC_MIN <= len(desc) <= DESC_MAX):
        add("description %d знаків (норма %d–%d)" % (len(desc), DESC_MIN, DESC_MAX))

    canon = meta(s, r'<link rel="canonical" href="([^"]*)"')
    if not canon:
        add("немає canonical")
    elif not canon.startswith(BASE):
        add("canonical веде на чужий домен: %s" % canon)

    langs = re.findall(r'<link rel="alternate" hreflang="([^"]*)"', s)
    for need in ("uk", "ru", "x-default"):
        if need not in langs:
            add("немає hreflang=%s" % need)

    for tag in ("og:title", "og:description", "og:url", "og:image", "og:type"):
        if 'property="%s"' % tag not in s:
            add("немає %s" % tag)
    if 'name="twitter:card"' not in s:
        add("немає twitter:card")

    if 'application/ld+json' not in s:
        add("немає розмітки ld+json")

    # Російські метадані. Підміна може бути записана трьома способами — на
    # головній через querySelector('title'), у статтях через document.title,
    # а на посадкових вона взагалі винесена в зовнішній /js/lang.js. Шукаємо
    # усі три, інакше перевірка сама себе обманює.
    external = '/js/lang.js' in s   # з версією в query або без неї
    swaps_title = bool(re.search(r"document\.title\s*=", s)) or         bool(re.search(r"querySelector\(\s*'title'\s*\)", s))
    swaps_lang = bool(re.search(r"documentElement\.lang\s*=\s*'ru'", s))

    if "ru" in langs and not (swaps_title or external):
        add("hreflang обіцяє ru, але title російською не підміняється")
    if not (swaps_lang or external):
        add("атрибут lang не перемикається на ru")


def main():
    files = ["index.html"]
    files += [f for f in sorted(os.listdir(ROOT))
              if f.endswith(".html") and f != "index.html" and not f.startswith("_")]
    files += ["blog/" + f for f in sorted(os.listdir(os.path.join(ROOT, "blog")))
              if f.endswith(".html")]

    for rel in files:
        p = os.path.join(ROOT, rel.replace("/", os.sep))
        if os.path.exists(p):
            check(p, rel)

    print("перевірено індексованих сторінок: %d (з %d файлів)" % (checked, len(files)))
    if problems:
        print("\nЗНАЙДЕНО: %d\n" % len(problems))
        cur = None
        for rel, msg in problems:
            if rel != cur:
                print("  %s" % rel)
                cur = rel
            print("      %s" % msg)
        return 1
    print("мета-теги: усе на місці")
    return 0


if __name__ == "__main__":
    sys.exit(main())
