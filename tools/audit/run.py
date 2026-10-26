# -*- coding: utf-8 -*-
"""Прогоняє всі перевірки разом. Один код виходу на всіх.

Запуск:  python tools/audit/run.py
Код виходу: 1, якщо хоч одна перевірка знайшла проблему.
"""
from __future__ import unicode_literals

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = [
    ("посилання", "links.py"),
    ("цифри",     "facts.py"),
    ("розмітка",  "schema.py"),
    ("кліше ІІ",   "cliche.py"),
    ("двомовність", "i18n.py"),
    ("мета-теги",  "meta.py"),
    ("ассети",    "assets.py"),
    # Клас, якого немає в скомпільованому css/style.css, браузер мовчки
    # ігнорує. Так на 76 сторінках не працював підйом картки (.card-lift), а
    # на головній не було двох декоративних плям. Підключено 26.10.2026,
    # коли всі знайдені мертві класи полагоджено.
    ("класи",     "classes.py"),
]


def main():
    failed = []
    for title, script in CHECKS:
        print("\n" + "=" * 62)
        print("  %s  (%s)" % (title.upper(), script))
        print("=" * 62)
        # Без flush заголовки лишаються в буфері батька, а підпроцес пише
        # напряму — і звіт виходить у переплутаному порядку.
        sys.stdout.flush()
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        code = subprocess.call([sys.executable, os.path.join(HERE, script)], env=env)
        if code != 0:
            failed.append(title)

    print("\n" + "=" * 62)
    if failed:
        print("  ПРОБЛЕМИ: %s" % ", ".join(failed))
        return 1
    print("  усі перевірки пройдені")
    return 0


if __name__ == "__main__":
    sys.exit(main())
