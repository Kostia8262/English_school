# -*- coding: utf-8 -*-
"""Стежить за темпом виходу статей: партіями не викладаємо.

Навіщо це взагалі. 19.10.2026 за один день на сайт виклали **11 статей** — усю
першу десятку довідника плюс одну. Статей стало 42 замість 31, тобто +35% до
обсягу сайту за добу. Вісім днів показы трималися й навіть росли, а 27.10
обірвалися в нуль: 1 показ, потім 4, потім ноль чотири дні поспіль.

Поломки при цьому не знайшлося жодної — ні технічної, ні змістової. Сайт
віддає 200, сертифікат живий, усі адреси в Search Console «Submitted and
indexed», Googlebot ходить, ручних мір немає, решта мережі стоїть ровно (отже
не апдейт), власний аудит проходить цілком, а сама партія при замері виявилася
добротною: 1 230–1 485 слів на статтю, попарна схожість усередині партії —
медіана 2,7%. Єдина подія, що збігається з обривом за масштабом і строком, —
сама партія.

Довести цей зв'язок нічим: алгоритмічне пониження Search Console не показує
ніде. Але ціна обережності нульова, а ціна повтору — ще одна видача. Розбір і
правило — `docs/plan-2026-10.md`, розділ «Темп публікації».

Чому скриптом, а не записом у документації. Правило «одна стаття на тиждень»
уже стояло в `content-queue/sites.json` мережі (`cadence: weekly`) — і 19.10
його обійшли руками. Запис у плані обійти так само легко; перевірка перед
пушем — ні.

Межі навмисно м'які, щоб сторож не заважав звичайній роботі:

* 0–1 стаття за сім днів — норма, нічого не кажемо;
* 2–3 — попередження, код виходу 0 (буває: статтю перевиклали, поправили слаг);
* 4 і більше — це партія, код виходу 1.

Історії немає (не репозиторій, git недоступний) — перевірка молчки
пропускається: краще не перевірити, ніж завалити публікацію через відсутній
`.git`.

Неглибокий клон (`git clone --depth N`) — окремий випадок. Його найстаріший
коміт не має батька, і `git log --diff-filter=A` бачить у ньому «додавання»
кожного файлу репозиторію. 03.11 і 06.11.2026 конвеєр мережі клонував сайт
з `--depth 1` — сторож нарахував «41 статтю за 7 днів» і двічі завалив
публікацію однієї статті. Тому граничні коміти неглибокого клону з підрахунку
виключаємо (`--not <межа>`), а про неповну історію пишемо прямо.

Запуск:  python tools/audit/pace.py
Код виходу: 1, якщо за останні сім днів вийшла партія.
"""
from __future__ import unicode_literals

import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

WINDOW_DAYS = 7
WARN_FROM = 2
FAIL_FROM = 4
# Для контексту: скільки вийшло за місяць. Саме це число показує, чи темп
# рівний, чи знову збирається горб.
CONTEXT_DAYS = 30


def _git(args):
    """Виклик git у корені репозиторію. None, якщо git або історії немає."""
    try:
        out = subprocess.check_output(
            ["git"] + args, cwd=ROOT, stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError):
        return None
    if not isinstance(out, str):
        out = out.decode("utf-8", "replace")
    return out


def shallow_roots():
    """Граничні коміти неглибокого клону; порожньо — історія повна."""
    flag = _git(["rev-parse", "--is-shallow-repository"])
    if flag is None or flag.strip() != "true":
        return []
    path = _git(["rev-parse", "--git-path", "shallow"])
    if not path:
        return []
    path = path.strip()
    if not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    try:
        with open(path) as fh:
            return [line.strip() for line in fh if line.strip()]
    except (IOError, OSError):
        return []


def added_articles(days, roots=()):
    """Статті блогу, додані за `days` днів. None — історія недоступна.

    Беремо тільки українські файли: `.ru.html` їде тією ж правкою й подвоїв би
    кожну цифру.
    """
    args = ["log", "--since=%d.days" % days, "--diff-filter=A",
            "--name-only", "--format=", "HEAD"]
    if roots:
        # Межа клону «додає» всі файли разом — її не рахуємо.
        args += ["--not"] + list(roots)
    out = _git(args + ["--", "blog/"])
    if out is None:
        return None
    found = []
    for line in out.splitlines():
        line = line.strip()
        if not line.endswith(".html") or line.endswith(".ru.html"):
            continue
        name = os.path.basename(line)
        if name == "index.html":
            continue
        found.append(name[:-5])
    return sorted(set(found))


def main():
    # `.git` буває не каталогом, а файлом із посиланням — так виглядає
    # worktree, а правки тут роблять саме з тимчасового worktree. Тому
    # exists, а не isdir: inakше перевірка молчки пропускалася б щоразу.
    if not os.path.exists(os.path.join(ROOT, ".git")):
        print("історії git немає — перевірку темпу пропущено")
        return 0

    roots = shallow_roots()
    if roots:
        print("клон неглибокий (%d граничн. коміт) — межу не рахуємо; "
              "якщо історія коротша за %d днів, цифри занижені"
              % (len(roots), WINDOW_DAYS))

    recent = added_articles(WINDOW_DAYS, roots)
    if recent is None:
        print("git не відповів або історія неповна — перевірку темпу пропущено")
        return 0

    month = added_articles(CONTEXT_DAYS, roots) or []

    print("нових статей за %d днів: %d" % (WINDOW_DAYS, len(recent)))
    for slug in recent:
        print("   " + slug)
    print("за %d днів: %d" % (CONTEXT_DAYS, len(month)))

    if len(recent) >= FAIL_FROM:
        print()
        print("ПАРТІЯ: %d статей за %d днів, межа %d."
              % (len(recent), WINDOW_DAYS, FAIL_FROM - 1))
        print("Правило для цього домену — одна стаття на тиждень:")
        print("19.10.2026 партія з 11 статей збіглася з обривом показів у нуль")
        print("(docs/plan-2026-10.md, розділ «Темп публікації»).")
        print("Решту статей тримати в pending/ — писати можна скільки завгодно,")
        print("обмеження саме на викладку.")
        return 1

    if len(recent) >= WARN_FROM:
        print()
        print("попередження: %d статті за %d днів — темп вище за одну на тиждень"
              % (len(recent), WINDOW_DAYS))
        return 0

    print("темп рівний")
    return 0


if __name__ == "__main__":
    sys.exit(main())
