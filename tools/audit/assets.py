# -*- coding: utf-8 -*-
"""Одна версія ?v= на весь сайт — і жодного посилання на чужий CDN шрифтів.

Навіщо. `css/style.css` один, а ключ кешу до нього був у трьох генераторах
різний: головна просила `?v=20260906e`, посадкові — `?v=20260906`, статті
блогу — знову своє. Кеш при цьому річний і `immutable`, тож відвідувач, який
перейшов із головної на посадкову, качав той самий файл удруге. Тепер значення
живе в tools/assets.py, але частина сторінок (юридичні, 404/500/503, лістинг
блогу) не збирається генератором і правиться руками — саме там розбіжність і
з'явиться знову. Перевірка звіряє кожен `?v=` у репозиторії з tools/assets.py.

Друга перевірка — про шрифт. Nunito лежить у /fonts і підключається своїм
@font-face; посилання на fonts.googleapis.com або fonts.gstatic.com означає,
що якась сторінка знову блокує відмальовку запитом на чужий домен. CSP їх уже
не пропустить, тобто шрифт просто мовчки не завантажиться.

Запуск:  python tools/audit/assets.py
"""
from __future__ import unicode_literals

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from assets import ASSET_VERSION  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "__pycache__", "seo"}

# У шаблонах версія стоїть підстановкою, а не числом — це не розбіжність.
PLACEHOLDER = re.compile(r"^(%\(\w+\)s|\{\w+\}|%s)$")

VER = re.compile(r"""(?:/css/|/js/)[a-z0-9./-]+\?v=(%\(\w+\)s|\{\w+\}|%s|[^"'&\s)]+)""")
GOOGLE_FONTS = re.compile(r"fonts\.(?:googleapis|gstatic)\.com")

# Окремо — версія, яку php тримає константою, а не в рядку «?v=...».
# 21.09.2026 саме через це api/lead.php лишився на попередній версії:
# у джерелі там `?v={$v}`, і регулярка вище такого не бачить, тому бамп
# пройшов повз нього мовчки. Сторінка, яку він віддає відвідувачу без
# JS, тягнула старий style.css із чужим ключем кешу.
PHP_CONST = re.compile(r"""ASSET_VERSION\s*=\s*['\"]([^'\"]+)['\"]""")


def walk():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            # .php теж: сторінка, яку `api/lead.php` віддає відвідувачу без JS,
            # підключає style.css і носить версію руками — рівно як юридичні
            # сторінки й 404. Без цього рядка вона тихо розійшлася б із рештою
            # сайту при першому ж бампі.
            if f.endswith((".html", ".py", ".js", ".css", ".php")):
                yield os.path.join(base, f)


def main():
    bad = []
    for path in walk():
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        src = io.open(path, encoding="utf-8").read()

        if path.endswith(".php"):
            for m in PHP_CONST.finditer(src):
                if m.group(1) != ASSET_VERSION:
                    bad.append("%s: ASSET_VERSION = %s замість %s"
                               % (rel, m.group(1), ASSET_VERSION))

        for m in VER.finditer(src):
            v = m.group(1)
            if PLACEHOLDER.match(v) or v == ASSET_VERSION:
                continue
            bad.append("%s: ?v=%s замість %s\n    %s"
                       % (rel, v, ASSET_VERSION, m.group(0)))

        # Коментарі в аудиті й у самих файлах пояснюють, чому шрифт тепер свій;
        # шукаємо тільки те, що браузер справді піде завантажувати.
        if rel in ("tools/audit/assets.py", "css/fonts.css"):
            continue
        for m in re.finditer(r'(?:href|src|url)\s*=?\s*[("\']([^"\')]*)', src):
            if GOOGLE_FONTS.search(m.group(1)):
                bad.append("%s: шрифт із чужого домену — %s" % (rel, m.group(1)))

    if bad:
        sys.stdout.write("\n".join(bad) + "\n")
        sys.stdout.write("\nзнайдено проблем: %d\n" % len(bad))
        return 1
    sys.stdout.write("версія ассетів усюди %s, шрифт локальний\n" % ASSET_VERSION)
    return 0


if __name__ == "__main__":
    sys.exit(main())
