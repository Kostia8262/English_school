# -*- coding: utf-8 -*-
"""Скільки на сторінці власного тексту, а скільки — спільного з сусідами групи.

Навіщо. 27.10.2026 сайт втратив майже всі покази при живому індексі, і одна з
версій — 21 країнова сторінка з одного шаблону: у кожної 37–55 % свого тексту,
решта слово в слово повторювалась на інших країнах (для Google — схоже на
doorway pages). 13.11.2026 країн лишилось 5, кожну переписав окремий агент, а
мірялось це скриптом у scratchpad, який писали заново. Тепер він тут.

Як міряє: текст `<main>` зібраної сторінки (без script/style/svg/form/nav/
header/footer), шинглі по N слів (N — `shingle` у similarity.json). «Свій
текст» — частка шинглів сторінки, яких немає на жодній іншій сторінці групи.
«Пара» — коефіцієнт Жаккара з найближчою сторінкою групи. Групи й пороги —
у similarity.json, не тут.

Запуск (після складання tools/landing/build.py):
    python tools/audit/similarity.py                 # усі групи
    python tools/audit/similarity.py --page anhliyska-dlya-ditey-u-polshchi
        # одна сторінка + перелік спільних фраз (що саме переписувати)
    python tools/audit/similarity.py --ru            # російські .ru.html
    python tools/audit/similarity.py --src [--page …]
        # з джерел tools/landing/pages_*.py, без складання: для агентів, що
        # переписують сторінки паралельно й не мають права запускати build.py.
        # Цифри близькі до складених (13.11.2026: 93–97 % проти 84–87 %:
        # у зібраному <main> ще ціновий блок, контакти, картки блогу).
        # «слів» у цьому режимі — uk і ru разом.

Код виходу: 1, якщо сторінка групи з порогами вийшла за межу.
У run.py не входить: це перевірка при переписуванні партії сторінок, а не гейт
кожного пушу.
"""
from __future__ import unicode_literals

import glob
import html
import io
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONF = os.path.join(os.path.dirname(__file__), "similarity.json")


def words(path):
    s = io.open(path, encoding="utf-8").read()
    m = re.search(r"(?is)<main[^>]*>(.*)</main>", s)
    s = m.group(1) if m else s
    s = re.sub(r"(?is)<(script|style|noscript|svg|template|form)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?is)<(header|footer|nav)[^>]*>.*?</\1>", " ", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.findall(r"[\w'’]+", s.lower())


SKIP_KEYS = ("schema", "hero_art")


def _strings(x, out):
    """Тексти сторінки-словника: без *_ru, адрес і розмітки Schema.org."""
    if isinstance(x, str):
        if not x.startswith(("/", "http")) and len(x) > 2:
            out.append(x)
    elif isinstance(x, dict):
        for key, v in x.items():
            if not key.endswith("_ru") and key not in SKIP_KEYS:
                _strings(v, out)
    elif isinstance(x, (list, tuple)):
        for v in x:
            _strings(v, out)
    return out


def source_pages():
    """slug -> слова, з модулів tools/landing (усі pages_*.py дописують content.PAGES)."""
    land = os.path.join(ROOT, "tools", "landing")
    sys.path.insert(0, land)
    import importlib
    content = importlib.import_module("content")
    for f in sorted(glob.glob(os.path.join(land, "pages_*.py"))):
        mod = os.path.basename(f)[:-3]
        try:
            importlib.import_module(mod)
        except Exception as e:  # чужий файл посеред правки не має валити всю групу
            print("!! %s не імпортується: %s" % (mod, e))
    return {p["slug"].strip("/"): re.findall(r"[\w'’]+", " ".join(_strings(p, [])).lower())
            for p in content.PAGES}


def shingles(w, k):
    return {" ".join(w[i:i + k]) for i in range(len(w) - k + 1)}


def main(argv):
    ru = "--ru" in argv
    src = "--src" in argv
    only = argv[argv.index("--page") + 1] if "--page" in argv else None
    conf = json.load(io.open(CONF, encoding="utf-8"))
    k = conf["shingle"]
    suffix = ".ru.html" if ru else ".html"
    names = {}
    for f in glob.glob(os.path.join(ROOT, "*" + suffix)):
        base = os.path.basename(f)
        if not ru and base.endswith(".ru.html"):
            continue
        names[base[:-len(suffix)]] = f
    if src:
        cache = source_pages()
        names = {n: n for n in cache}
        words_of = cache.get
    else:
        words_of = lambda n: words(names[n])
    bad = 0
    for gname, g in conf["groups"].items():
        rx = re.compile(g["pattern"])
        members = sorted(n for n in names if rx.search(n))
        if only and only not in members:
            continue
        if len(members) < 2:
            print("%s: менше двох сторінок, нема з чим порівнювати" % gname)
            continue
        W = {n: words_of(n) for n in members}
        S = {n: shingles(W[n], k) for n in members}
        print("== %s (%d стор.)" % (gname, len(members)))
        for n in members:
            if only and n != only:
                continue
            others = set().union(*[S[o] for o in members if o != n])
            own = 1 - len(S[n] & others) / float(len(S[n]) or 1)
            pair, near = max((len(S[n] & S[o]) / float(len(S[n] | S[o]) or 1), o)
                             for o in members if o != n)
            flag = ""
            if g.get("min_own") is not None and own < g["min_own"]:
                flag += "  < свого %d%%" % (g["min_own"] * 100)
            if g.get("max_pair") is not None and pair > g["max_pair"]:
                flag += "  > пари %d%%" % (g["max_pair"] * 100)
            if flag:
                bad += 1
            print("  %-45s слів %5d  свого %3.0f%%  пара %3.0f%% з %s%s"
                  % (n, len(W[n]), own * 100, pair * 100, near, flag))
            if only:
                common = sorted(S[n] & others)
                print("  спільні фрази (%d, перші 60):" % len(common))
                for c in common[:60]:
                    print("    " + c)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
