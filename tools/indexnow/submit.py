# -*- coding: utf-8 -*-
"""Повідомити пошуковим системам, що адреса змінилася — протокол IndexNow.

Навіщо. Пошук ChatGPT спирається на індекс Bing, а не Google. За тринадцять
місяців у нас нуль сесій із Bing і нуль переходів із ChatGPT, Perplexity та
Gemini — при тому що robots.txt їх усіх пускає, а текст лежить у HTML без
скриптів. Обхід — єдина ланка цього ланцюга, на яку статичний сайт узагалі може
вплинути, і IndexNow саме вона: один POST замість чекання, поки бот зайде сам.

Bing, Yandex, Seznam і Naver ділять один пул — подавати треба один раз, у
будь-яку з точок входу.

    python tools/indexnow/submit.py --all          # усі адреси з карти сайту
    python tools/indexnow/submit.py --dry-run --all
    python tools/indexnow/submit.py https://fluent-fox.site/tsiny
    python tools/indexnow/submit.py --changed origin/master..HEAD

Ключ лежить у корені сайта окремим файлом `<ключ>.txt`, у якому написаний сам
ключ, — так вимагає протокол: сервіс качає цей файл і звіряє. Ключ не секрет,
його видно всім, тому він і живе в цьому публічному репозиторії. Другої копії
ключа ніде немає навмисно: єдине джерело правди — той самий файл, який реально
віддається з сайта.
"""
from __future__ import unicode_literals

import io
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOST = "fluent-fox.site"
ORIGIN = "https://" + HOST
ENDPOINT = "https://api.indexnow.org/indexnow"
# Протокол дозволяє 10 000 адрес за раз; у нас їх сорок із чимось, але межа
# хай буде видима в коді, а не з'ясується колись у відповіді 413.
BATCH = 10000

SITEMAP_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "xhtml": "http://www.w3.org/1999/xhtml",
}


def find_key():
    """Ключ — ім'я файла в корені, яке збігається з його вмістом.

    Перевіряємо саме збіг, а не просто наявність файла: якщо колись ключ
    перевипустять і перейменують файл, забувши поправити вміст, сервіс відповість
    403, і причина буде неочевидна. Хай ламається тут і словами.
    """
    found = []
    for name in os.listdir(ROOT):
        m = re.match(r"^([0-9a-f]{8,128})\.txt$", name)
        if not m:
            continue
        body = io.open(os.path.join(ROOT, name), encoding="utf-8").read().strip()
        if body == m.group(1):
            found.append(m.group(1))
        else:
            sys.exit("Файл %s не збігається зі своїм вмістом — ключ недійсний." % name)
    if not found:
        sys.exit("Ключа IndexNow немає: у корені бракує файла <ключ>.txt.")
    if len(found) > 1:
        sys.exit("У корені кілька ключів IndexNow: %s. Лишіть один." % ", ".join(found))
    return found[0]


def urls_from_sitemap():
    """Адреси з карти сайту, разом із російськими версіями.

    Російська версія — не окремий запис `<loc>`, а `xhtml:link` у тій самій
    парі: адреса одна, з `?lang=ru`. Але для індексу це різні документи —
    власний `<title>`, власний canonical, власний `inLanguage`, — тому подаємо
    обидві. Карта тут єдине джерело: додали сторінку в неї — потрапить і сюди.
    """
    tree = ET.parse(os.path.join(ROOT, "sitemap.xml"))
    out = []
    for url in tree.getroot().findall("sm:url", SITEMAP_NS):
        loc = url.find("sm:loc", SITEMAP_NS)
        if loc is not None and loc.text:
            out.append(loc.text.strip())
        for link in url.findall("xhtml:link", SITEMAP_NS):
            href = link.get("href")
            if href and href not in out:
                out.append(href.strip())
    return out


def url_of_file(path):
    """Файл у репозиторії → адреса, за якою він реально віддається.

    Сайт живе на безрозширених адресах: `/tsiny`, а не `/tsiny.html`, і
    `/tsiny?lang=ru`, а не `/tsiny.ru.html` — на .html і .ru.html стоїть 301.
    Подати адресу з 301 означає попросити переобійти редирект замість сторінки.
    """
    path = path.replace("\\", "/")
    if not path.endswith(".html"):
        return None
    # Публікуються тільки .html у корені та в blog/. Решта — заготовки
    # генераторів: `tools/home/template.html` теж закінчується на .html, і без
    # цієї перевірки з нього виходила адреса /tools/home/template, якої на сайті
    # немає й ніколи не було.
    if "/" in path and not path.startswith("blog/"):
        return None
    if path.count("/") > 1:
        return None
    ru = path.endswith(".ru.html")
    stem = path[:-len(".ru.html")] if ru else path[:-len(".html")]
    suffix = "?lang=ru" if ru else ""

    if stem == "index":
        return ORIGIN + "/" + suffix
    if stem == "blog/index":
        return ORIGIN + "/blog/" + suffix
    return ORIGIN + "/" + stem + suffix


def changed_urls(rev_range):
    """Адреси сторінок, які змінилися в заданому діапазоні комітів.

    Що подавати, вирішує карта сайту, а не наявність файла: у корені лежать і
    сторінки, яких в індексі бути не повинно. Юридичні несуть `noindex`, а
    `/oplata` навмисно тримають поза картою, доки немає ключів оплати —
    подати її звідси означало б тихо скасувати те рішення. Другого списку
    винятків тут немає навмисно: два списки колись розійдуться.
    """
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", rev_range],
            cwd=ROOT, stderr=subprocess.STDOUT,
        ).decode("utf-8", "replace")
    except subprocess.CalledProcessError as err:
        sys.exit("git diff не вдався: %s" % err.output.decode("utf-8", "replace").strip())

    known = set(urls_from_sitemap())
    urls, skipped = [], []
    for line in out.splitlines():
        u = url_of_file(line.strip())
        if not u or u in urls:
            continue
        (urls if u in known else skipped).append(u)
    for u in skipped:
        print("  поза картою, не подаю: %s" % u)
    return urls


def submit(key, urls, dry_run=False):
    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": "%s/%s.txt" % (ORIGIN, key),
        "urlList": urls,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    if dry_run:
        print("— нічого не надсилаю (--dry-run) —")
        return 0

    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            print("Відповідь: HTTP %s" % res.status)
            return 0
    except urllib.error.HTTPError as err:
        text = err.read().decode("utf-8", "replace")[:300]
        # Коди протоколу говорять різне, і плутати їх дорого: 403 — ключ не
        # знайдено або не збігається, 422 — адреси не з цього домену.
        hint = {
            400: "неправильний запит",
            403: "ключ не підтверджено — чи віддається %s/%s.txt?" % (ORIGIN, key),
            422: "адреси не належать домену %s" % HOST,
            429: "надто часто — спробувати пізніше",
        }.get(err.code, "")
        print("Не прийнято: HTTP %s %s %s" % (err.code, hint, text), file=sys.stderr)
        return 1
    except urllib.error.URLError as err:
        print("Немає зв'язку: %s" % err.reason, file=sys.stderr)
        return 1


def main(argv):
    dry_run = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]

    if "--all" in argv:
        urls = urls_from_sitemap()
    elif "--changed" in argv:
        i = argv.index("--changed")
        if i + 1 >= len(argv):
            sys.exit("--changed потребує діапазону, напр. origin/master..HEAD")
        urls = changed_urls(argv[i + 1])
    else:
        urls = [a for a in argv[1:] if a.startswith("http")]

    if not urls:
        print("Немає що подавати.")
        return 0
    if len(urls) > BATCH:
        sys.exit("Адрес більше за %d — протокол стільки за раз не бере." % BATCH)

    key = find_key()
    print("Ключ: %s" % key)
    print("Адрес: %d" % len(urls))
    for u in urls:
        print("  %s" % u)
    return submit(key, urls, dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
