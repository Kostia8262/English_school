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
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "i18n"))
sys.path.insert(0, os.path.join(ROOT, "tools", "sitemap"))

from assets import ASSET_VERSION  # noqa: E402  — спільна версія ?v= для всього сайту
from icons_map import icon  # noqa: E402  — емодзі в джерелі, <img> на сторінці
from html_min import squeeze  # noqa: E402  — коментарі й відступи лишаються в джерелі
import ru_pages as RU        # noqa: E402  — російські версії тих самих сторінок
import graph as GRAPH        # noqa: E402  — переклад розмітки Schema.org
import lastmod as LASTMOD    # noqa: E402  — дати в sitemap.xml за вмістом
import content as C          # noqa: E402  — хелпери + три вікові сторінки
import pages_exams          # noqa: E402,F401  — НМТ і Cambridge, дописують C.PAGES
import pages_service        # noqa: E402,F401  — ціни, відгуки, школа, пробний урок
import pages_dnipro         # noqa: E402,F401  — локальна сторінка з двома класами
import pages_generic        # noqa: E402,F401  — курси, онлайн, репетитор, розмовна
import pages_niche          # noqa: E402,F401  — англійська з нуля, діти за кордоном
import pages_country        # noqa: E402,F401  — окремі країни: Польща
import home_blocks          # noqa: E402  — контакти, статті й модалка з головної

BASE = "https://fluent-fox.site"
ORG = BASE + "/#organization"

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
        return ('      <h2 class="text-xl sm:text-2xl md:text-4xl font-black text-gray-900 '
                'leading-tight mb-4 mt-8 sm:mt-12 first:mt-0"%s</h2>' % attr_ru(b[1], b[2]))

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
            '            %s\n'
            '            <h3 class="text-xl font-black text-gray-900 leading-tight mb-2"%s</h3>\n'
            '            <p class="text-sm text-gray-600 leading-relaxed"%s</p>\n'
            '          </div>'
            % (icon(emoji, "w-11 h-11 mb-3"), attr_ru(t_uk, t_ru), attr_ru(d_uk, d_ru))
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

    if kind == "chips":
        # Міста списком у тексті читаються як перелік, який хочеться проґавити;
        # тими самими пілюлями, що й мітка секції, вони читаються як факт.
        # Це не посилання — окремої сторінки під місто немає й не планується:
        # заняття онлайн, і місто не змінює ні розклад, ні ціну.
        items = "\n".join(
            '          <li class="bg-fox-50 text-fox-600 font-bold text-sm px-4 py-1.5 '
            'rounded-full"%s</li>' % attr_ru(uk, ru) for uk, ru in b[1])
        return ('      <ul class="flex flex-wrap gap-2 mb-6 mt-4">\n%s\n      </ul>'
                % items)

    if kind == "callout":
        return ('      <div class="bg-fox-50 border-l-4 border-fox-500 rounded-r-3xl px-6 py-5 mb-6 mt-4">\n'
                '        <p class="text-base text-gray-700 leading-relaxed font-semibold"%s</p>\n'
                '      </div>' % attr_ru(b[1], b[2]))

    if kind == "pay":
        # Поле суми, призначення і дві кнопки шлюзів. Поведінка — js/pay.js:
        # він шле суму на свій же /api/pay.php, той створює рахунок і повертає
        # адресу сторінки оплати шлюзу, куди браузер просто переходить.
        #
        # Без скрипта кнопки не працюють, і це єдине місце на сайті, де так.
        # Інакше й бути не може: рахунок підписується секретом мерчанта, а
        # секрет живе на сервері. Тому поруч стоїть телефон — щоб людина без
        # JS не впиралася в мертву кнопку, а знала, куди дзвонити.
        _, note_uk, note_ru = b
        return (
            '      <div class="bg-white rounded-3xl border border-fox-100 p-6 sm:p-8 '
            'shadow-sm mb-6 mt-4" data-pay>\n'
            '        <div class="flex flex-col gap-4 mb-5">\n'
            '          <label class="flex flex-col gap-2">\n'
            '            <span class="text-sm font-bold text-gray-700"'
            '%s</span>\n'
            '            <input type="number" inputmode="decimal" min="1" max="100000" '
            'step="1" value="1800" data-pay-amount '
            'class="w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 '
            'text-base font-medium text-gray-900 aria-[invalid=true]:border-red-400 '
            'aria-[invalid=true]:bg-red-50 transition-colors duration-200"/>\n'
            '          </label>\n'
            '          <label class="flex flex-col gap-2">\n'
            '            <span class="text-sm font-bold text-gray-700"%s</span>\n'
            '            <input type="text" maxlength="120" data-pay-purpose '
            'class="w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 '
            'text-base font-medium text-gray-900 transition-colors duration-200"%s/>\n'
            '          </label>\n'
            '        </div>\n'
            '        <div class="flex flex-col sm:flex-row gap-3">\n'
            '          <button type="button" data-pay-provider="mono" '
            'class="flex-1 bg-fox-500 hover:bg-fox-600 text-white font-black text-base '
            'px-7 py-3.5 rounded-full shadow-fox hover:shadow-fox-lg hover:-translate-y-1 '
            'transition-all duration-200 disabled:opacity-60 disabled:translate-y-0"'
            '%s</button>\n'
            '          <button type="button" data-pay-provider="wfp" '
            'class="flex-1 bg-white hover:bg-gray-50 text-gray-800 border border-gray-200 '
            'font-black text-base px-7 py-3.5 rounded-full shadow-sm hover:shadow-md '
            'hover:-translate-y-1 transition-all duration-200 disabled:opacity-60 '
            'disabled:translate-y-0"'
            '%s</button>\n'
            '        </div>\n'
            '        <p class="text-sm text-gray-500 leading-relaxed mt-4 empty:hidden '
            'data-[state=error]:text-red-600 data-[state=error]:font-semibold" '
            'data-pay-status role="status" aria-live="polite"></p>\n'
            '        <p class="text-sm text-gray-500 leading-relaxed mt-4"%s</p>\n'
            '      </div>'
            % (attr_ru("Сума, грн", "Сумма, грн"),
               attr_ru("Призначення платежу", "Назначение платежа"),
               ' placeholder="%s" data-ru-placeholder="%s"'
               % (esc("Оплата навчання, Марія, вересень"),
                  esc("Оплата обучения, Мария, сентябрь")),
               attr_ru("Оплатити через MonoPay", "Оплатить через MonoPay"),
               attr_ru("Оплатити через WayForPay", "Оплатить через WayForPay"),
               attr_ru(note_uk, note_ru)))

    raise ValueError("невідомий блок: " + kind)


# ── вікові картки на всю ширину ─────────────────────────────

def render_agegroups(p):
    """Секція з вікових карток — та сама, що колись відкривала головну.

    Не блок, а окрема секція: всередині max-w-3xl три такі картки стиснулися б
    до 230 px, а в них і чипси формату, і шкала CEFR на чотири поділки. Тому
    вона малюється поза колонкою тексту, одразу під геро, і повторює верстку
    головної один в один — з тією різницею, що текст тут статичний, а російська
    версія живе в data-ru, як і на решті сторінки.

    .card-lift сюди не годиться: цей клас оголошено в <style> головної, а не в
    style.css. Той самий підйом зібрано утилітами.
    """
    if not p.get("agegroups"):
        return ""
    g = C.AGE_GROUPS
    cards = []
    for c in g["cards"]:
        chips = "".join(
            '<span class="inline-flex items-center gap-1 bg-gray-50 border border-gray-200 '
            'text-gray-600 text-xs font-semibold px-2.5 py-1 rounded-full"%s</span>'
            % attr_ru(uk, ru) for uk, ru in c["format"])
        items = "\n".join(
            '            <li class="flex items-start gap-2 text-sm text-gray-600">'
            '<span class="w-5 h-5 rounded-full bg-fox-50 flex items-center justify-center '
            'flex-shrink-0 mt-0.5"><svg class="w-3 h-3 text-fox-500" fill="none" '
            'stroke="currentColor" stroke-width="3" viewBox="0 0 24 24" aria-hidden="true">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>'
            '</span><span%s</span></li>' % attr_ru(uk, ru) for uk, ru in c["items"])
        track = "".join(
            '<div class="flex-1 text-center">'
            '<div class="h-1.5 rounded-full mb-1.5 %s"></div>'
            '<span class="text-2xs font-bold %s">%s</span></div>'
            % ("bg-fox-500" if on else "bg-gray-100",
               "text-fox-600" if on else "text-gray-300", lv)
            for lv, on in c["track"])
        cards.append(
            '        <div class="bg-white border-2 border-gray-100 rounded-3xl p-8 shadow-sm '
            'flex flex-col transition-all duration-300 hover:-translate-y-1 hover:shadow-fox-lg">\n'
            '          <div class="flex items-center justify-between mb-5">\n'
            '            <div class="w-14 h-14 rounded-2xl bg-fox-50 border-2 border-fox-100 '
            'flex items-center justify-center text-3xl" aria-hidden="true">%s</div>\n'
            '            <div class="inline-block bg-fox-50 text-fox-600 font-bold text-xs '
            'px-3 py-1 rounded-full"%s</div>\n'
            '          </div>\n'
            '          <h3 class="text-xl font-black text-gray-900 mb-4"%s</h3>\n'
            '          <div class="flex flex-wrap gap-2 mb-5">%s</div>\n'
            '          <ul class="flex flex-col gap-2 mb-6">\n%s\n          </ul>\n'
            '          <div class="mt-auto pt-5 border-t border-gray-100">\n'
            '            <p class="text-2xs font-black text-gray-400 uppercase tracking-widest mb-2"%s</p>\n'
            '            <div class="flex gap-1.5 mb-4">%s</div>\n'
            '            <div class="bg-fox-50 rounded-xl px-4 py-3">\n'
            '              <p class="text-2xs font-black text-fox-600 uppercase tracking-widest mb-1"%s</p>\n'
            '              <p class="text-sm text-gray-700 leading-tight"%s</p>\n'
            '            </div>\n'
            '            <a href="%s" class="inline-flex items-center gap-1.5 mt-4 text-sm '
            'font-black text-fox-600 hover:text-fox-700 transition-colors duration-200"%s</a>\n'
            '          </div>\n'
            '        </div>'
            % (icon(c["emoji"], "w-11 h-11"), attr_ru(*c["range"]), attr_ru(*c["title"]), chips, items,
               attr_ru(*g["level_label"]), track,
               attr_ru(*g["result_label"]), attr_ru(*c["result"]), c["href"],
               attr_ru(g["more"][0] + " →", g["more"][1] + " →")))

    return ('\n<section class="py-12 md:py-20 bg-fox-50">\n'
            '  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">\n'
            '    <div class="text-center mb-10 md:mb-14">\n'
            '      <span class="inline-block bg-white text-fox-600 font-bold text-sm px-4 '
            'py-1.5 rounded-full mb-4 shadow-sm"%s</span>\n'
            '      <h2 class="text-xl sm:text-2xl md:text-4xl font-black text-gray-900 leading-tight mb-3"%s</h2>\n'
            '      <p class="text-gray-500 text-base md:text-lg max-w-xl mx-auto"%s</p>\n'
            '    </div>\n'
            '    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">\n%s\n    </div>\n'
            '  </div>\n</section>\n'
            % (attr_ru(*g["label"]), attr_ru(*g["title"]), attr_ru(*g["subtitle"]),
               "\n".join(cards)))


# ── розмітка ─────────────────────────────────────────────────────────────────

def build_graph(p, lang="uk"):
    """Граф сторінки. Російська версія — той самий граф, перекладений за
    словником: див. tools/i18n/graph.py, там і пояснено чому саме так.

    Виняток — FAQ. Решту графа перекладати справді нізвідки, а питання й
    відповіді лежать тут-таки, обома мовами: у кожного запису чотири поля,
    uk-питання, uk-відповідь, ru-питання, ru-відповідь. Ганяти їх через
    словник означало б тримати той самий текст іще й там — і щоразу, коли на
    сторінці з'являється нове питання, складання падало б, вимагаючи
    переписати в graph_ru.json те, що вже написано. Тому вузол FAQPage
    будується для російської сторінки одразу з російського тексту.
    """
    nodes = graph_nodes(p)
    if lang == "ru":
        own = "%s/%s" % (BASE, p["slug"])
        nodes = [n for n in nodes if n.get("@type") != "FAQPage"]
        nodes = GRAPH.localize(nodes, own=own)
        faq = faq_node(p, own + "?lang=ru", ru=True)
        if faq:
            nodes.append(faq)
    return json.dumps({"@context": "https://schema.org", "@graph": nodes},
                      ensure_ascii=False, separators=(",", ":"))


def faq_node(p, url, ru=False):
    """Вузол FAQPage. `url` веде на конкретну відповідь: номер у розмітці той
    самий, що в `id` її <details>. Доти `@id` вузла закінчувався на `#faq`, а
    елемента з таким `id` на сторінці не було взагалі."""
    if not p.get("faq"):
        return None
    q_i, a_i = (2, 3) if ru else (0, 1)
    return {
        "@type": "FAQPage",
        "@id": url + "#faq",
        "isPartOf": {"@id": url + "#webpage"},
        "mainEntity": [
            {"@type": "Question", "name": item[q_i],
             "url": "%s#faq-%d" % (url, i + 1),
             "acceptedAnswer": {"@type": "Answer", "text": item[a_i]}}
            for i, item in enumerate(p["faq"])
        ],
    }


def graph_nodes(p):
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
            "primaryImageOfPage": {"@type": "ImageObject", "url": BASE + "/og/" + p["slug"] + ".jpg"},
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
    faq = faq_node(p, url)
    if faq:
        graph.append(faq)
    return graph


# ── каркас ───────────────────────────────────────────────────────────────────

HEAD = """<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>

<!-- Google Analytics 4. Контейнера GTM тут більше немає: він був порожній
     («tags»:[]), тобто 331 КБ рушія на кожне завантаження не робили нічого,
     а лічильник і так стоїть прямим gtag.js. -->
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
<meta property="og:image" content="{base}/og/{slug}.jpg"/>
<meta property="og:image:width" content="1200"/>
<meta property="og:image:height" content="630"/>
<meta property="og:image:alt" content="FluentFox — онлайн-школа англійської для дітей"/>
<meta property="og:locale" content="uk_UA"/>
<!-- ru_RU, а не ru_UA: месенджери знають лише перелік локалей, ru_UA у ньому немає (див. tools/i18n/ru_pages.py). -->
<meta property="og:locale:alternate" content="ru_RU"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{og_title_uk}"/>
<meta name="twitter:description" content="{desc_uk}"/>
<meta name="twitter:image" content="{base}/og/{slug}.jpg"/>

<!-- ═══ Favicon ═══ -->
<link rel="icon" href="/favicon.ico" sizes="any"/>
<link rel="icon" type="image/png" sizes="96x96" href="/favicon-96x96.png"/>
<link rel="icon" type="image/png" sizes="192x192" href="/favicon-192x192.png"/>
<link rel="apple-touch-icon" href="/apple-touch-icon.png"/>
<meta name="theme-color" content="#FF6B35"/>
<!-- Шрифт свій, правила @font-face — усередині style.css. Підмножина
     cyrillic несе весь текст сторінки, тому її беремо наперед, не чекаючи,
     доки браузер дочитає таблицю стилів. -->
<link rel="preload" as="font" type="font/woff2" href="/fonts/nunito-cyrillic.woff2" crossorigin/>

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

<link rel="preload" as="style" href="/css/style.css?v={assetv}"/>
<link rel="stylesheet" href="/css/style.css?v={assetv}" fetchpriority="high"/>
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

  /* Далі — правила, без яких перенесені з головної блоки (контакти з формою
     і модалка) працюють неправильно.

     [hidden] з !important: і форма, і вікно ховаються саме цим атрибутом, а
     в їхніх класах стоїть flex або grid — браузерне display:none для
     [hidden] такий клас перебиває. Без цього рядка модалка з атрибутом
     hidden лишалася на екрані затемненням; так і сталося на першій складанні.

     Підсвітка поля у фокусі — те саме правило, що на головній. Дві змінні
     оголошені тут, бо решта :root головної живе в її інлайновому <style>. */
  :root {{ --fox-500: #FF6B35; --fox-ring: rgba(255,107,53,0.18); }}
  [hidden] {{ display: none !important; }}
  .form-input:focus {{
    outline: none;
    border-color: var(--fox-500) !important;
    box-shadow: 0 0 0 3px var(--fox-ring);
  }}
</style>
</head>
<body class="font-sans antialiased text-gray-800 bg-cream">
"""

HEADER = """
<header class="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-fox-100">
  <nav class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex items-center justify-between h-16">
      <a href="/" class="flex items-center gap-2 flex-none">
        <img src="/logo.svg" alt="" width="36" height="36" class="w-9 h-9 flex-none" fetchpriority="high" decoding="async">
        <span class="flex flex-col leading-none">
          <span class="text-2xl font-black text-gray-900 leading-none">Fluent<span class="gradient-text">Fox</span></span>
          <span class="text-2xs font-bold uppercase tracking-widest text-gray-500 mt-1">English School</span>
        </span>
      </a>

      <ul class="hidden nav:flex items-center gap-6">
        <li><a href="/#about" class="text-sm font-semibold text-gray-600 hover:text-fox-500 transition-colors duration-200" data-ru="О школе">Про школу</a></li>
        <li><a href="/#program" class="text-sm font-semibold text-gray-600 hover:text-fox-500 transition-colors duration-200" data-ru="Программа">Програма</a></li>
        <li><a href="/tsiny" class="text-sm font-semibold text-gray-600 hover:text-fox-500 transition-colors duration-200" data-ru="Цены">Ціни</a></li>
        <li><a href="/blog/" class="text-sm font-semibold text-gray-600 hover:text-fox-500 transition-colors duration-200">Блог</a></li>
        <!-- Замість «Відгуків» — контакти: блок із телефонами й месенджерами
             тепер є на самій сторінці (#contacts), тож посилання веде на
             екран нижче, а не на іншу сторінку. На /vidhuky досі ведуть
             картки «Читайте також» і підвал. -->
        <li><a href="#contacts" class="text-sm font-semibold text-gray-600 hover:text-fox-500 transition-colors duration-200" data-ru="Контакты">Контакти</a></li>
      </ul>

      <div class="flex items-center gap-3">
        <a href="tel:+380954624672" class="hidden nav:inline text-sm font-bold text-gray-700 hover:text-fox-500 transition-colors duration-200">+38 (095) 462-46-72</a>
        <!-- Перемикач мови — посилання, а не кнопка. Кнопку, що міняє
             location.href, краулер не натискає: єдиною дорогою до ?lang=ru
             лишалися hreflang і карта сайту. Цього досить, щоб адресу знали,
             і замало, щоб вона отримувала вагу перелінковки. Клік усе одно
             перехоплює js/lang.js — щоб не загубити якір і решту запиту. -->
        <div class="flex items-center bg-gray-100 rounded-full p-0.5 text-sm font-bold">
          <a href="%(path)s" hreflang="uk" data-lang-btn="uk" class="px-2.5 py-1 rounded-full transition-all duration-200">UA</a>
          <a href="%(path)s?lang=ru" hreflang="ru" data-lang-btn="ru" class="px-2.5 py-1 rounded-full transition-all duration-200">RU</a>
        </div>
        <a href="/probnyi-urok" data-modal="open" class="hidden sm:inline-flex bg-fox-500 hover:bg-fox-600 text-white font-black text-sm px-4 py-2 rounded-full shadow-fox-sm hover:shadow-fox transition-all duration-200 hover:-translate-y-0.5 whitespace-nowrap" data-ru="Пробный урок">Пробний урок</a>
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
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-8 mb-8">
      <div>
        <a href="/" class="flex items-center gap-2 mb-3">
          <img src="/logo.svg" alt="" width="36" height="36" class="w-9 h-9 flex-none" loading="lazy" decoding="async">
          <span class="flex flex-col leading-none">
            <span class="text-xl font-black text-white leading-none">Fluent<span class="text-fox-500">Fox</span></span>
            <span class="text-2xs font-bold uppercase tracking-widest text-gray-400 mt-1">English School</span>
          </span>
        </a>
        <p class="text-sm leading-relaxed" data-ru="Онлайн-школа английского языка для детей и подростков 6–18 лет.">Онлайн-школа англійської мови для дітей та підлітків 6–18 років.</p>
        <div class="flex gap-3 mt-4">
        <a href="https://www.instagram.com/fluent.fox.study/" target="_blank" rel="noopener" aria-label="Instagram" class="w-9 h-9 bg-gray-800 hover:bg-fox-500 rounded-xl flex items-center justify-center transition-all duration-200 text-white">
        <svg viewBox="0 0 24 24" fill="currentColor" class="w-4 h-4"><path d="M12 2.16c3.2 0 3.58.01 4.85.07 3.25.15 4.77 1.69 4.92 4.92.06 1.27.07 1.65.07 4.85 0 3.2-.01 3.58-.07 4.85-.15 3.23-1.66 4.77-4.92 4.92-1.27.06-1.64.07-4.85.07-3.2 0-3.58-.01-4.85-.07-3.26-.15-4.77-1.7-4.92-4.92C2.17 15.58 2.16 15.2 2.16 12c0-3.2.01-3.58.07-4.85C2.38 3.86 3.9 2.31 7.15 2.23 8.42 2.17 8.8 2.16 12 2.16zM12 0C8.74 0 8.33.01 7.05.07 2.7.27.27 2.7.07 7.05.01 8.33 0 8.74 0 12c0 3.26.01 3.67.07 4.95.2 4.36 2.62 6.78 6.98 6.98C8.33 23.99 8.74 24 12 24c3.26 0 3.67-.01 4.95-.07 4.35-.2 6.78-2.62 6.98-6.98.06-1.28.07-1.69.07-4.95 0-3.26-.01-3.67-.07-4.95-.2-4.35-2.62-6.78-6.98-6.98C15.67.01 15.26 0 12 0zm0 5.84a6.16 6.16 0 1 0 0 12.32A6.16 6.16 0 0 0 12 5.84zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.4-11.85a1.44 1.44 0 1 0 0 2.88 1.44 1.44 0 0 0 0-2.88z"/></svg>
        </a>
        <a href="https://t.me/Artist8262" target="_blank" rel="noopener" aria-label="Telegram" class="w-9 h-9 bg-gray-800 hover:bg-fox-500 rounded-xl flex items-center justify-center transition-all duration-200 text-white">
        <svg viewBox="-3 -3 30 30" fill="currentColor" class="w-4 h-4"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>
        </a>
        <a href="https://www.facebook.com/people/FluentFoxAcademy/61591810049590/" target="_blank" rel="noopener" aria-label="Facebook" class="w-9 h-9 bg-gray-800 hover:bg-fox-500 rounded-xl flex items-center justify-center transition-all duration-200 text-white">
        <svg viewBox="0 0 24 24" fill="currentColor" class="w-4 h-4"><path d="M24 12.07C24 5.41 18.63 0 12 0S0 5.4 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.04V9.41c0-3.02 1.8-4.7 4.54-4.7 1.31 0 2.68.24 2.68.24v2.97h-1.5c-1.5 0-1.96.93-1.96 1.89v2.26h3.32l-.53 3.5h-2.8V24C19.62 23.1 24 18.1 24 12.07z"/></svg>
        </a>
        </div>
      </div>
      <div>
        <h3 class="text-sm font-black text-white mb-3" data-ru="Разделы">Розділи</h3>
        <ul class="flex flex-col gap-2 text-sm">
          <li><a href="/anhliyska-6-8-rokiv" class="hover:text-fox-400 transition-colors duration-200" data-ru="Английский 6–8 лет">Англійська 6–8 років</a></li>
          <li><a href="/anhliyska-9-12-rokiv" class="hover:text-fox-400 transition-colors duration-200" data-ru="Английский 9–12 лет">Англійська 9–12 років</a></li>
          <li><a href="/anhliyska-13-18-rokiv" class="hover:text-fox-400 transition-colors duration-200" data-ru="Английский 13–18 лет">Англійська 13–18 років</a></li>
          <li><a href="/kursy-anhliyskoyi-dlya-ditey" class="hover:text-fox-400 transition-colors duration-200" data-ru="Курсы английского">Курси англійської</a></li>
          <li><a href="/anhliyska-onlayn-dlya-ditey" class="hover:text-fox-400 transition-colors duration-200" data-ru="Английский онлайн">Англійська онлайн</a></li>
          <li><a href="/repetytor-z-anhliyskoyi" class="hover:text-fox-400 transition-colors duration-200" data-ru="Репетитор по английскому">Репетитор з англійської</a></li>
          <li><a href="/rozmovna-anhliyska-dlya-ditey" class="hover:text-fox-400 transition-colors duration-200" data-ru="Разговорный английский">Розмовна англійська</a></li>
          <li><a href="/anhliyska-z-nulya-dlya-ditey" class="hover:text-fox-400 transition-colors duration-200" data-ru="Английский с нуля">Англійська з нуля</a></li>
          <li><a href="/pidhotovka-do-nmt" class="hover:text-fox-400 transition-colors duration-200" data-ru="Подготовка к НМТ">Підготовка до НМТ</a></li>
          <li><a href="/cambridge" class="hover:text-fox-400 transition-colors duration-200" data-ru="Экзамены Cambridge">Іспити Cambridge</a></li>
          <li><a href="/dnipro" class="hover:text-fox-400 transition-colors duration-200" data-ru="Английский в Днепре">Англійська у Дніпрі</a></li>
          <li><a href="/pro-shkolu" class="hover:text-fox-400 transition-colors duration-200" data-ru="О школе">Про школу</a></li>
        </ul>
      </div>
      <div>
        <h3 class="text-sm font-black text-white mb-3" data-ru="Наши школы">Наші школи</h3>
        <ul class="flex flex-col gap-2 text-sm">
          <li><a href="https://mycomputer.education/" target="_blank" rel="noopener" class="hover:text-fox-400 transition-colors duration-200" data-ru="Школа программирования">Школа програмування</a></li>
          <li><a href="https://mycomputer.school/" target="_blank" rel="noopener" class="hover:text-fox-400 transition-colors duration-200" data-ru="Школа дизайна">Школа дизайну</a></li>
          <li><a href="https://child.mycomputer.education/" target="_blank" rel="noopener" class="hover:text-fox-400 transition-colors duration-200" data-ru="Центр «Дошколярик»: развитие с 2,5 лет">Центр «Дошколярик»: розвиток з 2,5 років</a></li>
        </ul>
      </div>
      <div>
        <h3 class="text-sm font-black text-white mb-3" data-ru="Контакты">Контакти</h3>
        <ul class="flex flex-col gap-2 text-sm">
          <li><a href="tel:+380954624672" class="hover:text-fox-400 transition-colors duration-200">+38 (095) 462-46-72</a></li>
          <li><a href="tel:+380682522876" class="hover:text-fox-400 transition-colors duration-200">+38 (068) 252-28-76</a></li>
          <li class="min-w-0"><a href="mailto:fluent.fox.study@gmail.com" class="hover:text-fox-400 transition-colors duration-200 break-all">fluent.fox.study@gmail.com</a></li>
          <li data-ru="Днепр, пр. А. Поля 28а">Дніпро, пр. О. Поля 28а</li>
        </ul>
      </div>
    </div>
    <!-- Країни. Окремий рядок, а не ще одна колонка: колонок у сітці чотири, і
         п'ята ламає її на планшеті. Тут росте серія сторінок під країни, де
         живуть українські родини, тож рядок із переносом витримає і шість
         посилань. -->
    <div class="border-t border-gray-800 py-6">
      <h3 class="text-sm font-black text-white mb-3" data-ru="Детям за рубежом">Дітям за кордоном</h3>
      <ul class="flex flex-wrap gap-x-5 gap-y-2 text-sm">
        <li><a href="/anhliyska-dlya-ditey-u-polshchi" class="hover:text-fox-400 transition-colors duration-200" data-ru="Английский в Польше">Англійська у Польщі</a></li>
        <li><a href="/anhliyska-dlya-ditey-za-kordonom" class="hover:text-fox-400 transition-colors duration-200" data-ru="Все страны">Усі країни</a></li>
      </ul>
    </div>
    <!-- Підписка на листи: адреса йде в панель розсилки мережі (smm.mycomputer.education),
         яка одразу додає людину в базу й надсилає вітальний лист. Код тексту згоди —
         data-consent: змінили текст згоди — змінюйте код. Обробник — /js/subscribe.js. -->
    <div class="border-t border-gray-800 py-6 grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,440px)] md:gap-10 md:items-start">
      <div>
        <p class="text-base font-black text-white" data-ru="Письма от FluentFox">Листи від FluentFox</p>
        <p class="text-sm leading-relaxed text-gray-400 mt-1 max-w-md" data-ru="Новые курсы, разговорные клубы и советы, как поддержать английский дома. Отписаться — в один клик.">Нові курси, розмовні клуби й поради, як підтримати англійську вдома. Відписатися — в один клік.</p>
      </div>
      <form data-subscribe data-school="fluentfox" data-consent="footer-2026-09" data-endpoint="https://smm.mycomputer.education/s/subscribe" novalidate class="flex flex-col gap-2 min-w-0">
        <div class="flex flex-col sm:flex-row gap-2 min-w-0">
          <label for="footerSubscribeEmail" class="sr-only" data-ru="Ваш email">Ваш email</label>
          <input id="footerSubscribeEmail" type="email" name="email" inputmode="email" autocomplete="email" required placeholder="Ваш email" data-ru-placeholder="Ваш email" class="w-full sm:w-auto sm:flex-1 min-w-0 h-12 px-5 rounded-full bg-gray-900 border border-gray-700 text-white text-base placeholder-gray-500 transition-colors focus:outline-none focus:border-fox-500 focus:ring-2 focus:ring-fox-500/30 aria-[invalid=true]:border-red-500">
          <input class="sr-only" type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
          <button type="submit" class="h-12 px-7 rounded-full bg-fox-500 hover:bg-fox-600 text-white font-black transition-colors duration-200 disabled:opacity-60" data-ru="Подписаться">Підписатися</button>
        </div>
        <p class="text-xs leading-relaxed text-gray-500"><span data-ru="Нажимая «Подписаться», вы соглашаетесь получать письма и с">Натискаючи «Підписатися», ви погоджуєтесь отримувати листи та з</span> <a href="/privacy.html" class="underline hover:text-fox-400 transition-colors" data-ru="политикой конфиденциальности">політикою конфіденційності</a>.</p>
        <p data-subscribe-status role="status" aria-live="polite" class="text-sm text-gray-300 empty:hidden data-[state=ok]:text-green-400 data-[state=error]:text-red-400 [&_button]:font-bold [&_button]:underline [&_button]:text-fox-400"></p>
      </form>
    </div>
    <div class="border-t border-gray-800 pt-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div class="flex flex-wrap gap-x-5 gap-y-2 text-xs">
        <a href="/privacy.html" class="hover:text-fox-400 transition-colors duration-200" data-ru="Конфиденциальность">Конфіденційність</a>
        <a href="/offer.html" class="hover:text-fox-400 transition-colors duration-200" data-ru="Оферта">Оферта</a>
        <a href="/returns.html" class="hover:text-fox-400 transition-colors duration-200" data-ru="Возврат средств">Повернення коштів</a>
      </div>
      <p class="text-xs text-gray-600">&copy; 2026 FluentFox</p>
    </div>
  </div>
</footer>

<script src="/js/lang.js?v=%(assetv)s" defer></script>
<script src="/js/lead.js?v=%(assetv)s" defer></script>
<script src="/js/subscribe.js?v=%(assetv)s" defer></script>
<script src="/js/pay.js?v=%(assetv)s" defer></script>
</body>
</html>
"""


def render_faq(p):
    if not p.get("faq"):
        return ""
    items = "\n".join(
        '        <details class="bg-white rounded-3xl border border-fox-100 px-6 py-4" id="faq-%d">\n'
        '          <summary class="flex items-center justify-between gap-4">\n'
        '            <h3 class="text-base md:text-lg font-black text-gray-900 leading-tight"%s</h3>\n'
        '            <span class="faq-chevron flex-none text-fox-500 font-black transition-transform duration-200" aria-hidden="true">&#9662;</span>\n'
        '          </summary>\n'
        '          <p class="text-base text-gray-600 leading-relaxed mt-3"%s</p>\n'
        '        </details>'
        % (i + 1, attr_ru(q_uk, q_ru), attr_ru(a_uk, a_ru))
        for i, (q_uk, a_uk, q_ru, a_ru) in enumerate(p["faq"]))
    return """
<section class="py-8 md:py-20 bg-fox-50" id="faq">
  <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="text-center mb-8 md:mb-14">
      <span class="inline-block bg-white text-fox-600 font-bold text-sm px-4 py-1.5 rounded-full mb-4" data-ru="Вопросы">Питання</span>
      <h2 class="text-xl sm:text-2xl md:text-4xl font-black text-gray-900 mb-3 leading-tight" data-ru="Частые вопросы">Часті питання</h2>
    </div>
    <div class="flex flex-col gap-4">
%s
    </div>
  </div>
</section>
""" % items


def related_subtitle(href):
    """Один рядок під назву картки — мітка тієї сторінки, її `badge`.

    Навіщо так, а не четвертим полем у `related`. Картка з однією назвою не
    каже нічого, крім того, що сторінка існує: три великі прямокутники
    тримали три коротких рядки. Дописувати опис руками означало б четверте
    поле в кожному з ~45 записів `related` по всіх сторінках — і ще одну
    копію тексту, яка розійдеться з джерелом, як розійшлися колись FAQ. Тому
    підпис беремо з самої цільової сторінки.

    Саме `badge`, а не перше речення `desc`. По-перше, мітка коротка й
    написана як мітка («Онлайн · Zoom або Google Meet»), а опис — як речення,
    що переказує назву. По-друге, опис /tsiny містить «1800 або 3600 грн», і
    з ним у картці сторінка діставала 3600 і 3000 без 1800 — перевірка
    тарифної трійки в tools/audit/facts.py справедливо падала.

    Для статей блогу сторінки в PAGES немає — там лишається сама мітка.
    """
    slug = href.lstrip("/")
    if slug.startswith("blog/"):
        return ("Стаття в блозі", "Статья в блоге")
    for page in C.PAGES:
        if page["slug"] == slug:
            return (page["badge_uk"], page["badge_ru"])
    return None


def render_related(p):
    if not p.get("related"):
        return ""
    cards = []
    for href, emoji, t_uk, t_ru in p["related"]:
        sub = related_subtitle(href)
        sub_html = ('\n          <p class="text-sm text-gray-500 leading-relaxed mt-2"%s</p>'
                    % attr_ru(sub[0], sub[1])) if sub else ""
        cards.append(
            '        <a href="%s" class="group flex flex-col bg-white rounded-3xl p-6 '
            'border border-gray-100 hover:border-fox-200 hover:-translate-y-1 shadow-sm '
            'hover:shadow-md transition-all duration-300">\n'
            '          <span class="w-12 h-12 rounded-2xl bg-fox-50 flex items-center '
            'justify-center mb-4">%s</span>\n'
            '          <p class="font-black text-gray-900 text-xl leading-tight"%s</p>'
            '%s\n'
            '          <span class="inline-flex items-center gap-1.5 text-sm font-black '
            'text-fox-600 mt-auto pt-5"><span data-ru="Подробнее">Детальніше</span>'
            '<span class="transition-transform duration-200 group-hover:translate-x-1" '
            'aria-hidden="true">&rarr;</span></span>\n'
            '        </a>' % (href, icon(emoji, "w-7 h-7"), attr_ru(t_uk, t_ru), sub_html))
    return """
<section class="py-8 md:py-20 bg-white">
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
    <h2 class="text-xl sm:text-2xl md:text-3xl font-black text-gray-900 mb-6 sm:mb-8 leading-tight" data-ru="Читайте также">Читайте також</h2>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
%s
    </div>
  </div>
</section>
""" % "\n".join(cards)


def render_seo(p):
    """Підсумковий абзац унизу сторінки.

    Навіщо. Такий абзац був лише на головній, а посадкові закінчувалися
    картками «Читайте також» — тобто останнє, що бачив краулер, це три назви
    чужих сторінок. Тут сторінка своїми словами каже, про що вона: формат,
    ціна, вік, місто, — і звідти ж веде на суміжні сторінки контекстним
    посиланням, а не назвою в картці.

    Текст лежить у сторінці списком шматків: `(uk, ru)` — звичайний текст,
    `(href, uk, ru)` — посилання. Складати його з готового HTML не можна:
    увесь текст на цих сторінках екранується, а російська версія береться з
    `data-ru`, тож посилання має бути окремим вузлом із власним перекладом.
    """
    if not p.get("seo"):
        return ""
    parts = []
    for seg in p["seo"]:
        if len(seg) == 3:
            href, uk, ru = seg
            parts.append('<a class="font-semibold text-fox-600 hover:text-fox-700 '
                         'transition-colors duration-200" href="%s"%s</a>'
                         % (href, attr_ru(uk, ru)))
        else:
            parts.append("<span%s</span>" % attr_ru(seg[0], seg[1]))
    return ("""
<section class="py-8 md:py-16 bg-gradient-to-b from-white to-fox-50">
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
    <p class="text-sm sm:text-base leading-relaxed text-gray-500">%s</p>
  </div>
</section>
""" % "".join(parts))


# Банер перед «Читайте також». Був рівним оранжевим прямокутником із двома
# кнопками, з яких друга — темно-оранжева на оранжевому — читалася як
# вимкнена. Тепер: мітка над заголовком, декоративні плями під вмістом
# (overflow-hidden, тому за межі секції не виходять), контурна друга кнопка й
# рядок із трьох фактів, які знімають страх «а що це мені буде коштувати».
CTA = """
<section class="relative overflow-hidden py-10 md:py-16 bg-gradient-to-br from-fox-500 to-fox-600">
  <div class="absolute -top-20 -right-12 w-64 h-64 bg-white/10 rounded-4xl rotate-12" aria-hidden="true"></div>
  <div class="absolute -bottom-24 -left-16 w-72 h-72 bg-white/10 rounded-full" aria-hidden="true"></div>
  <div class="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
    <span class="inline-block bg-white/15 text-white font-bold text-sm px-4 py-1.5 rounded-full mb-4" data-ru="Пробный урок">Пробний урок</span>
    <h2 class="text-xl sm:text-2xl md:text-4xl font-black text-white mb-3 leading-tight" data-ru="Первый урок — бесплатно">Перший урок — безкоштовно</h2>
    <p class="text-base md:text-lg text-white/90 leading-relaxed mb-8 max-w-2xl mx-auto" data-ru="Познакомимся с ребёнком, определим уровень и покажем, как проходят занятия. Без оплаты и без обязательств.">Познайомимось з дитиною, визначимо рівень і покажемо, як минають заняття. Без оплати та без зобов'язань.</p>
    <div class="flex flex-wrap gap-3 justify-center">
      <a href="/#form" class="inline-flex items-center bg-white text-fox-600 hover:bg-fox-50 font-black text-base px-7 py-3.5 rounded-full shadow-lg hover:shadow-xl hover:-translate-y-0.5 transition-all duration-200" data-ru="Записаться на урок">Записатись на урок</a>
      <a href="tel:+380954624672" class="inline-flex items-center gap-2 border-2 border-white/70 text-white hover:bg-white/10 hover:border-white font-black text-base px-7 py-3.5 rounded-full transition-all duration-200 hover:-translate-y-0.5"><span aria-hidden="true">&#128222;</span><span data-ru="Позвонить">Зателефонувати</span></a>
    </div>
    <ul class="flex flex-wrap justify-center gap-x-7 gap-y-2 mt-8 text-sm font-semibold text-white/90">
      <li class="inline-flex items-center gap-2"><span class="text-white font-black" aria-hidden="true">&#10003;</span><span data-ru="Без оплаты и карты">Без оплати й картки</span></li>
      <li class="inline-flex items-center gap-2"><span class="text-white font-black" aria-hidden="true">&#10003;</span><span data-ru="Полный урок 1,5 часа">Повний урок 1,5 години</span></li>
      <li class="inline-flex items-center gap-2"><span class="text-white font-black" aria-hidden="true">&#10003;</span><span data-ru="Уровень определяет преподаватель">Рівень визначає вчитель</span></li>
    </ul>
  </div>
</section>
"""


# Блоки, перенесені з головної «один в один». Розмітки тут немає: її
# витягує home_blocks із зібраного index.html, тож копія не розійдеться
# з оригіналом.
#
# Форма заявки тепер стоїть і на посадкових — рішення власника від
# 24.09.2026; доти правило було «форма лише на index.html, посадкові
# ведуть на /#form». Що з цього випливає: копій форми на сайті стало
# шістнадцять, усі йдуть в один api/lead.php, а сторінку, з якої прийшла
# заявка, видно з поля `page` — його додає js/lead.js.
CONTACTS = home_blocks.CONTACTS
ARTICLES = home_blocks.ARTICLES
MODAL = home_blocks.MODAL


def render_page(p):
    url = "%s/%s" % (BASE, p["slug"])
    head = HEAD.format(
        title_uk=esc(p["title_uk"]), title_ru=p["title_ru"].replace("'", "\\'"),
        desc_uk=esc(p["desc_uk"]), desc_ru=p["desc_ru"].replace("'", "\\'"),
        og_title_uk=esc(p.get("og_uk", p["title_uk"])),
        og_title_ru=p.get("og_ru", p["title_ru"]).replace("'", "\\'"),
        url=url, base=BASE, slug=p["slug"], graph=build_graph(p), assetv=ASSET_VERSION)

    # Крихти йдуть по ширині геро: на сторінці з ілюстрацією геро широкий, і
    # крихти у вузькій колонці висіли б із власним лівим краєм.
    crumb_w = "max-w-6xl" if p.get("hero_art") else "max-w-3xl"
    crumbs = (('\n<nav class="%s mx-auto px-4 sm:px-6 lg:px-8 pt-6" aria-label="Хлібні крихти" data-ru-aria="Хлебные крошки">\n' % crumb_w)
              + ('  <ol class="flex flex-wrap items-center gap-2 text-sm text-gray-400">\n'
              '    <li><a href="/" class="hover:text-fox-500 transition-colors duration-200" data-ru="Главная">Головна</a></li>\n'
              '    <li aria-hidden="true">/</li>\n'
              '    <li class="text-gray-600 font-semibold"%s</li>\n'
              '  </ol>\n</nav>\n' % attr_ru(p["crumb_uk"], p["crumb_ru"])))

    # Друга кнопка героя за замовчуванням веде на ціни — але на самій сторінці
    # цін це посилання саме на себе, тому там вона змінюється на пробний урок.
    cta2 = p.get("cta2") or (("/probnyi-urok", "Пробний урок", "Пробный урок")
                             if p["slug"] == "tsiny"
                             else ("/tsiny", "Дивитись ціни", "Смотреть цены"))

    # Сторінка з ілюстрацією («hero_art») малює геро двома колонками й на всю
    # ширину контейнера; решта лишається як була — вузька колонка під текст.
    # Тіло статті в обох випадках max-w-3xl: широкий геро й вузька колонка
    # тексту — звичайна редакційна розкладка, а не недогляд.
    art = p.get("hero_art")
    hero_text = (
        '    <span class="inline-block bg-fox-50 text-fox-600 font-bold text-sm px-4 py-1.5 rounded-full mb-4"%s</span>\n'
        '    <h1 class="text-2xl sm:text-4xl md:text-5xl font-black text-gray-900 leading-tight mb-5"%s</h1>\n'
        '    <p class="text-base md:text-lg text-gray-600 leading-relaxed max-w-2xl mb-8"%s</p>\n'
        '    <div class="flex flex-wrap gap-3">\n'
        '      <a href="/#form" class="inline-flex items-center bg-fox-500 hover:bg-fox-600 text-white font-black text-base px-7 py-3.5 rounded-full shadow-fox hover:shadow-fox-lg hover:-translate-y-1 transition-all duration-200" data-ru="Бесплатный урок">Безкоштовний урок</a>\n'
        '      <a href="%s" class="inline-flex items-center bg-white hover:bg-gray-50 text-gray-800 font-bold text-base px-7 py-3.5 rounded-full border border-gray-200 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-200"%s</a>\n'
        '    </div>\n'
        % (attr_ru(p["badge_uk"], p["badge_ru"]),
           attr_ru(p["h1_uk"], p["h1_ru"]),
           attr_ru(p["lead_uk"], p["lead_ru"]),
           cta2[0], attr_ru(cta2[1], cta2[2])))

    if art:
        hero = ('\n<section class="pt-6 pb-8 md:pb-14">\n'
                '  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">\n'
                '    <div class="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,440px)] lg:gap-12 lg:items-center">\n'
                '      <div>\n%s      </div>\n'
                '      <div class="relative">\n%s      </div>\n'
                '    </div>\n  </div>\n</section>\n'
                % (hero_text.replace("\n    ", "\n        "), art))
    else:
        hero = ('\n<section class="pt-8 pb-8 md:pb-14">\n'
                '  <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">\n'
                '%s'
                '  </div>\n</section>\n' % hero_text)

    body = "\n".join(render_block(b) for b in p["blocks"])
    main = ('\n<main>\n' + render_agegroups(p) + '<section class="pb-8 md:pb-20">\n'
            '  <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">\n'
            '%s\n'
            '  </div>\n</section>\n' % body)

    # FOOTER не проходить через %-форматування, тому версію для /js/lang.js
    # підставляємо тут. Без неї скрипт кешується на рік як immutable, і
    # правка в ньому не доходить до тих, хто вже був на сайті.
    # Контакти стоять після банера: людина вже прочитала сторінку й вирішує —
    # дзвонити чи писати. Якір #contacts, на нього веде пункт у шапці.
    return (head + HEADER.replace("%(path)s", "/" + p["slug"])
            + crumbs + hero + main + render_faq(p) + CTA + CONTACTS + ARTICLES
            + render_related(p) + render_seo(p) + "</main>\n"
            + FOOTER.replace("%(assetv)s", ASSET_VERSION)
                    .replace("</body>", MODAL + "</body>"))


def main():
    built = []
    paths = []
    for p in C.PAGES:
        html = squeeze(render_page(p))
        path = os.path.join(ROOT, p["slug"] + ".html")
        io.open(path, "w", encoding="utf-8", newline="\n").write(html)
        paths.append(path)
        built.append((p["slug"], len(html), len(p["blocks"]), len(p.get("faq", []))))

    print("зібрано %d сторінок:" % len(built))
    for slug, size, blocks, faq in built:
        print("  /%-24s %6d Б  блоків: %-2d  FAQ: %d" % (slug, size, blocks, faq))

    # Російські версії — окремими файлами, одразу тут. Окремою командою вони
    # рано чи пізно лишилися б від попередньої правки: складання мовчить, а на
    # сайті половина сторінок перекладена, половина ні.
    RU.build(paths, quiet=True)
    for p in C.PAGES:
        path = RU.ru_path(os.path.join(ROOT, p["slug"] + ".html"))
        html = io.open(path, encoding="utf-8").read()
        io.open(path, "w", encoding="utf-8", newline="\n").write(ru_html(html, p))
    print("російські версії: %d файлів" % len(paths))


def ru_html(html, p):
    """Крок, якого пост-процесор зробити не може: власний граф ld+json.

    Винесено окремо, бо цим самим кодом користується аудит — він звіряє
    російські сторінки, перескладаючи їх у пам'яті, і має повторити весь
    конвеєр, а не половину."""
    return GRAPH.replace(html, build_graph(p, "ru"))

    # Дати в карті сайту — теж тут, з тієї ж причини: окремою командою вони
    # лишилися б від позаминулого складання. Переставляються лише там, де
    # змінився вміст, тож зайвий запуск нічого не зрушить.
    LASTMOD.refresh()


if __name__ == "__main__":
    main()
