# -*- coding: utf-8 -*-
"""Ілюстрація в геро для сторінок, які не про країну.

`country_art.art()` малює під картинкою пару пілюль «18:00 у Києві → 17:00 у
вас»: на країновій сторінці це головний факт, заради якого туди й заходять. На
сторінці цін, відгуків чи пробного уроку такої пари немає й бути не може, тому
тут той самий блок без неї — картинка й підпис.

Решта однакова навмисно: та сама рамка, ті самі декоративні плями, та сама
ширина 440 px. Через це `build.py` не доводиться вчити другому вигляду геро —
він просто отримує готовий шматок розмітки в тому самому полі `hero_art`.

Підпис лишається текстом, а не їде в картинку: його читає пошук, перекладає
`js/lang.js` і бачить людина з вимкненими зображеннями.
"""
from __future__ import unicode_literals

_TEMPLATE = """      <div class="absolute -top-6 -right-4 w-32 h-32 bg-fox-100 rounded-4xl rotate-12 hidden sm:block" aria-hidden="true"></div>
      <div class="absolute -bottom-8 -left-6 w-28 h-28 bg-violet-100 rounded-full hidden sm:block" aria-hidden="true"></div>
      <figure class="relative bg-white rounded-4xl border border-fox-100 p-4 sm:p-6 shadow-sm">
        <picture>
          <source srcset="/%(img)s-hero.webp 1x, /%(img)s-hero@2x.webp 2x" type="image/webp">
          <img class="w-full h-auto rounded-3xl" src="/%(img)s-hero.jpg" srcset="/%(img)s-hero.jpg 1x, /%(img)s-hero@2x.jpg 2x" alt="%(alt_uk)s" data-ru-alt="%(alt_ru)s" width="440" height="440" loading="eager" fetchpriority="high">
        </picture>
        <figcaption class="text-sm text-gray-500 leading-relaxed mt-4 text-center" data-ru="%(cap_ru)s">%(cap_uk)s</figcaption>
      </figure>
"""


def art_plain(image, alt_uk, alt_ru, caption_uk, caption_ru):
    return _TEMPLATE % {
        "img": image,
        "alt_uk": alt_uk, "alt_ru": alt_ru,
        "cap_uk": caption_uk, "cap_ru": caption_ru,
    }
