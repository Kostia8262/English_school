# -*- coding: utf-8 -*-
"""Звіряє ключові цифри між усіма сторінками.

Ціни, розмір групи й тривалість уроку живуть щонайменше в семи місцях: об'єкт
TRANS у index.html, граф розмітки там же, llms.txt, статичний noscript-блок,
три файли генератора лендингів і стаття блогу про ціни. Сторінка, яка обіцяє
інші гроші, ніж сусідня, — це привід для скарги, а не для SEO.

У сусідньої школи для цього є цілий tools/course-audit на десять скриптів —
там дані ще й у базі та CMS. Нам вистачає одного: шукаємо всі грошові суми й
вікові діапазони в текстах і б'ємо на сполох, щойно з'явиться щось поза
списком дозволених.

Запуск:  python tools/audit/facts.py
Код виходу: 1, якщо знайдено цифру поза списком.
"""
from __future__ import unicode_literals

import collections
import io
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Суми, які мають право зустрічатися. Перші три — наші тарифи, 300 і 500 — ціна
# години, 250 і 400 — орієнтири ринку в тексті про те, чому ми стільки коштуємо.
ALLOWED_MONEY = {"1800", "3600", "3000", "300", "500", "400", "250"}

# Вікові діапазони наших груп плюс ті, що згадуються в статтях як довідка.
ALLOWED_AGES = {
    "6-8", "9-12", "13-18", "6-18",          # наші групи
    "6-10", "11-18", "10-18", "12-18", "6-9", "6-12", "7-18",
    "11-14", "11-16", "13-16", "15-16", "9-10", "10-12", "6-7",
    "11-12",  # поріг, з якого дитині стає корисним викладач-носій мови
    "2-3", "3-5", "4-5", "10-14", "12-17", "7-8", "8-11", "9-11",
}

MONEY_RE = re.compile(r"(\d[\d  ]{2,6})\s*грн")
AGE_RE = re.compile(r"(\d{1,2})\s*[–-]\s*(\d{1,2})\s*(?:рок|років|лет|год)")


def collect_files():
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in (".git", "node_modules", "src", "__pycache__")]
        for f in files:
            if f.startswith("_"):
                continue
            if f.endswith((".html", ".txt")) or (
                    f.endswith(".py") and os.sep + "landing" in base):
                out.append(os.path.join(base, f))
    return sorted(out)


def main():
    files = collect_files()
    money = collections.defaultdict(set)
    ages = collections.defaultdict(set)

    for p in files:
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        try:
            s = io.open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, IOError):
            continue
        for m in MONEY_RE.finditer(s):
            money[re.sub(r"\D", "", m.group(1))].add(rel)
        for m in AGE_RE.finditer(s):
            ages[m.group(1) + "-" + m.group(2)].add(rel)

    problems = 0

    print("Грошові суми в текстах:")
    for val in sorted(money, key=lambda v: -int(v)):
        ok = val in ALLOWED_MONEY
        print("  %-8s файлів: %-3d %s" % (val + " грн", len(money[val]),
                                          "" if ok else "<-- ПОЗА СПИСКОМ"))
        if not ok:
            problems += 1
            for f in sorted(money[val])[:6]:
                print("            ", f)

    print("\nВікові діапазони:")
    unexpected = [a for a in ages if a not in ALLOWED_AGES]
    print("  усього різних: %d | поза списком: %d" % (len(ages), len(unexpected)))
    for a in sorted(unexpected):
        problems += 1
        print("  %-8s <-- ПОЗА СПИСКОМ, файлів: %d" % (a, len(ages[a])))
        for f in sorted(ages[a])[:4]:
            print("            ", f)

    # Тарифи мають бути присутні скрізь, де взагалі є ціни: якщо на сторінці
    # згадано 1800, але немає 3600 — швидше за все, забули оновити половину.
    print("\nПовнота тарифної трійки:")
    trio = ("1800", "3600", "3000")
    with_any = set().union(*(money[v] for v in trio)) if any(money[v] for v in trio) else set()
    for f in sorted(with_any):
        have = [v for v in trio if f in money[v]]
        # Два тарифи з трьох — третій майже напевно забули при оновленні.
        # Один окремо це нормально: сторінка підготовки до НМТ говорить лише
        # про індивідуальні заняття, і групові ціни там ні до чого.
        if len(have) == 2:
            problems += 1
            print("  %-44s є %s, немає %s <-- схоже, забули"
                  % (f, ", ".join(have), ", ".join(v for v in trio if v not in have)))
    if not problems:
        print("  усі сторінки з цінами показують повний набір")

    print()
    if problems:
        print("знайдено розбіжностей: %d" % problems)
        return 1
    print("розбіжностей немає")
    return 0


if __name__ == "__main__":
    sys.exit(main())
