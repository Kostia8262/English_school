# -*- coding: utf-8 -*-
"""Ілюстрації геро: з вихідного рендера робить чотири файли на сторінку.

Картинки малює Magnific (модель Recraft V4.1) — промпт і фірмові кольори
описані в пам'яті проєкту. Сюди рендер потрапляє великим PNG, а сторінці
потрібні чотири файли: 440 px для звичайного екрана, 880 px для щільного, і
кожен у webp та jpg. Раніше це робилося руками, через що сім перших країн
мають файли трохи різної ваги; тепер крок один і відтворюваний.

Навіщо обидва формати. `webp` важить удвічі менше й віддається сучасним
браузерам через `<source>`; `jpg` лежить поруч для старих. Розмір 440 — це
рівно ширина колонки в геро, більший файл користі не дає, а важить більше.

Імена файлів версії не містять, а віддаються з `immutable` на рік
(див. `.htaccess`), тож **замінити картинку означає перейменувати її** — інакше
відвідувач, який уже був на сайті, побачить стару.

Запуск:

    python tools/hero/build.py <тека-з-PNG>

У теці мають лежати файли з іменами, які потрібні сторінкам: `britain.png`,
`ireland.png` і так далі. Результат кладеться в корінь репозиторію як
`<ім'я>-hero.webp`, `<ім'я>-hero@2x.webp` і такі самі `.jpg`.
"""
from __future__ import unicode_literals

import io
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE)) if os.path.basename(
    os.path.dirname(HERE)) == 'tools' else os.path.dirname(os.path.dirname(HERE))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

# Дві ширини: одинарна — ширина колонки, подвійна — для щільних екранів.
# Кремове тло сторінки — те саме `--cream`, що в дизайн-системі; потрібне
# лише як підкладка під прозорість, бо jpg альфи не має.
CREAM = (255, 251, 247)

SIZES = (('', 440), ('@2x', 880))

# Якість підібрана за першими сімома країнами: webp 9–12 КБ, jpg 16–20 КБ на
# 440 px. Вище — важче без видимої різниці на плоскій ілюстрації.
WEBP_QUALITY = 82
JPEG_QUALITY = 86


def build_one(src_path, name, out_dir):
    im = Image.open(src_path)
    if im.mode != 'RGB':
        # Рендер приходить із альфою; підкладаємо кремове тло сторінки, щоб
        # країв не було видно на jpg, який прозорості не має.
        bg = Image.new('RGB', im.size, CREAM)
        bg.paste(im, mask=im.split()[-1] if im.mode in ('RGBA', 'LA') else None)
        im = bg

    made = []
    for suffix, side in SIZES:
        resized = im.resize((side, side), Image.LANCZOS)
        for ext, params in (('webp', {'quality': WEBP_QUALITY, 'method': 6}),
                            ('jpg', {'quality': JPEG_QUALITY, 'optimize': True,
                                     'progressive': True})):
            out = os.path.join(out_dir, '%s-hero%s.%s' % (name, suffix, ext))
            resized.save(out, **params)
            made.append((os.path.basename(out), os.path.getsize(out) // 1024))
    return made


def main():
    if len(sys.argv) < 2:
        raise SystemExit('вкажіть теку з вихідними PNG')
    src_dir = sys.argv[1]
    names = sorted(f for f in os.listdir(src_dir) if f.lower().endswith('.png'))
    if not names:
        raise SystemExit('у теці немає PNG')

    total = 0
    for fn in names:
        name = os.path.splitext(fn)[0]
        made = build_one(os.path.join(src_dir, fn), name, ROOT)
        total += len(made)
        sizes = ', '.join('%s %d КБ' % m for m in made)
        out = io.open(os.devnull, 'w') if False else sys.stdout
        out.write('%-14s %s\n' % (name, sizes))
    sys.stdout.write('разом файлів: %d\n' % total)


if __name__ == '__main__':
    main()
