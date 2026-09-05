# -*- coding: utf-8 -*-
"""Шукає биті внутрішні посилання.

Сайт статичний, тож будь-яке посилання на неіснуючий файл — це 404, який
знайде Google раніше за нас. Перевірка дешева й має ганятися перед кожним
пушем.

Окремий випадок: Alpine-прив'язки `:href="lang==='ru' ? ... : ..."`. Це не
адреси, а вирази — їх пропускаємо, інакше половина звіту буде з вигаданих
шляхів на кшталт `/lang==='ru'`.

Запуск:  python tools/audit/links.py
Код виходу: 1, якщо знайдено биті посилання.
"""
from __future__ import unicode_literals

import io
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Адреси без .html, які віддає .htaccess внутрішнім переписуванням.
#
# Список читається з самого .htaccess, а не дублюється тут руками. Копія
# розходиться з оригіналом на першій же новій сторінці: слуг додали в правило
# перепису, забули додати сюди — і перевірка починає звітувати про «биті»
# посилання на сторінки, які насправді відкриваються.
def clean_urls():
    src = io.open(os.path.join(ROOT, ".htaccess"), encoding="utf-8").read()
    m = re.search(r"RewriteRule \^\(([^)]+)\)\$ \$1\.html", src)
    if not m:
        sys.stderr.write("links.py: у .htaccess не знайдено правило "
                         "безрозширенних адрес\n")
        return []
    return m.group(1).split("|")


CLEAN_URLS = clean_urls()

# Те, що існує, але файлом на диску не є.
VIRTUAL = {"/", "/blog/"}

# Пробіл на початку обов'язковий: він відсікає Alpine-прив'язки
# `:href="..."` і `x-bind:href="..."` — там усередині вираз, а не адреса.
LINK_RE = re.compile(r'\s(?:href|src)="([^"]+)"')
SKIP_PREFIX = ("http://", "https://", "//", "#", "data:", "tel:", "mailto:",
               "viber:", "javascript:")


def is_expression(value):
    """Залишковий захист: вираз, що прослизнув повз регулярку."""
    return any(ch in value for ch in "?'`") or "===" in value


def collect_files():
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in (".git", "node_modules", "tools", "src", "__pycache__")]
        for f in files:
            if f.endswith(".html") and not f.startswith("_"):
                out.append(os.path.join(base, f))
    return sorted(out)


def main():
    files = collect_files()

    existing = set(VIRTUAL)
    for p in files:
        rel = "/" + os.path.relpath(p, ROOT).replace(os.sep, "/")
        existing.add(rel)
    for slug in CLEAN_URLS:
        existing.add("/" + slug)
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in (".git", "node_modules", "tools", "src", "__pycache__")]
        for n in names:
            if not n.endswith(".html"):
                existing.add("/" + os.path.relpath(os.path.join(base, n), ROOT)
                             .replace(os.sep, "/"))

    broken, checked, skipped = [], 0, 0
    for p in files:
        rel_dir = os.path.dirname(os.path.relpath(p, ROOT)).replace(os.sep, "/")
        s = io.open(p, encoding="utf-8").read()
        for raw in sorted(set(LINK_RE.findall(s))):
            if raw.startswith(SKIP_PREFIX) or not raw:
                continue
            if is_expression(raw):
                skipped += 1
                continue
            target = raw.split("?")[0].split("#")[0]
            if not target:
                continue
            if not target.startswith("/"):
                target = "/" + (rel_dir + "/" if rel_dir else "") + target
            target = re.sub(r"/+", "/", target)
            checked += 1
            if target not in existing:
                broken.append((os.path.relpath(p, ROOT), raw, target))

    print("файлів: %d | посилань перевірено: %d | виразів пропущено: %d"
          % (len(files), checked, skipped))
    if broken:
        print("\nБИТІ ПОСИЛАННЯ (%d):" % len(broken))
        for f, raw, target in broken:
            print("  %-46s %s  ->  %s" % (f, raw, target))
        return 1
    print("битих посилань немає")
    return 0


if __name__ == "__main__":
    sys.exit(main())
