# -*- coding: utf-8 -*-
"""Кожен клас у розмітці справді існує у скомпільованому css/style.css.

Навіщо. Tailwind збирається один раз (`npm run css`) і тільки з файлів, які
перелічені в `content` у tailwind.config.js. Класу, якого там не було, у
style.css немає — браузер його просто ігнорує, а сторінка виглядає «майже
правильно». 21-26.10.2026 на цьому тричі згоріла верстка міні-лендінга
`lp/probnyi-urok/`: папка `lp` взагалі не входить у `content`, тож `px-8` дав
нульовий падінг, `text-5xl` — звичайний кегль, `shadow-fox-lg` — жодної тіні.
Перед кожною здачею класи гріпали по style.css руками — тепер це робить скрипт.

Як працює: збирає імена класів зі селекторів style.css і fonts.css, розшифровує
CSS-екранування (`.md\:inline-flex`, `.bg-fox-500\/20`, кома в довільному
значенні записана як `\2c `), і порівнює з класами з усіх `class="..."`
сторінок. Клас, оголошений у власному `<style>` сторінки, відсутнім не
вважається.

У tools/audit/run.py НЕ входить свідомо: на 26.10.2026 сайт носить шість давно
мертвих класів (`card-lift` і `scrollbar-hide` — на всіх посадкових,
`bg-fox-500/6`, `bg-violet-500/4`, `nav:h-18` — на головній, `md:inline` — на
лендінгу), тож перевірка зараз червона. Це окрема правка верстки; поки вона не
зроблена, ламати гейт пушу не можна.

Запуск:  python tools/audit/classes.py
Код виходу: 1, якщо знайдено клас, якого немає в стилях.
"""
from __future__ import unicode_literals

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

B = chr(92)

# Ім'я класу в селекторі: літери, цифри, дефіс, екранований символ — і окремо
# шістнадцяткове екранування «\2c » (кома у довільних значеннях Tailwind).
SELECTOR = re.compile("[.]((?:[A-Za-z0-9_-]|" + B + B + "[0-9a-fA-F]{1,6} ?|" + B + B + ".)+)")
HEXESC = re.compile(B + B + "([0-9a-fA-F]{1,6}) ?")
SIMPLE = re.compile(B + B + "(.)")
STYLE = re.compile("<style[^>]*>(.*?)</style>", re.S)
CLASSATTR = re.compile('class="([^"]*)"')

SKIP_DIRS = {"__pycache__", "node_modules"}


def unescape(name):
    name = HEXESC.sub(lambda m: chr(int(m.group(1), 16)), name)
    return SIMPLE.sub(B + "1", name)


def selectors(text):
    return set(unescape(m.group(1)) for m in SELECTOR.finditer(text))


def pages():
    """Усі сторінки сайту: корінь, блог і лендінги під рекламу."""
    for name in sorted(os.listdir(ROOT)):
        if name.endswith(".html"):
            yield os.path.join(ROOT, name)
    for sub in ("blog", "lp"):
        for cur, dirs, files in os.walk(os.path.join(ROOT, sub)):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in sorted(files):
                if f.endswith(".html"):
                    yield os.path.join(cur, f)


def main():
    known = set()
    for rel in ("css/style.css", "css/fonts.css"):
        path = os.path.join(ROOT, rel)
        if os.path.exists(path):
            known |= selectors(io.open(path, encoding="utf-8").read())
    if not known:
        print("css/style.css не знайдено — спочатку npm run css")
        return 1

    missing = {}
    for path in pages():
        rel = os.path.relpath(path, ROOT).replace(B, "/")
        html = io.open(path, encoding="utf-8").read()
        local = set()
        for block in STYLE.findall(html):
            local |= selectors(block)
        used = set()
        for attr in CLASSATTR.findall(html):
            used.update(attr.split())
        for cls in sorted(used - known - local):
            missing.setdefault(cls, []).append(rel)

    if not missing:
        print("усі класи зі сторінок є в стилях")
        return 0

    print("класи, яких немає в стилях (браузер їх ігнорує):")
    for cls in sorted(missing, key=lambda c: (-len(missing[c]), c)):
        files = missing[cls]
        tail = "" if len(files) <= 3 else " і ще %d" % (len(files) - 3)
        print("  %-26s %3d стор.: %s%s" % (cls, len(files), ", ".join(files[:3]), tail))
    print("")
    print("лікується або прибраним класом, або файлом у content "
          "у tailwind.config.js + npm run css")
    return 1


if __name__ == "__main__":
    sys.exit(main())
