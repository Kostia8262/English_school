# -*- coding: utf-8 -*-
"""Ілюстрація в геро країнової сторінки: малюнок, дві часові пілюлі, підпис.

Спершу така схема була намальована інлайновим SVG. Вона працювала, але
виглядала як креслення: контур, точки, підписи — і нічого, що каже «школа для
дітей». Тепер це намальована ілюстрація (Magnific, модель Recraft V4.1):
силует країни у фірмовому оранжевому, три картки з іконками уроку й лисеня в
навушниках. Кремове тло малюнка збігається з тлом сторінки, тому картинка не
виглядає вклеєною.

Розмір: 440 px — стільки колонка й займає; @2x для щільних екранів. webp
важить 9–12 КБ, @2x — 22–27 КБ, jpg лежить поруч для старих браузерів. Шлях
абсолютний, бо адреси сторінок безрозширенні.

Час і міста лишаються **текстом** поруч із малюнком, а не їдуть у нього: їх
читає пошук, перекладає js/lang.js і бачить людина з вимкненими зображеннями.
Тому ж у промпті стояло «no text, no letters, no numbers» — намальовані літери
виходять кривими й не перекладаються.
"""
from __future__ import unicode_literals

_TEMPLATE = """      <div class="absolute -top-6 -right-4 w-32 h-32 bg-fox-100 rounded-4xl rotate-12 hidden sm:block" aria-hidden="true"></div>
      <div class="absolute -bottom-8 -left-6 w-28 h-28 bg-violet-100 rounded-full hidden sm:block" aria-hidden="true"></div>
      <figure class="relative bg-white rounded-4xl border border-fox-100 p-4 sm:p-6 shadow-sm">
        <picture>
          <source srcset="/%(img)s-hero.webp 1x, /%(img)s-hero@2x.webp 2x" type="image/webp">
          <img class="w-full h-auto rounded-3xl" src="/%(img)s-hero.jpg" srcset="/%(img)s-hero.jpg 1x, /%(img)s-hero@2x.jpg 2x" alt="%(alt_uk)s" data-ru-alt="%(alt_ru)s" width="440" height="440" loading="eager" fetchpriority="high">
        </picture>
        <div class="flex flex-wrap items-center justify-center gap-2 mt-5">
          <span class="bg-white border border-fox-100 text-gray-600 font-bold text-sm px-4 py-1.5 rounded-full" data-ru="%(left_ru)s">%(left_uk)s</span>
          <span class="text-fox-500 font-black" aria-hidden="true">&rarr;</span>
          <span class="bg-fox-500 text-white font-black text-sm px-4 py-1.5 rounded-full" data-ru="%(right_ru)s">%(right_uk)s</span>
        </div>
        <figcaption class="text-sm text-gray-500 leading-relaxed mt-4 text-center" data-ru="%(cap_ru)s">%(cap_uk)s</figcaption>
      </figure>
"""


# Кільце перелінковки серії: кожна країнова сторінка веде на решту з тіла, а не
# лише з підвалу — вагу несе саме тіло. Перелік один, тому нова країна
# з'являється на всіх сторінках одночасно; сторінка сама себе не показує.
COUNTRIES = [
    ("anhliyska-dlya-ditey-u-polshchi", "Польща", "Польша"),
    ("anhliyska-dlya-ditey-u-nimechchyni", "Німеччина", "Германия"),
    ("anhliyska-dlya-ditey-u-chekhiyi", "Чехія", "Чехия"),
    ("anhliyska-dlya-ditey-v-italiyi", "Італія", "Италия"),
    ("anhliyska-dlya-ditey-u-rumuniyi", "Румунія", "Румыния"),
    ("anhliyska-dlya-ditey-u-frantsiyi", "Франція", "Франция"),
    ("anhliyska-dlya-ditey-v-ispaniyi", "Іспанія", "Испания"),
]


# Текст посилання — не сама назва країни, а запит: «Англійська в Німеччині».
# Анкор читає пошук, і назва країни в ньому важить більше за коротке слово в
# пілюлі. Прийменник у кожної свій, тому перелічений, а не вгаданий правилом.
ANCHORS = {
    "anhliyska-dlya-ditey-u-polshchi": ("Англійська у Польщі", "Английский в Польше"),
    "anhliyska-dlya-ditey-u-nimechchyni": ("Англійська в Німеччині", "Английский в Германии"),
    "anhliyska-dlya-ditey-u-chekhiyi": ("Англійська в Чехії", "Английский в Чехии"),
    "anhliyska-dlya-ditey-v-italiyi": ("Англійська в Італії", "Английский в Италии"),
    "anhliyska-dlya-ditey-u-rumuniyi": ("Англійська в Румунії", "Английский в Румынии"),
    "anhliyska-dlya-ditey-u-frantsiyi": ("Англійська у Франції", "Английский во Франции"),
    "anhliyska-dlya-ditey-v-ispaniyi": ("Англійська в Іспанії", "Английский в Испании"),
}


def links(exclude=None):
    """Перелік країн посиланнями для блоку `chiplinks`."""
    out = [("/" + slug, ANCHORS[slug][0], ANCHORS[slug][1])
           for slug, _uk, _ru in COUNTRIES if slug != exclude]
    out.append(("/anhliyska-dlya-ditey-za-kordonom", "Інші країни",
                "Другие страны"))
    return out


def ring(current_slug):
    """Блоки «а якщо ви в іншій країні» для країнової сторінки."""
    others = links(exclude=current_slug)
    return [
        ("h2", "А якщо ви в іншій країні", "А если вы в другой стране"),
        ("p",
         "Формат, ціна й програма всюди ті самі — різняться тільки час уроку й те, "
         "якою мовою дитині пояснюють англійську в місцевій школі. Ось сторінки під "
         "інші країни, де живуть наші учні:",
         "Формат, цена и программа везде те же — различаются только время урока и то, "
         "на каком языке ребёнку объясняют английский в местной школе. Вот страницы "
         "под другие страны, где живут наши ученики:"),
        ("chiplinks", others),
    ]


def art(image, alt_uk, alt_ru, left_uk, left_ru, right_uk, right_ru,
        caption_uk, caption_ru):
    return _TEMPLATE % {
        "img": image,
        "alt_uk": alt_uk, "alt_ru": alt_ru,
        "left_uk": left_uk, "left_ru": left_ru,
        "right_uk": right_uk, "right_ru": right_ru,
        "cap_uk": caption_uk, "cap_ru": caption_ru,
    }
