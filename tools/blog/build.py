# -*- coding: utf-8 -*-
"""Складає статті блогу з даних у articles.py.

Перші десять статей писалися руками, і це видно: п'ять старих мали плоский
Article замість графа, автором стояла «Команда FluentFox», а верстка в них
розійшлася з новішими. Коли статей має стати сорок, руками їх не втримати
однаковими.

Тексти пишуться за двома методичками з `Desktop/Инструкции для клода`:
humanize-guide (як не звучати як ІІ і не потрапити під санкції Google) і
GEO-гайд (як писати так, щоб ІІ-пошуковики цитували). Головні вимоги, які
шаблон підтримує технічно:

  * заголовок розділу — справжнє питання, яким його ставлять асистенту;
  * пряма відповідь у першому-третьому реченні під заголовком;
  * блок питання-відповідь усередині тексту, не лише в кінці (тип `qa`);
  * врізка від першої особи з іменем викладача (тип `expert`);
  * час читання рахується з реального обсягу, а не пишеться на око.

Запуск:  python tools/blog/build.py
"""
from __future__ import unicode_literals

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from assets import ASSET_VERSION  # noqa: E402  — спільна версія ?v= для всього сайту
import articles as A  # noqa: E402
import queue as Q  # noqa: E402
import site_index as IDX  # noqa: E402

BASE = "https://fluent-fox.site"
ORG = BASE + "/#organization"

MONTHS_UK = ["січня", "лютого", "березня", "квітня", "травня", "червня",
             "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]
MONTHS_RU = ["января", "февраля", "марта", "апреля", "мая", "июня",
             "июля", "августа", "сентября", "октября", "ноября", "декабря"]

# Ті самі люди, що й у розмітці головної сторінки. Спільний @id зшиває
# «автора статті» і «вчителя школи» в одну сутність — без цього Google бачить
# однойменних незнайомців.
PEOPLE = {
    "Катерина Волошина": {
        "slug": "voloshyna",
        "job_uk": "Вчителька англійської, CELTA",
        "job_ru": "Учитель английского, CELTA",
        "name_ru": "Екатерина Волошина",
        "byline_uk": "вчителька англійської (CELTA)",
        "byline_ru": "учитель английского (CELTA)",
    },
    "Олена Марченко": {
        "slug": "marchenko",
        "job_uk": "Вчителька англійської, TEFL",
        "job_ru": "Учитель английского, TEFL",
        "name_ru": "Елена Марченко",
        "byline_uk": "вчителька англійської (TEFL)",
        "byline_ru": "учитель английского (TEFL)",
    },
    "Артем Дороженко": {
        "slug": "dorozhenko",
        "job_uk": "Вчитель англійської, MA Linguistics",
        "job_ru": "Учитель английского, MA Linguistics",
        "name_ru": "Артём Дороженко",
        "byline_uk": "вчитель англійської (MA Linguistics)",
        "byline_ru": "учитель английского (MA Linguistics)",
    },
}


# ── шапка, підвал і підписи ──────────────────────────────────────────────────
#
# Раніше кожне посилання жило в шаблоні двічі — `:href` для адреси і `x-text`
# для підпису — а мову підставляв Alpine уже в браузері. Тепер стаття
# складається окремим файлом на кожну мову, тож підпис і адреса відомі під час
# складання, і тримати їх треба в одному місці.

NAV = [
    ("/pro-shkolu", "Про нас", "О нас"),
    ("/tsiny", "Ціни", "Цены"),
]

FOOTER_LINKS = [
    ("/", "Головна", "Главная"),
    ("/kursy-anhliyskoyi-dlya-ditey", "Курси англійської", "Курсы английского"),
    ("/anhliyska-onlayn-dlya-ditey", "Англійська онлайн", "Английский онлайн"),
    ("/repetytor-z-anhliyskoyi", "Репетитор з англійської", "Репетитор по английскому"),
    ("/rozmovna-anhliyska-dlya-ditey", "Розмовна англійська", "Разговорный английский"),
    ("/tsiny", "Ціни", "Цены"),
    ("/pro-shkolu", "Про школу", "О школе"),
    ("/blog/", "Блог", "Блог"),
    ("/probnyi-urok", "Пробний урок", "Пробный урок"),
]

LABELS = {
    "uk": {
        "home": "Головна", "blog": "Блог", "trial": "Пробний урок",
        "crumbs": "Хлібні крихти", "doshkolyaryk": "Центр «Дошколярик»",
        "og_image_alt": "FluentFox — онлайн-школа англійської для дітей",
        "og_locale": "uk_UA", "og_locale_alt": "ru_RU",
    },
    "ru": {
        "home": "Главная", "blog": "Блог", "trial": "Пробный урок",
        "crumbs": "Хлебные крошки", "doshkolyaryk": "Центр «Дошколярик»",
        "og_image_alt": "FluentFox — онлайн-школа английского для детей",
        # ru_RU, а не ru_UA: месенджери розбирають лише перелік підтримуваних
        # локалей, і ru_UA у ньому немає — тег просто ігнорується.
        "og_locale": "ru_RU", "og_locale_alt": "uk_UA",
    },
}


def href(path, lang):
    """Внутрішня адреса потрібною мовою."""
    if lang != "ru":
        return path
    return path + ("&" if "?" in path else "?") + "lang=ru"


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def rich(s):
    """Дозволяємо лише <strong> і <em> — решту екрануємо."""
    s = esc(s)
    s = s.replace("[b]", "<strong>").replace("[/b]", "</strong>")
    s = s.replace("[i]", "<em>").replace("[/i]", "</em>")
    return s


def strip_tags(s):
    return re.sub(r"\[/?[bi]\]", "", s)


def fmt_date(iso, lang):
    y, m, d = (int(x) for x in iso.split("-"))
    months = MONTHS_UK if lang == "uk" else MONTHS_RU
    return "%d %s %d" % (d, months[m - 1], y)


# ── блоки ────────────────────────────────────────────────────────────────────

def render_blocks(blocks, lang):
    i = 0 if lang == "uk" else 1
    out = []
    for b in blocks:
        kind = b[0]

        if kind == "p":
            out.append("        <p>%s</p>" % rich(b[1 + i]))

        elif kind == "h2":
            out.append("        <h2>%s</h2>" % esc(b[1 + i]))

        elif kind == "h3":
            out.append("        <h3>%s</h3>" % esc(b[1 + i]))

        elif kind == "ul":
            items = "\n".join("          <li>%s</li>" % rich(x[i])
                              for x in b[1])
            out.append("        <ul>\n%s\n        </ul>" % items)

        elif kind == "ol":
            items = "\n".join("          <li>%s</li>" % rich(x[i])
                              for x in b[1])
            out.append("        <ol>\n%s\n        </ol>" % items)

        elif kind == "callout":
            out.append('        <div class="callout"><p>%s</p></div>'
                       % rich(b[1 + i]))

        elif kind == "qa":
            # Питання-відповідь усередині тексту. GEO-гайд вимагає саме такий
            # блок: питання як заголовок, відповідь одразу під ним, без розгону.
            out.append('        <h3 class="qa-q">%s</h3>\n        <p>%s</p>'
                       % (esc(b[1 + i]), rich(b[3 + i])))

        elif kind == "expert":
            person = PEOPLE[b[1]]
            name = b[1] if lang == "uk" else person["name_ru"]
            job = person["job_uk"] if lang == "uk" else person["job_ru"]
            out.append(
                '        <figure class="expert">\n'
                '          <blockquote>%s</blockquote>\n'
                '          <figcaption>%s — %s</figcaption>\n'
                '        </figure>' % (rich(b[2 + i]), esc(name), esc(job)))

        elif kind == "courselink":
            # Контекстне посилання на профільну посадкову. Посилання з меню,
            # однакове на всіх сторінках, Google майже не враховує — вагу несе
            # саме таке, з тіла тексту, оточене релевантними словами.
            _, page, t_uk, t_ru, cta_uk, cta_ru = b
            href = page if lang == "uk" else page + "?lang=ru"
            out.append(
                '        <div class="course-link">\n'
                '          <p class="cl-label">%s</p>\n'
                '          <p class="cl-title">%s</p>\n'
                '          <a href="%s">%s &rarr;</a>\n'
                '        </div>'
                % ("За цією темою" if lang == "uk" else "По этой теме",
                   esc(t_uk if lang == "uk" else t_ru),
                   href,
                   esc(cta_uk if lang == "uk" else cta_ru)))

        elif kind == "table":
            head, rows = b[1], b[2]
            th = "".join("<th scope=\"col\">%s</th>" % esc(c[i]) for c in head)
            tr = "\n".join(
                "            <tr>%s</tr>"
                % "".join("<td>%s</td>" % rich(c[i]) for c in row)
                for row in rows)
            out.append(
                '        <div class="table-wrap">\n'
                '          <table>\n'
                '            <thead><tr>%s</tr></thead>\n'
                '            <tbody>\n%s\n            </tbody>\n'
                '          </table>\n        </div>' % (th, tr))

        elif kind == "html":
            # Готова розмітка статті, що приїхала конвеєром мережі. Теги вже
            # перевірені за білим списком у queue.py, тож тут вона просто
            # лягає в .prose як є — це єдиний блок, який не збирається з
            # частин, і єдиний, який пише не людина.
            out.append(b[1 + i])

        else:
            raise ValueError("невідомий блок: " + kind)

    return "\n".join(out)


def word_count(blocks, faq, lang):
    i = 0 if lang == "uk" else 1
    words = 0
    for b in blocks:
        kind = b[0]
        if kind in ("p", "h2", "h3", "callout"):
            words += len(strip_tags(b[1 + i]).split())
        elif kind in ("ul", "ol"):
            for x in b[1]:
                words += len(strip_tags(x[i]).split())
        elif kind == "qa":
            words += len(strip_tags(b[1 + i]).split())
            words += len(strip_tags(b[3 + i]).split())
        elif kind == "expert":
            words += len(strip_tags(b[2 + i]).split())
        elif kind == "courselink":
            words += len(strip_tags(b[2 + i]).split())
        elif kind == "table":
            for row in b[2]:
                for c in row:
                    words += len(strip_tags(c[i]).split())
        elif kind == "html":
            words += len(re.sub(r"<[^>]+>", " ", b[1 + i]).split())
    for q in faq:
        words += len(q[0 + i * 2].split()) + len(q[1 + i * 2].split())
    return words


def _minutes(words):
    return max(1, int(round(words / 190.0)))


def plural(n, forms):
    """forms = (одна, дві, п'ять) — українська й російська відмінюються однаково."""
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def read_time(words, lang):
    mins = _minutes(words)
    if lang == "uk":
        return "%d %s читання" % (mins, plural(mins, ("хвилина", "хвилини", "хвилин")))
    return "%d %s чтения" % (mins, plural(mins, ("минута", "минуты", "минут")))


# ── розмітка ─────────────────────────────────────────────────────────────────

def build_graph(a, lang):
    """Граф однієї мовної версії.

    Мова тут не косметика: доти обидві версії статті жили в одному файлі й
    ділили один граф, у якому стояло `inLanguage: uk` і український заголовок —
    тобто російська сторінка описувала себе українською. Тепер версії — різні
    файли за різними адресами, і `@id` теж мусять різнитися, інакше дві
    сторінки оголошують себе однією сутністю."""
    i = 0 if lang == "uk" else 1
    url = href("%s/blog/%s" % (BASE, a["slug"]), lang)
    L = LABELS[lang]
    person = PEOPLE[a["author"]]
    title = a["title_uk"] if lang == "uk" else a["title_ru"]
    desc = a["desc_uk"] if lang == "uk" else a["desc_ru"]
    graph = [
        {
            "@type": "WebPage",
            "@id": url + "#webpage",
            "url": url,
            "name": title,
            "description": desc,
            "inLanguage": lang,
            "isPartOf": {"@id": BASE + "/#website"},
            "breadcrumb": {"@id": url + "#breadcrumb"},
            "primaryImageOfPage": {"@type": "ImageObject", "url": BASE + "/og-image.jpg"},
        },
        {
            "@type": "BreadcrumbList",
            "@id": url + "#breadcrumb",
            "itemListElement": [
                {"@type": "ListItem", "position": 1,
                 "item": {"@id": href(BASE + "/", lang), "name": L["home"]}},
                {"@type": "ListItem", "position": 2,
                 "item": {"@id": href(BASE + "/blog/", lang), "name": L["blog"]}},
                {"@type": "ListItem", "position": 3,
                 "item": {"@id": url, "name": title}},
            ],
        },
        {
            "@type": "Article",
            "@id": url + "#article",
            "headline": title,
            "description": desc,
            "url": url,
            "inLanguage": lang,
            "datePublished": a["published"],
            "dateModified": a.get("modified", a["published"]),
            "articleSection": a["category_uk"] if lang == "uk" else a["category_ru"],
            "wordCount": a["_words_" + lang],
            "author": {
                "@type": "Person",
                # @id один на обидві мови навмисно: це та сама людина, що й
                # серед вчителів на головній.
                "@id": BASE + "/#teacher-" + person["slug"],
                "name": a["author"] if lang == "uk" else person["name_ru"],
                "jobTitle": person["job_uk"] if lang == "uk" else person["job_ru"],
                "worksFor": {"@id": ORG},
            },
            "publisher": {"@id": ORG},
            "isPartOf": {"@id": url + "#webpage"},
            "mainEntityOfPage": {"@id": url + "#webpage"},
            "image": {"@type": "ImageObject", "url": BASE + "/og-image.jpg",
                      "width": 1200, "height": 630},
        },
    ]

    # HowTo написаний тільки українською — у даних статті російського варіанта
    # немає. На російській сторінці він і не з'являється: краще без блоку, ніж
    # блок українською під `inLanguage: ru`.
    if a.get("howto") and lang == "uk":
        h = a["howto"]
        graph.append({
            "@type": "HowTo",
            "@id": url + "#howto",
            "name": h["name"],
            "description": h["description"],
            "inLanguage": lang,
            "step": [
                {"@type": "HowToStep", "position": n + 1, "name": s[0], "text": s[1]}
                for n, s in enumerate(h["steps"])
            ],
        })

    if a.get("faq"):
        graph.append({
            "@type": "FAQPage",
            "@id": url + "#faq",
            "isPartOf": {"@id": url + "#webpage"},
            "mainEntity": [
                {"@type": "Question", "name": q[0 + i * 2],
                 "acceptedAnswer": {"@type": "Answer", "text": q[1 + i * 2]}}
                for q in a["faq"]
            ],
        })

    return json.dumps({"@context": "https://schema.org", "@graph": graph},
                      ensure_ascii=False, separators=(",", ":"))


TPL = io.open(os.path.join(HERE, "template.html"), encoding="utf-8").read()


def render_faq(a, lang):
    if not a.get("faq"):
        return ""
    i = 0 if lang == "uk" else 1
    title = "Часті питання" if lang == "uk" else "Частые вопросы"
    items = "\n".join(
        '        <h3 class="qa-q">%s</h3>\n        <p>%s</p>'
        % (esc(q[0 + i * 2]), rich(q[1 + i * 2])) for q in a["faq"])
    return "        <h2>%s</h2>\n%s" % (title, items)


def render_related(a, lang):
    i = 0 if lang == "uk" else 1
    suffix = "" if lang == "uk" else "?lang=ru"
    title = "Читайте також" if lang == "uk" else "Читайте также"
    cards = "\n".join(
        '          <a href="/blog/%s%s" class="bg-white rounded-2xl p-5 border border-gray-100 hover:border-fox-200 transition-colors">\n'
        '            <span class="text-2xl">%s</span>\n'
        '            <p class="font-black text-gray-900 text-sm mt-2 leading-tight">%s</p>\n'
        '          </a>' % (slug, suffix, emoji, esc(t[i]))
        for slug, emoji, t in [(r[0], r[1], (r[2], r[3])) for r in a["related"]])
    return ('      <div class="mt-12">\n'
            '        <h3 class="text-lg font-black text-gray-900 mb-4">%s</h3>\n'
            '        <div class="grid sm:grid-cols-2 gap-4">\n%s\n        </div>\n'
            '      </div>' % (title, cards))


def render_side(a, lang):
    """Одна мовна версія статті цілком."""
    i = 0 if lang == "uk" else 1
    person = PEOPLE[a["author"]]
    author_name = a["author"] if lang == "uk" else person["name_ru"]
    byline = person["byline_uk"] if lang == "uk" else person["byline_ru"]
    updated = ""
    if a.get("modified") and a["modified"] != a["published"]:
        label = "оновлено" if lang == "uk" else "обновлено"
        updated = ('<span>·</span><span>%s %s</span>'
                   % (label, fmt_date(a["modified"], lang)))

    body = render_blocks(a["blocks"], lang)
    faq = render_faq(a, lang)
    if faq:
        body = body + "\n" + faq

    cta = a["cta"]
    return """      <div class="mb-6">
        <span class="inline-block bg-fox-50 text-fox-600 font-bold text-xs px-3 py-1 rounded-full mb-4">%(cat)s</span>
        <h1 class="text-xl sm:text-2xl md:text-4xl font-black text-gray-900 leading-tight mb-4">%(title)s</h1>
        <div class="flex flex-wrap items-center gap-2 text-sm text-gray-400">
          <span>&#128197; %(date)s</span><span>·</span><span>&#9201; %(read)s</span><span>·</span><span>&#9997;&#65039; %(author)s, %(byline)s</span>%(updated)s
        </div>
      </div>

      <div class="prose">
%(body)s
      </div>

      <div class="bg-gradient-to-br from-fox-500 to-fox-600 rounded-3xl p-8 text-white mt-10 text-center">
        <div class="text-3xl mb-3">&#129418;</div>
        <h2 class="text-xl md:text-2xl font-black mb-2 leading-tight">%(cta_h)s</h2>
        <p class="text-white/80 mb-6 text-sm leading-relaxed">%(cta_p)s</p>
        <a href="%(form_href)s" class="inline-block bg-white text-fox-600 font-black px-6 py-3 rounded-full hover:bg-fox-50 transition-all duration-200 hover:-translate-y-0.5 shadow-lg">%(cta_b)s</a>
      </div>

%(related)s""" % {
        "cat": esc(a["category_uk"] if lang == "uk" else a["category_ru"]),
        "title": esc(a["title_uk"] if lang == "uk" else a["title_ru"]),
        "date": fmt_date(a["published"], lang),
        "read": a["_read_" + lang],
        "author": esc(author_name),
        "byline": esc(byline),
        "updated": updated,
        "body": body,
        "cta_h": esc(cta[0 + i * 3]),
        "cta_p": esc(cta[1 + i * 3]),
        "cta_b": esc(cta[2 + i * 3]),
        "form_href": "/#form" if lang == "uk" else "/?lang=ru#form",
        "related": render_related(a, lang),
    }


ACTIVE = "bg-white shadow text-fox-600"
IDLE = "text-gray-400 hover:text-gray-600"


def render_nav(lang):
    """Посилання шапки. «Блог» — поточний розділ, тому без адреси."""
    out = [
        '        <a href="%s" class="text-sm font-semibold text-gray-600 '
        'hover:text-fox-500 transition-colors">%s</a>'
        % (href(path, lang), esc(uk if lang == "uk" else ru))
        for path, uk, ru in NAV
    ]
    out.append('        <a href="%s" class="text-sm font-semibold text-fox-500">%s</a>'
               % (href("/blog/", lang), esc(LABELS[lang]["blog"])))
    return "\n".join(out)


def render_footer(lang):
    return "\n".join(
        '        <a href="%s" class="%s">%s</a>'
        % (href(path, lang),
           "text-fox-400" if path == "/blog/"
           else "hover:text-fox-400 transition-colors",
           esc(uk if lang == "uk" else ru))
        for path, uk, ru in FOOTER_LINKS)


def render(a, lang):
    """Одна мовна версія статті — окремим файлом.

    Доти обидві мови лежали в одному файлі під `x-show`, і російську показував
    Alpine уже в браузері. Тобто читач без JS бачив дві мови поспіль, а файл
    важив удвічі більше, ніж потрібно кожному з них."""
    url = "%s/blog/%s" % (BASE, a["slug"])
    L = LABELS[lang]
    uk = lang == "uk"
    return TPL % {
        "assetv": ASSET_VERSION,
        "lang": lang,
        "title": esc(a["meta_title_uk"] if uk else a["meta_title_ru"]),
        "desc": esc(a["desc_uk"] if uk else a["desc_ru"]),
        "og_title": esc(a["title_uk"] if uk else a["title_ru"]),
        "og_desc": esc(a["og_desc_uk"] if uk else a["desc_ru"]),
        "og_image_alt": esc(L["og_image_alt"]),
        "og_locale": L["og_locale"],
        "og_locale_alt": L["og_locale_alt"],
        "url_self": href(url, lang),
        "url_uk": url,
        "url_ru": href(url, "ru"),
        "sw_uk": ACTIVE if uk else IDLE,
        "sw_ru": IDLE if uk else ACTIVE,
        "base": BASE,
        "home": href("/", lang),
        "blog": href("/blog/", lang),
        "form": href("/", lang) + "#form",
        "nav": render_nav(lang),
        "footer": render_footer(lang),
        "published": a["published"],
        "modified": a.get("modified", a["published"]),
        "section": esc(a["category_uk"] if uk else a["category_ru"]),
        "author": esc(a["author"] if uk else PEOPLE[a["author"]]["name_ru"]),
        "graph": build_graph(a, lang),
        "crumb": esc(a["category_uk"] if uk else a["category_ru"]),
        "l_home": esc(L["home"]),
        "l_blog": esc(L["blog"]),
        "l_trial": esc(L["trial"]),
        "l_crumbs": esc(L["crumbs"]),
        "l_doshkolyaryk": esc(L["doshkolyaryk"]),
        "body": render_side(a, lang),
    }


def card(a, prev):
    """Картка статті для лістингу.

    Що вважається порахованим, а що — написаним, тут розділено навмисно. Дата,
    час читання і заголовок беруться зі статті: вони або обчислюються, або
    мають збігатися з нею дослівно. А от анонс на картці, емодзі й вкладка —
    це окремий текст, коротший за meta description і написаний під сітку
    карток; у статей, що писалися руками, він живе в listing.json, і
    складання не має права затирати його описом зі сторінки.

    Те саме стосується llmsTitle і llmsDesc — коротких рядків для llms.txt.
    Поки перші десять статей не збиралися звідси, їхні записи ніхто не
    перезаписував, і пропуск цих двох полів тут нічого не ламав. Щойно таку
    статтю переносять у генератор, картка перезбирається — і без цих рядків
    llms.txt мовчки підмінив би написані від руки описи анонсом із лістингу.
    """
    from_queue = a.get("_from_queue")
    entry = {
        "slug": a["slug"],
        "emoji": a.get("emoji") or prev.get("emoji") or "🦊",
        "accent": a.get("accent") or prev.get("accent") or "fox",
        "catKey": a.get("catKey") or prev.get("catKey") or "methods",
        "date": fmt_date(a["published"], "uk"),
        "dateRu": fmt_date(a["published"], "ru"),
        "readTime": "%d хв читання" % _minutes(a["_words_uk"]),
        "readTimeRu": "%d мин чтения" % _minutes(a["_words_ru"]),
        "category": a["category_uk"],
        "categoryRu": a["category_ru"],
        "title": a["title_uk"],
        "titleRu": a["title_ru"],
        "excerpt": a["desc_uk"] if from_queue else (prev.get("excerpt") or a["desc_uk"]),
        "excerptRu": a["desc_ru"] if from_queue else (prev.get("excerptRu") or a["desc_ru"]),
        "published": a["published"],
        "modified": a.get("modified") or prev.get("modified") or a["published"],
    }
    for k in ("llmsTitle", "llmsDesc"):
        if prev.get(k):
            entry[k] = prev[k]
    return entry


RELATED_SAME_CAT = 3
RELATED_TOTAL = 4


def link_related(arts, entries):
    """«Читайте також» рахується з кільця, а не пишеться руками.

    Раніше цей перелік лежав у самій статті й після написання не мінявся
    ніколи. Тому кожна нова стаття приходила в блог сиротою: сама вела на
    чотирьох сусідів, а на неї не вів ніхто — крім лістингу. Серпнева масова
    перелінковка виправила це руками, і все, що вийшло після неї, знову
    лишилося з однією вхідною посилкою.

    Тепер сусіди беруться з кільця категорії: стаття веде на три наступні
    статті своєї рубрики за порядком лістингу. Кільце симетричне — у категорії
    з k статей кожна не лише веде на min(3, k-1) сусідів, а й сама стільки ж
    разів згадана, тож нова стаття вбудовується в сітку сама.

    Четверта картка (а в малій рубриці — друга, третя й четверта) добирається
    не за порядком, а за потребою: береться стаття, на яку поки що веде
    найменше посилань. Без цього кроку кільце лишало б сиріт у рубриках із
    двох статей — і найгірше саме там, де другу статтю рубрики складання ще не
    перескладає, тож відповісти посиланням вона не може.

    Рахується після того, як картки всіх статей уже лежать у `entries`:
    інакше стаття з черги не потрапила б у власне кільце.
    """
    pos = dict((e["slug"], i) for i, e in enumerate(entries))
    by_cat = {}
    for e in entries:
        by_cat.setdefault(e["catKey"], []).append(e)

    picks = {}
    got = dict((e["slug"], 0) for e in entries)

    for a in arts:
        me = a["slug"]
        ring = by_cat[entries[pos[me]]["catKey"]]
        picked = []
        i = [e["slug"] for e in ring].index(me)
        for j in range(1, len(ring)):
            if len(picked) >= RELATED_SAME_CAT:
                break
            e = ring[(i + j) % len(ring)]
            picked.append(e)
            got[e["slug"]] += 1
        picks[me] = picked

    total = len(entries)
    for a in arts:
        me = a["slug"]
        picked = picks[me]
        seen = set([me]) | set(e["slug"] for e in picked)
        while len(picked) < RELATED_TOTAL and len(seen) < total:
            e = min((e for e in entries if e["slug"] not in seen),
                    key=lambda e: (got[e["slug"]],
                                   (pos[e["slug"]] - pos[me]) % total))
            picked.append(e)
            seen.add(e["slug"])
            got[e["slug"]] += 1
        a["related"] = [(e["slug"], e["emoji"], e["title"], e["titleRu"])
                        for e in picked]


def incoming(arts, entries):
    """Скільки статей веде на кожну — щоб сирота не пройшла непоміченою.

    Рахуються лише посилання зі статей, які складання перескладає. Ті кілька
    статей, що ще лежать готовим HTML і в генератор не перенесені, посилаються
    зі свого боку самі, і тут їх не видно — число нижче реального, не вище.
    """
    n = dict((e["slug"], 0) for e in entries)
    for a in arts:
        for r in a["related"]:
            if r[0] in n:
                n[r[0]] += 1
    return n


def main():
    entries = IDX.load_entries()
    by_slug = {e["slug"]: e for e in entries}

    queued = [Q.to_art(x, sorted(PEOPLE)) for x in Q.load()]
    for a in queued:
        # Стаття з конвєєра часто приїжджає без дати, і тоді її ставлять за
        # днем складання. Але складання відбувається щоразу, коли в блозі з'являється
        # будь-що нове — і без цього рядка вже опублікована стаття щоразу молодшала б
        # на кілька днів — разом із datePublished у розмітці й lastmod у карті сайту.
        prev = by_slug.get(a["slug"])
        if a.pop("_dated_by_default", False) and prev:
            a["published"] = prev["published"]

    built = list(A.ARTICLES) + queued
    for a in built:
        for lang in ("uk", "ru"):
            w = word_count(a["blocks"], a.get("faq", []), lang)
            a["_words_" + lang] = w
            a["_read_" + lang] = read_time(w, lang)
        entries = IDX.upsert(entries, card(a, by_slug.get(a["slug"], {})))

    # Складання йде у два проходи навмисно: перелінковка мусить бачити картки
    # всіх статей, включно з тією, що приїхала з черги хвилину тому. Порахувати
    # її до upsert означало б знову випустити нову статтю з кільця.
    link_related(built, entries)

    for a in built:
        for lang in ("uk", "ru"):
            name = a["slug"] + (".html" if lang == "uk" else ".ru.html")
            path = os.path.join(ROOT, "blog", name)
            io.open(path, "w", encoding="utf-8", newline="\n").write(render(a, lang))

    # Сторінка, на яку ніхто не посилається, для пошуку не існує: лістинг,
    # noscript-перелік, розмітка блогу і карта сайту оновлюються тут же, одним
    # проходом, щоб між «стаття складена» і «на неї можна прийти» не лишалося
    # ручного кроку.
    IDX.save_entries(entries)
    IDX.apply(entries)

    links = incoming(built, entries)
    print("зібрано статей: %d (з черги: %d)\n" % (len(built), len(queued)))
    print("  %-46s %-18s %6s %6s %5s"
          % ("слаг", "автор", "слів uk", "слів ru", "вхід"))
    for a in built:
        flag = "" if a["_words_uk"] >= 1000 and a["_words_ru"] >= 1000 else "  <-- МЕНШЕ 1000"
        # Вхідні посилання рахуються тут же: стаття, на яку веде менше трьох
        # сусідів, для пошуку майже не існує, і мовчати про це складання не має.
        if links[a["slug"]] < RELATED_SAME_CAT:
            flag += "  <-- МАЛО ВХІДНИХ"
        print("  %-46s %-18s %6d %6d %5d%s"
              % (a["slug"], a["author"], a["_words_uk"], a["_words_ru"],
                 links[a["slug"]], flag))


if __name__ == "__main__":
    main()
