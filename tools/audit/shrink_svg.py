# -*- coding: utf-8 -*-
"""Округляє координати в декоративних SVG до цілих.

bus.svg має viewBox 5000×5000, а показується приблизно на 320 CSS-пікселів:
одна одиниця viewBox — це 0.064 пікселя, тобто десята її частка не видима
ніяк. При цьому дробові хвости займають третину файлу.

Округлюємо все, крім атрибутів зі списку KEEP: там дріб несе сенс, і
`opacity="0.8"` після округлення стало б `opacity="1"`, а `stroke-width="0.5"`
взагалі зникло б у нуль. Зараз таких атрибутів у наших файлах немає, але
список лишається — наступний експорт з ілюстратора цілком може їх принести.

Запуск:  python tools/audit/shrink_svg.py [файл ...]
"""
from __future__ import unicode_literals

import io
import os
import re
import sys

KEEP = (
    "opacity", "fill-opacity", "stroke-opacity", "stop-opacity",
    "stroke-width", "stroke-miterlimit", "stroke-dasharray", "stroke-dashoffset",
    "offset", "scale",
)

KEEP_RE = re.compile(
    r'(?:' + '|'.join(KEEP) + r')\s*=\s*"[^"]*"', re.I)
NUM_RE = re.compile(r"-?\d+\.\d+")


def shrink(text):
    # Вирізаємо захищені атрибути, щоб регулярка з числами їх не бачила,
    # і повертаємо на місце після округлення.
    saved = []

    def stash(m):
        saved.append(m.group(0))
        return "\x00%d\x00" % (len(saved) - 1)

    text = KEEP_RE.sub(stash, text)
    text = NUM_RE.sub(lambda m: str(int(round(float(m.group(0))))), text)
    # Після округлення лишаються подвійні пробіли й пробіл перед мінусом,
    # який у path-даних є самостійним роздільником.
    text = re.sub(r"(?<=\d)\s+(?=-)", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: saved[int(m.group(1))], text)
    return text


def main(paths):
    if not paths:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        paths = [os.path.join(root, f) for f in ("bus.svg", "bigben.svg")]

    total_before = total_after = 0
    for p in paths:
        s = io.open(p, encoding="utf-8").read()
        before = len(s.encode("utf-8"))
        out = shrink(s)
        after = len(out.encode("utf-8"))
        io.open(p, "w", encoding="utf-8", newline="\n").write(out)
        total_before += before
        total_after += after
        print("  %-16s %7d -> %7d Б  (-%d%%)"
              % (os.path.basename(p), before, after,
                 round(100.0 * (before - after) / before) if before else 0))

    if total_before:
        print("\n  разом: %d -> %d Б (-%d%%)"
              % (total_before, total_after,
                 round(100.0 * (total_before - total_after) / total_before)))


if __name__ == "__main__":
    main(sys.argv[1:])
