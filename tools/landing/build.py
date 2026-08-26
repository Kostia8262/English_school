# -*- coding: utf-8 -*-
"""Складає посадкові сторінки FluentFox з даних у content.py.

Чому генератор, а не десять окремих файлів. Сторінки відрізняються текстом, але
не версткою: шапка, хлібні крихти, блок FAQ, підвал і вся розмітка в них
однакові. Десять копій однієї верстки розходяться після першої ж правки
дизайн-системи — у сусідньої школи ту саму задачу вирішено шаблоном на сервері,
а тут сервера немає, тож роль шаблона грає цей скрипт. Результат комітиться в
репозиторій як звичайний HTML: у деплої жодного кроку збірки не з'являється.

Запуск:  python tools/landing/build.py
"""
from __future__ import unicode_literals

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import content as C          # noqa: E402  — хелпери + три вікові сторінки
import pages_exams          # noqa: E402,F401  — НМТ і Cambridge, дописують C.PAGES
import pages_service        # noqa: E402,F401  — ціни, відгуки, школа, пробний урок
import pages_dnipro         # noqa: E402,F401  — локальна сторінка з двома класами

BASE = "https://fluent-fox.site"
ORG = BASE + "/#organization"

# Версія в query до style.css. Піднімати руками разом зі складанням CSS,
# інакше повернені відвідувачі побачать сторінку зі старими стилями.
CSS_VERSION = "20260826"


# ── дрібні помічники ─────────────────────────────────────────────────────────

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def bi(uk, ru, tag="span", cls=""):
    """Двомовний вузол: українська — текстом, російська — в data-ru.

    Саме тут і живе головна відмінність від index.html: там текст підставляє
    Alpine, тому в HTML його немає взагалі. Тут українська версія — звичайний
    текст, який видно будь-якому краулеру без запуску скриптів."""
    c = ' class="%s"' % cls if cls else ""
    if ru and ru != uk:
        return '<%s%s data-ru="%s">%s</%s>' % (tag, c, esc(ru), esc(uk), tag)
    return "<%s%s>%s</%s>" % (tag, c, esc(uk), tag)


def attr_ru(uk, ru):
    """Двомовність прямо в атрибутах елемента, без обгортки."""
    if ru and ru != uk:
        return ' data-ru="%s">%s' % (esc(ru), esc(uk))
    return ">" + esc(uk)


# ── блоки контенту ───────────────────────────────────────────────────────────

def render_block(b):
    kind = b[0]

    if kind == "h2":
        return ('      <h2 class="text-2xl md:text-4xl font-black text-gray-900 '
                'leading-tight mb-4 mt-12 first:mt-0"%s</h2>' % attr_ru(b[1], b[2]))

    if kind == "h3":
        return ('      <h3 class="text-xl font-black text-gray-900 leading-tight '
                'mb-3 mt-8"%s</h3>' % attr_ru(b[1], b[2]))

    if kind == "p":
        return ('      <p class="text-base text-gray-600 leading-relaxed mb-4"%s</p>'
                % attr_ru(b[1], b[2]))

    if kind == "ul":
        items = "\n".join(
            '          <li class="flex gap-3 items-start">'
            '<span class="text-fox-500 font-black mt-0.5 flex-none" aria-hidden="true">&#10003;</span>'
            '<span class="text-base text-gray-600 leading-relaxed"%s</span></li>'
            % attr_ru(uk, ru) for uk, ru in b[1])
        return ('      <ul class="flex flex-col gap-3 mb-6 mt-2">\n%s\n      </ul>'
                % items)

    if kind == "cards":
        cards = "\n".join(
            '          <div class="bg-white rounded-3xl p-6 border border-gray-100 shadow-sm">\n'
            '            <div class="text-3xl mb-3" aria-hidden="true">%s</div>\n'
            '            <h3 class="text-xl font-black text-gray-900 leading-tight mb-2"%s</h3>\n'
            '            <p class="text-sm text-gray-600 leading-relaxed"%s</p>\n'
            '          </div>'
            % (emoji, attr_ru(t_uk, t_ru), attr_ru(d_uk, d_ru))
            for emoji, t_uk, t_ru, d_uk, d_ru in b[1])
        return ('      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6 mt-4">\n%s\n      </div>'
                % cards)

    if kind == "steps":
        steps = "\n".join(
            '          <li class="flex gap-4 items-start">\n'
            '            <span class="flex-none w-9 h-9 rounded-2xl bg-fox-500 text-white '
            'font-black text-base flex items-center justify-center shadow-fox-sm" '
            'aria-hidden="true">%d</span>\n'
            '            <div>\n'
            '              <h3 class="text-base font-black text-gray-900 leading-tight mb-1"%s</h3>\n'
            '              <p class="text-sm text-gray-600 leading-relaxed"%s</p>\n'
            '            </div>\n'
            '          </li>'
            % (i + 1, attr_ru(t_uk, t_ru), attr_ru(d_uk, d_ru))
            for i, (t_uk, t_ru, d_uk, d_ru) in enumerate(b[1]))
        return ('      <ol class="flex flex-col gap-5 mb-6 mt-4">\n%s\n      </ol>' % steps)

    if kind == "table":
        head, rows = b[1], b[2]
        th = "".join(
            '<th scope="col" class="text-left font-black text-gray-900 text-sm px-4 py-3'
            '%s"%s</th>'
            % (" whitespace-nowrap" if max(len(uk), len(ru)) <= 24 else "",
               attr_ru(uk, ru))
            for uk, ru in head)
        # «3 600 грн» у вузькій колонці розривалося на два рядки й читалося як
        # два різні числа. Короткі клітинки не переносимо; довгі лишаємо як є,
        # інакше таблиця розсуне себе далеко за межі екрана.
        def cell(uk, ru):
            nowrap = " whitespace-nowrap" if max(len(uk), len(ru)) <= 24 else ""
            return ('<td class="px-4 py-3 text-sm text-gray-600 align-top%s"%s</td>'
                    % (nowrap, attr_ru(uk, ru)))

        tr = "\n".join(
            "          <tr class=\"border-t border-fox-100\">%s</tr>"
            % "".join(cell(uk, ru) for uk, ru in row)
            for row in rows)
        # overflow-x-auto обов'язковий: на 375 px таблиця з трьох колонок інакше
        # розсуває сторінку й ламає горизонтальний скрол усього документа.
        return ('      <div class="overflow-x-auto mb-6 mt-4 rounded-3xl border border-fox-100 bg-white">\n'
                '        <table class="w-full min-w-[520px]">\n'
                '          <thead class="bg-fox-50">%s</thead>\n'
                '          <tbody>\n%s\n          </tbody>\n'
                '        </table>\n      </div>' % (th, tr))

    if kind == "notelink":
        # Callout із посиланням. Потрібен там, де сторінка про онлайн-формат
        # мусить чесно сказати про очні класи й одразу дати туди дорогу.
        _, uk, ru, href, l_uk, l_ru = b
        return ('      <div class="bg-violet-50 border-l-4 border-violet-500 rounded-r-3xl px-6 py-5 mb-6 mt-4">\n'
                '        <p class="text-base text-gray-700 leading-relaxed font-semibold mb-2"%s</p>\n'
                '        <a href="%s" class="inline-flex items-center gap-1.5 text-sm font-black '
                'text-violet-600 hover:text-violet-500 transition-colors duration-200"%s</a>\n'
                '      </div>'
                % (attr_ru(uk, ru), href, attr_ru(l_uk + " →", l_ru + " →")))

    if kind == "callout":
        return ('      <div class="bg-fox-50 border-l-4 border-fox-500 rounded-r-3xl px-6 py-5 mb-6 mt-4">\n'
                '        <p class="text-base text-gray-700 leading-relaxed font-semibold"%s</p>\n'
                '      </div>' % attr_ru(b[1], b[2]))

    raise ValueError("невідомий блок: " + kind)


# ── розмітка ─────────────────────────────────────────────────────────────────

def build_graph(p):
    url = "%s/%s" % (BASE, p["slug"])
    graph = [
        {
            "@type": "WebPage",
            "@id": url + "#webpage",
            "url": url,
            "name": p["title_uk"],
            "description": p["desc_uk"],
            "inLanguage": "uk",
            "isPartOf": {"@id": BASE + "/#website"},
            "breadcrumb": {"@id": url + "#breadcrumb"},
            "about": {"@id": ORG},
            "primaryImageOfPage": {"@type": "ImageObject", "url": BASE + "/og-image.jpg"},
        },
        {
            "@type": "BreadcrumbList",
            "@id": url + "#breadcrumb",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "item": {"@id": BASE + "/", "name": "Головна"}},
                {"@type": "ListItem", "position": 2,
                 "item": {"@id": url, "name": p["crumb_uk"]}},
            ],
        },
    ]
    graph.extend(p.get("schema", []))
    if p.get("faq"):
        graph.append({
            "@type": "FAQPage",
            "@id": url + "#faq",
            "isPartOf": {"@id": url + "#webpage"},
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a, _, _ in p["faq"]
            ],
        })
    return json.dumps({"@context": "https://schema.org", "@graph": graph},
                      ensure_ascii=False, separators=(",", ":"))


# ── каркас ───────────────────────────────────────────────────────────────────

HEAD = """<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>

<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);}})(window,document,'script','dataLayer','GTM-MLTS9FQ3');</script>
<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-K60LSESFTV"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-K60LSESFTV');</script>

<title>{title_uk}</title>
<meta name="description" content="{desc_uk}"/>
<meta name="robots" content="index, follow"/>
<meta name="author" content="FluentFox"/>
<link rel="canonical" href="{url}"/>
<link rel="alternate" hreflang="uk" href="{url}"/>
<link rel="alternate" hreflang="ru" href="{url}?lang=ru"/>
<link rel="alternate" hreflang="x-default" href="{url}"/>

<meta property="og:type" content="website"/>
<meta property="og:site_name" content="FluentFox"/>
<meta property="og:title" content="{og_title_uk}"/>
<meta property="og:description" content="{desc_uk}"/>
<meta property="og:url" content="{url}"/>
<meta property="og:image" content="{base}/og-image.jpg"/>
<meta property="og:image:width" content="1200"/>
<meta property="og:image:height" content="630"/>
<meta property="og:image:alt" content="FluentFox — онлайн-школа англійської для дітей"/>
<meta property="og:locale" content="uk_UA"/>
<meta property="og:locale:alternate" content="ru_UA"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{og_title_uk}"/>
<meta name="twitter:description" content="{desc_uk}"/>
<meta name="twitter:image" content="{base}/og-image.jpg"/>

<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#129418;</text></svg>"/>
<meta name="theme-color" content="#FF6B35"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800;900&display=swap" rel="stylesheet"/>

<script type="application/ld+json">{graph}</script>

<!-- ?lang=ru: title і description підміняються до відмальовки, інакше в історії
     браузера й у метриці лишається український заголовок російської сторінки -->
<script>
(function(){{
  if(new URLSearchParams(location.search).get('lang')!=='ru') return;
  document.title='{title_ru}';
  var d=document.querySelector('meta[name="description"]'); if(d) d.content='{desc_ru}';
  var ot=document.querySelector('meta[property="og:title"]'); if(ot) ot.content='{og_title_ru}';
  var od=document.querySelector('meta[property="og:description"]'); if(od) od.content='{desc_ru}';
}})();
</script>

<link rel="preload" as="style" href="/css/style.css?v={cssv}"/>
<link rel="stylesheet" href="/css/style.css?v={cssv}" fetchpriority="high"/>
<style>
  * {{ scroll-behavior: smooth; }}
  .gradient-text {{
    background: linear-gradient(135deg, #FF6B35 0%, #E54E1A 100%);
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
  }}
  /* Рідний <details> замість акордеона на Alpine: питання лишаються в DOM
     розгорнутими для краулера й читаються без жодного скрипта. */
  details > summary {{ list-style: none; cursor: pointer; }}
  details > summary::-webkit-details-marker {{ display: none; }}
  details[open] .faq-chevron {{ transform: rotate(180deg); }}
</style>
</head>
<body class="font-sans antialiased text-gray-800 bg-cream">
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-MLTS9FQ3" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
"""

HEADER = """
<header class="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-fox-100">
  <nav class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex items-center justify-between h-16">
      <a href="/" class="flex items-center gap-2 flex-none">
        <span class="text-3xl" aria-hidden="true">&#129418;</span>
        <span class="text-2xl font-black text-gray-900">Fluent<span class="gradient-text">Fox</span></span>
      </a>

      <ul class="hidden nav:flex items-center gap-6">
        <li><a href="/#about" class="text-sm font-semibold text-gray-600 hover:text-fox-500 transition-colors duration-200" data-ru="О школе">Про школу</a></li>
        <li><a href="/#program" class="text-sm font-semibold text-gray-600 hover:text-fox-500 transition-colors duration-200" data-ru="Программа">Програма</a></li>
        <li><a href="/tsiny" class="text-sm font-semibold text-gray-600 hover:text-fox-500 transition-colors duration-200" data-ru="Цены">Ціни</a></li>
        <li><a href="/vidhuky" class="text-sm font-semibold text-gray-600 hover:text-fox-500 transition-colors duration-200" data-ru="Отзывы">Відгуки</a></li>
        <li><a href="/blog/" class="text-sm font-semibold text-gray-600 hover:text-fox-500 transition-colors duration-200">Блог</a></li>
      </ul>

      <div class="flex items-center gap-3">
        <a href="tel:+380954624672" class="hidden nav:inline text-sm font-bold text-gray-700 hover:text-fox-500 transition-colors duration-200">+38 (095) 462-46-72</a>
        <div class="flex items-center bg-gray-100 rounded-full p-0.5 text-sm font-bold">
          <button type="button" data-lang-btn="uk" class="px-2.5 py-1 rounded-full transition-all duration-200">UA</button>
          <button type="button" data-lang-btn="ru" class="px-2.5 py-1 rounded-full transition-all duration-200">RU</button>
        </div>
        <a href="/probnyi-urok" class="hidden sm:inline-flex bg-fox-500 hover:bg-fox-600 text-white font-black text-sm px-4 py-2 rounded-full shadow-fox-sm hover:shadow-fox transition-all duration-200 hover:-translate-y-0.5 whitespace-nowrap" data-ru="Пробный урок">Пробний урок</a>
        <button type="button" id="burger" class="nav:hidden flex flex-col gap-1 p-2 -mr-2" aria-label="Меню" data-ru-aria="Меню" aria-expanded="false" aria-controls="mobileMenu">
          <span class="block w-5 h-0.5 bg-gray-800 rounded-full"></span>
          <span class="block w-5 h-0.5 bg-gray-800 rounded-full"></span>
          <span class="block w-5 h-0.5 bg-gray-800 rounded-full"></span>
        </button>
      </div>
    </div>

    <div id="mobileMenu" hidden class="nav:hidden border-t border-fox-100 py-4">
      <ul class="flex flex-col gap-3">
        <li><a href="/#about" class="block text-base font-semibold text-gray-700 py-2" data-ru="О школе">Про школу</a></li>
        <li><a href="/#program" class="block text-base font-semibold text-gray-700 py-2" data-ru="Программа">Програма</a></li>
        <li><a href="/tsiny" class="block text-base font-semibold text-gray-700 py-2" data-ru="Цены">Ціни</a></li>
        <li><a href="/vidhuky" class="block text-base font-semibold text-gray-700 py-2" data-ru="Отзывы">Відгуки</a></li>
        <li><a href="/blog/" class="block text-base font-semibold text-gray-700 py-2">Блог</a></li>
        <li><a href="tel:+380954624672" class="block text-base font-bold text-fox-600 py-2">+38 (095) 462-46-72</a></li>
        <li><a href="/probnyi-urok" class="block text-center bg-fox-500 text-white font-black text-base px-7 py-3 rounded-full shadow-fox mt-2" data-ru="Пробный урок">Пробний урок</a></li>
      </ul>
    </div>
  </nav>
</header>
"""

FOOTER = """
<footer class="bg-gray-950 text-gray-400 py-10">
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
      <div>
        <a href="/" class="flex items-center gap-2 mb-3">
          <span class="text-2xl" aria-hidden="true">&#129418;</span>
          <span class="text-xl font-black text-white">Fluent<span class="text-fox-500">Fox</span></span>
        </a>
        <p class="text-sm leading-relaxed" data-ru="Онлайн-школа английского языка для детей и подростков 6–18 лет.">Онлайн-школа англійської мови для дітей та підлітків 6–18 років.</p>
      </div>
      <div>
        <h2 class="text-sm font-black text-white mb-3" data-ru="Разделы">Розділи</h2>
        <ul class="flex flex-col gap-2 text-sm">
          <li><a href="/anhliyska-6-8-rokiv" class="hover:text-fox-400 transition-colors duration-200" data-ru="Английский 6–8 лет">Англійська 6–8 років</a></li>
          <li><a href="/anhliyska-9-12-rokiv" class="hover:text-fox-400 transition-colors duration-200" data-ru="Английский 9–12 лет">Англійська 9–12 років</a></li>
          <li><a href="/anhliyska-13-18-rokiv" class="hover:text-fox-400 transition-colors duration-200" data-ru="Английский 13–18 лет">Англійська 13–18 років</a></li>
          <li><a href="/pidhotovka-do-nmt" class="hover:text-fox-400 transition-colors duration-200" data-ru="Подготовка к НМТ">Підготовка до НМТ</a></li>
          <li><a href="/cambridge" class="hover:text-fox-400 transition-colors duration-200" data-ru="Экзамены Cambridge">Іспити Cambridge</a></li>
          <li><a href="/dnipro" class="hover:text-fox-400 transition-colors duration-200" data-ru="Английский в Днепре">Англійська у Дніпрі</a></li>
        </ul>
      </div>
      <div>
        <h2 class="text-sm font-black text-white mb-3" data-ru="Контакты">Контакти</h2>
        <ul class="flex flex-col gap-2 text-sm">
          <li><a href="tel:+380954624672" class="hover:text-fox-400 transition-colors duration-200">+38 (095) 462-46-72</a></li>
          <li><a href="tel:+380682522876" class="hover:text-fox-400 transition-colors duration-200">+38 (068) 252-28-76</a></li>
          <li><a href="mailto:fluent.fox.study@gmail.com" class="hover:text-fox-400 transition-colors duration-200">fluent.fox.study@gmail.com</a></li>
          <li data-ru="Днепр, пр. А. Поля 28а">Дніпро, пр. О. Поля 28а</li>
        </ul>
      </div>
    </div>
    <div class="border-t border-gray-800 pt-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div class="flex flex-wrap gap-x-5 gap-y-2 text-xs">
        <a href="/privacy.html" class="hover:text-fox-400 transition-colors duration-200" data-ru="Конфиденциальность">Конфіденційність</a>
        <a href="/offer.html" class="hover:text-fox-400 transition-colors duration-200" data-ru="Оферта">Оферта</a>
        <a href="/terms.html" class="hover:text-fox-400 transition-colors duration-200" data-ru="Правила">Правила</a>
        <a href="/returns.html" class="hover:text-fox-400 transition-colors duration-200" data-ru="Возврат средств">Повернення коштів</a>
        <a href="/cookies.html" class="hover:text-fox-400 transition-colors duration-200">Cookie</a>
      </div>
      <p class="text-xs text-gray-600">&copy; 2026 FluentFox</p>
    </div>
  </div>
</footer>

<script src="/js/lang.js" defer></script>
</body>
</html>
"""


def render_faq(p):
    if not p.get("faq"):
        return ""
    items = "\n".join(
        '        <details class="bg-white rounded-3xl border border-fox-100 px-6 py-4">\n'
        '          <summary class="flex items-center justify-between gap-4">\n'
        '            <h3 class="text-base md:text-lg font-black text-gray-900 leading-tight"%s</h3>\n'
        '            <span class="faq-chevron flex-none text-fox-500 font-black transition-transform duration-200" aria-hidden="true">&#9662;</span>\n'
        '          </summary>\n'
        '          <p class="text-base text-gray-600 leading-relaxed mt-3"%s</p>\n'
        '        </details>'
        % (attr_ru(q_uk, q_ru), attr_ru(a_uk, a_ru))
        for q_uk, a_uk, q_ru, a_ru in p["faq"])
    return """
<section class="py-8 md:py-20 bg-fox-50">
  <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="text-center mb-14">
      <span class="inline-block bg-white text-fox-600 font-bold text-sm px-4 py-1.5 rounded-full mb-4" data-ru="Вопросы">Питання</span>
      <h2 class="text-3xl md:text-4xl font-black text-gray-900 mb-3 leading-tight" data-ru="Частые вопросы">Часті питання</h2>
    </div>
    <div class="flex flex-col gap-4">
%s
    </div>
  </div>
</section>
""" % items


def render_related(p):
    if not p.get("related"):
        return ""
    cards = "\n".join(
        '        <a href="%s" class="bg-white rounded-3xl p-6 border border-gray-100 '
        'hover:border-fox-200 hover:-translate-y-1 shadow-sm hover:shadow-md '
        'transition-all duration-300">\n'
        '          <span class="text-2xl" aria-hidden="true">%s</span>\n'
        '          <p class="font-black text-gray-900 text-base mt-2 leading-tight"%s</p>\n'
        '        </a>' % (href, emoji, attr_ru(t_uk, t_ru))
        for href, emoji, t_uk, t_ru in p["related"])
    return """
<section class="py-8 md:py-20 bg-white">
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
    <h2 class="text-2xl md:text-3xl font-black text-gray-900 mb-8 leading-tight" data-ru="Читайте также">Читайте також</h2>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
%s
    </div>
  </div>
</section>
""" % cards


CTA = """
<section class="py-8 md:py-16 bg-gradient-to-br from-fox-500 to-fox-600">
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
    <h2 class="text-2xl md:text-4xl font-black text-white mb-3 leading-tight" data-ru="Первый урок — бесплатно">Перший урок — безкоштовно</h2>
    <p class="text-base md:text-lg text-white/90 leading-relaxed mb-8" data-ru="Познакомимся с ребёнком, определим уровень и покажем, как проходят занятия. Без оплаты и без обязательств.">Познайомимось з дитиною, визначимо рівень і покажемо, як минають заняття. Без оплати та без зобов'язань.</p>
    <div class="flex flex-wrap gap-3 justify-center">
      <a href="/#form" class="inline-flex items-center bg-white text-fox-600 hover:bg-fox-50 font-black text-base px-7 py-3.5 rounded-full shadow-lg hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200" data-ru="Записаться на урок">Записатись на урок</a>
      <a href="tel:+380954624672" class="inline-flex items-center bg-fox-600 text-white hover:bg-fox-700 font-black text-base px-7 py-3.5 rounded-full shadow-lg hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200" data-ru="Позвонить">Зателефонувати</a>
    </div>
  </div>
</section>
"""


def render_page(p):
    url = "%s/%s" % (BASE, p["slug"])
    head = HEAD.format(
        title_uk=esc(p["title_uk"]), title_ru=p["title_ru"].replace("'", "\\'"),
        desc_uk=esc(p["desc_uk"]), desc_ru=p["desc_ru"].replace("'", "\\'"),
        og_title_uk=esc(p.get("og_uk", p["title_uk"])),
        og_title_ru=p.get("og_ru", p["title_ru"]).replace("'", "\\'"),
        url=url, base=BASE, graph=build_graph(p), cssv=CSS_VERSION)

    crumbs = ('\n<nav class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-6" aria-label="Хлібні крихти" data-ru-aria="Хлебные крошки">\n'
              '  <ol class="flex flex-wrap items-center gap-2 text-sm text-gray-400">\n'
              '    <li><a href="/" class="hover:text-fox-500 transition-colors duration-200" data-ru="Главная">Головна</a></li>\n'
              '    <li aria-hidden="true">/</li>\n'
              '    <li class="text-gray-600 font-semibold"%s</li>\n'
              '  </ol>\n</nav>\n' % attr_ru(p["crumb_uk"], p["crumb_ru"]))

    # Друга кнопка героя за замовчуванням веде на ціни — але на самій сторінці
    # цін це посилання саме на себе, тому там вона змінюється на пробний урок.
    cta2 = p.get("cta2") or (("/probnyi-urok", "Пробний урок", "Пробный урок")
                             if p["slug"] == "tsiny"
                             else ("/tsiny", "Дивитись ціни", "Смотреть цены"))

    hero = ('\n<section class="pt-8 pb-8 md:pb-14">\n'
            '  <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">\n'
            '    <span class="inline-block bg-fox-50 text-fox-600 font-bold text-sm px-4 py-1.5 rounded-full mb-4"%s</span>\n'
            '    <h1 class="text-3xl sm:text-4xl md:text-5xl font-black text-gray-900 leading-tight mb-5 max-w-3xl"%s</h1>\n'
            '    <p class="text-base md:text-lg text-gray-600 leading-relaxed max-w-2xl mb-8"%s</p>\n'
            '    <div class="flex flex-wrap gap-3">\n'
            '      <a href="/#form" class="inline-flex items-center bg-fox-500 hover:bg-fox-600 text-white font-black text-base px-7 py-3.5 rounded-full shadow-fox hover:shadow-fox-lg hover:-translate-y-1 transition-all duration-200" data-ru="Бесплатный урок">Безкоштовний урок</a>\n'
            '      <a href="%s" class="inline-flex items-center bg-white hover:bg-gray-50 text-gray-800 font-bold text-base px-7 py-3.5 rounded-full border border-gray-200 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-200"%s</a>\n'
            '    </div>\n'
            '  </div>\n</section>\n'
            % (attr_ru(p["badge_uk"], p["badge_ru"]),
               attr_ru(p["h1_uk"], p["h1_ru"]),
               attr_ru(p["lead_uk"], p["lead_ru"]),
               cta2[0], attr_ru(cta2[1], cta2[2])))

    body = "\n".join(render_block(b) for b in p["blocks"])
    main = ('\n<main>\n<section class="pb-8 md:pb-20">\n'
            '  <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">\n'
            '%s\n'
            '  </div>\n</section>\n' % body)

    return (head + HEADER + crumbs + hero + main + render_faq(p) + CTA
            + render_related(p) + "</main>\n" + FOOTER)


def main():
    built = []
    for p in C.PAGES:
        html = render_page(p)
        path = os.path.join(ROOT, p["slug"] + ".html")
        io.open(path, "w", encoding="utf-8", newline="\n").write(html)
        built.append((p["slug"], len(html), len(p["blocks"]), len(p.get("faq", []))))

    print("зібрано %d сторінок:" % len(built))
    for slug, size, blocks, faq in built:
        print("  /%-24s %6d Б  блоків: %-2d  FAQ: %d" % (slug, size, blocks, faq))


if __name__ == "__main__":
    main()
