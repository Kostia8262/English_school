# -*- coding: utf-8 -*-
"""Перевіряє, що обидві мовні версії існують і доходять до браузера.

У сусідній школі був показовий баг: російські переклади в коді були, але до
сторінки не доїжджали — на місці тексту лишалася порожнеча. Помітили це не
одразу, бо в самому коді все виглядало правильно. Ця перевірка шукає рівно
такий випадок, і не одним способом, а трьома — бо на трьох типах сторінок
двомовність влаштована по-різному:

  index.html      Alpine + словник TRANS: `x-text="t.nav.about"`.
                  Ризик — ключ є в uk, але немає в ru: вузол лишиться порожнім.

  посадкові       українська в тексті, російська в атрибуті `data-ru`.
                  Ризик — `data-ru=""` або взагалі відсутній атрибут.

  статті блогу    два повні блоки під `x-show="lang === '…'"`.
                  Ризик — блок є, але порожній, або немає зовсім.

Запуск:  python tools/audit/i18n.py
Код виходу: 1, якщо знайдено проблему.
"""
from __future__ import unicode_literals

import io
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def clean_urls():
    """Слуги посадкових сторінок — з .htaccess, а не окремим списком тут.

    Копія списку розходиться з оригіналом на першій же новій сторінці, і
    перевірка тихо перестає дивитися на те, що з'явилося останнім."""
    src = io.open(os.path.join(ROOT, ".htaccess"), encoding="utf-8").read()
    m = re.search(r"RewriteRule \^\(([^)]+)\)\$ \$1\.html", src)
    return m.group(1).split("|") if m else []


LANDING = clean_urls()

# Головна перейшла на той самий контракт, що й посадкові: українська текстом,
# російська в data-ru. Доти вона малювалася через Alpine, і перевіряти її
# доводилося окремо — тепер це та сама перевірка.
BILINGUAL = LANDING + ["index"]

# Як відрізнити справжній пропуск від законного збігу.
#
# Величезна частина рядків збігається обома мовами законно: емодзі, англійські
# назви тем («Present Perfect», «KET Reading 1–2»), коди рівнів, ціни, адреси,
# CSS-градієнти й слова, які в українській і російській пишуться однаково
# («Спорт», «Формат», «Дата»). Ловити їх усі — тонути в шумі.
#
# Надійна ознака справжнього пропуску: український рядок містить літери, яких
# у російській абетці немає взагалі (і, ї, є, ґ), а «російський» переклад
# збігається з ним буква в букву. Значить, російський текст просто скопіювали.
#
# Решта збігів іде окремим списком «глянути очима» і збірку не валить:
# автоматично їх не розсудити.
UK_ONLY = re.compile(r"[іїєґІЇЄҐ]")

# Пишуться однаково, але саме тому їх легко проґавити: імена, які в російській
# мають інший вигляд, хоч і не містять специфічних українських літер.
WATCH = {"Катерина В.", "Катерина", "Олена", "Артем", "Олена М.", "Артем Д."}

problems = []
review = []   # не помилки, але варто глянути очима
stats = {"ключів TRANS": 0, "сторінок data-ru": 0, "data-ru": 0, "статей": 0}


def note(where, msg):
    problems.append((where, msg))


# ── 1. Словник головної ──────────────────────────────────────────────────────
def check_trans():
    """Словник, з якого складається головна.

    Раніше він лежав інлайном в index.html і читався запуском node. Тепер це
    tools/home/trans.json — джерело для tools/home/build.py, тож і перевіряти
    треба саме його: у самій сторінці тексту вже немає, є готовий результат.
    """
    path = os.path.join(ROOT, "tools", "home", "trans.json")
    if not os.path.exists(path):
        note("tools/home/trans.json", "файла немає — головну нема з чого складати")
        return
    d = json.load(io.open(path, encoding="utf-8"))

    uk, ru = d.get("uk"), d.get("ru")
    if not uk or not ru:
        note("trans.json", "немає гілки uk або ru")
        return

    same = []

    def walk(a, b, path=""):
        if isinstance(a, dict):
            if not isinstance(b, dict):
                note("TRANS" + path, "тип не збігається")
                return
            for k in a:
                if k not in b:
                    note("TRANS" + path + "." + k, "ключа немає в ru — вузол буде порожній")
                else:
                    walk(a[k], b[k], path + "." + k)
            for k in b:
                if k not in a:
                    note("TRANS" + path + "." + k, "ключа немає в uk")
        elif isinstance(a, list):
            if not isinstance(b, list):
                note("TRANS" + path, "тип не збігається")
                return
            if len(a) != len(b):
                note("TRANS" + path, "різна довжина: uk=%d ru=%d" % (len(a), len(b)))
            for i in range(min(len(a), len(b))):
                walk(a[i], b[i], "%s[%d]" % (path, i))
        elif isinstance(a, str):
            stats["ключів TRANS"] += 1
            if not isinstance(b, str) or not b.strip():
                note("TRANS" + path, "російське значення порожнє")
            elif a == b:
                t = a.strip()
                if UK_ONLY.search(t) or t in WATCH:
                    note("TRANS" + path,
                         "російський текст скопійовано з українського: «%s»" % t[:46])
                else:
                    same.append((path, t))

    walk(uk, ru)
    if same:
        review.append(("словнику головної", len(same),
                       [p + " = «" + v[:34] + "»" for p, v in same[:5]]))


# ── 2. Посадкові: атрибути data-ru ───────────────────────────────────────────
CYR_UK = re.compile(r"[іїєґ]")          # літери, яких немає в російській
ATTR_RU = re.compile(r'data-ru="([^"]*)"')


def check_landing():
    for slug in BILINGUAL:
        path = os.path.join(ROOT, slug + ".html")
        if not os.path.exists(path):
            note(slug + ".html", "файла немає")
            continue
        s = io.open(path, encoding="utf-8").read()
        stats["сторінок data-ru"] += 1

        found = ATTR_RU.findall(s)
        stats["data-ru"] += len(found)
        empty = [v for v in found if not v.strip()]
        if empty:
            note(slug + ".html", "порожніх data-ru: %d" % len(empty))

        # Український текст без пари: вузол із українськими літерами,
        # у якого немає data-ru поруч.
        body = s.split("<body", 1)[1] if "<body" in s else s
        body = re.sub(r"<(script|style)\b.*?</\1>", " ", body, flags=re.S)
        untranslated = []
        for m in re.finditer(r"<([a-z0-9]+)([^>]*)>([^<>]{4,})</\1>", body):
            attrs, text = m.group(2), m.group(3).strip()
            if not CYR_UK.search(text):
                continue
            if "data-ru" in attrs:
                continue
            untranslated.append(text)
        if untranslated:
            note(slug + ".html",
                 "текст без перекладу (%d): %s"
                 % (len(untranslated), " | ".join(t[:44] for t in untranslated[:3])))


# ── 3. Статті блогу: два мовні блоки ─────────────────────────────────────────
def check_blog():
    d = os.path.join(ROOT, "blog")
    for f in sorted(os.listdir(d)):
        if not f.endswith(".html") or f == "index.html":
            continue
        s = io.open(os.path.join(d, f), encoding="utf-8").read()
        stats["статей"] += 1

        for lang in ("uk", "ru"):
            marker = "x-show=\"lang === '%s'\"" % lang
            if marker not in s:
                note("blog/" + f, "немає блоку %s" % lang)
                continue
            i = s.index(marker)
            # Беремо приблизний обсяг блоку — до наступного мовного маркера
            # або до кінця <main>.
            rest = s[i:]
            nxt = rest.find("x-show=\"lang === '", 10)
            chunk = rest[:nxt] if nxt > 0 else rest[:rest.find("</main>")]
            text = re.sub(r"<[^>]+>", " ", chunk)
            words = len(text.split())
            if words < 300:
                note("blog/" + f, "блок %s підозріло короткий: %d слів" % (lang, words))

        # У російському блоці не має бути суто українських літер у тексті.
        i = s.index("x-show=\"lang === 'ru'\"")
        ru_chunk = s[i:s.find("</main>", i)]
        ru_text = re.sub(r"<[^>]+>", " ", ru_chunk)
        bad = [w for w in ru_text.split() if CYR_UK.search(w)]
        if len(bad) > 3:
            note("blog/" + f,
                 "у російському блоці українські слова (%d): %s"
                 % (len(bad), ", ".join(bad[:5])))


def main():
    check_trans()
    check_landing()
    check_blog()

    print("оглянуто: " + ", ".join("%s %d" % (k, v) for k, v in stats.items()))
    print()

    for where, n, examples in review:
        print("до відома: у %s %d рядків збігаються обома мовами" % (where, n))
        print("           емодзі, англійські назви, ціни — зазвичай це нормально")
        for e in examples:
            print("           %s" % e)
        print()

    if problems:
        print("ЗНАЙДЕНО ПРОБЛЕМ: %d\n" % len(problems))
        for where, msg in problems:
            print("  %-44s %s" % (where[:44], msg))
        return 1
    print("двомовність: обидві версії на місці, порожніх вузлів немає")
    return 0


if __name__ == "__main__":
    sys.exit(main())
