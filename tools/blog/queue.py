# -*- coding: utf-8 -*-
"""Статті, які пише конвеєр мережі, у вигляді, зрозумілому build.py.

Мережа my_computer_new має власний конвеєр статей: хмарний агент двічі на
тиждень пише статтю для обраного сайта й кладе її файлом JSON у
`content-queue/pending/`, а GitHub Actions публікує. FluentFox під'єднаний до
того ж конвеєра — але він не має ані бази, ані сервера, тож «опублікувати» для
нього означає скласти сторінку й закомітити. Файл статті приїжджає сюди, у
`tools/blog/content/`, і складається разом з рештою.

Формат файлу — той самий, що й у всієї мережі (slug, title, title_ru, excerpt,
excerpt_ru, content, content_ru, category, category_ru, coverEmoji, author), і
це навмисно: конвеєр, знімок і перевірка дублів читають один формат, а не два.
Багатий формат блоків (`expert`, `qa`, `courselink`, таблиці) лишається для
статей, які пишуться руками модулем art_*.py — агенту він не потрібен, і кожен
зайвий різновид розмітки — це ще один спосіб зламати нічний прогон.

Необов'язкові поля, які конвеєр може додати:
  published — дата публікації (без неї береться день складання);
  faq       — [[питання_uk, відповідь_uk, питання_ru, відповідь_ru], ...],
              з нього збирається і видимий блок, і розмітка FAQPage;
  catKey    — вкладка лістингу; без неї визначається за назвою категорії.
"""
from __future__ import unicode_literals

import datetime
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(HERE, "content")

# Теги, які дозволено у content. Усе, що поза списком, зупиняє складання: HTML
# приходить від агента, а сторінка йде в прод без людини посередині. Тут не
# «санітизація на всяк випадок», а перелік того, що вміє стилізувати .prose у
# template.html, — чужий тег виглядав би на сторінці як голий текст.
ALLOWED_TAGS = {
    "p", "h2", "h3", "ul", "ol", "li", "strong", "em", "b", "i", "br",
    "blockquote", "table", "thead", "tbody", "tr", "th", "td", "a",
}
TAG_RE = re.compile(r"<\s*/?\s*([a-zA-Z0-9]+)")

# Вкладки лістингу. Категорію пише агент словами, а перемикач на сторінці
# працює за ключем — без цього зіставлення стаття лишилася б лише у вкладці
# «Усі».
CAT_KEYS = {
    "методи навчання": "methods",
    "методы обучения": "methods",
    "вік і розвиток": "age",
    "возраст и развитие": "age",
    "нмт та іспити": "exams",
    "нмт и экзамены": "exams",
    "формат занять": "format",
    "формат занятий": "format",
    "мотивація": "motivation",
    "мотивация": "motivation",
    "вибір школи": "choice",
    "выбор школы": "choice",
}

DEFAULT_CTA = (
    "Безкоштовний пробний урок у FluentFox",
    "Викладач подивиться рівень дитини, розкаже, де прогалини, і запропонує "
    "програму. Без оплати і без зобов'язань.",
    "Записатись на пробний урок",
    "Бесплатный пробный урок в FluentFox",
    "Преподаватель посмотрит уровень ребёнка, расскажет, где пробелы, и предложит "
    "программу. Без оплаты и без обязательств.",
    "Записаться на пробный урок",
)

REQUIRED = ("slug", "title", "title_ru", "excerpt", "excerpt_ru",
            "content", "content_ru", "category", "category_ru")


def check_html(html, where):
    for tag in TAG_RE.findall(html):
        if tag.lower() not in ALLOWED_TAGS:
            raise ValueError("%s: заборонений тег <%s>" % (where, tag))


# Посилання на сусідню статтю всередині тексту. Конвеєр пише їх у старому
# вигляді — з .html на кінці, — і мережа не має причин знати, що у нас адреси
# змінилися: сайтів у неї шістнадцять, а формат один. Тому розширення
# знімається тут, на вході. Без цього кожна нова стаття приносила б із собою
# по два посилання, які ловлять 301 замість того, щоб вести прямо.
BLOG_LINK = re.compile(r'(href="(?:https://fluent-fox\.site)?/blog/[a-z0-9-]+)\.html(")')


def strip_html_ext(html):
    return BLOG_LINK.sub(r"\1\2", html)


def cat_key(article):
    if article.get("catKey"):
        return article["catKey"]
    for name in (article.get("category", ""), article.get("category_ru", "")):
        key = CAT_KEYS.get(name.strip().lower())
        if key:
            return key
    return "methods"


def to_art(article, authors):
    """JSON конвеєра → словник статті у форматі art_*.py."""
    missing = [k for k in REQUIRED if not article.get(k)]
    if missing:
        raise ValueError("%s: бракує полів %s"
                         % (article.get("slug", "?"), ", ".join(missing)))
    check_html(article["content"], article["slug"] + " (uk)")
    check_html(article["content_ru"], article["slug"] + " (ru)")

    # Автор — реальна вчителька зі складу школи: її ім'я стоїть у розмітці
    # Article і зшите спільним @id з карткою вчителя на головній. Агент може
    # назвати автора сам, але якщо не назвав або назвав чужого, вибір має бути
    # стабільним — інакше та сама стаття при перескладанні змінювала б автора.
    author = article.get("author")
    if author not in authors:
        author = authors[sum(ord(c) for c in article["slug"]) % len(authors)]

    title_uk = article["title"]
    title_ru = article["title_ru"]
    art = {
        "slug": article["slug"],
        "category_uk": article["category"],
        "category_ru": article["category_ru"],
        "author": author,
        "published": article.get("published")
                     or datetime.datetime.utcnow().strftime("%Y-%m-%d"),
        # Звідси build.py дізнається, що дата взята з годинника, а не з JSON. Без цього
        # будь-яке перескладання блогу пересувало б усі статті з черги на сьогодні.
        "_dated_by_default": not article.get("published"),
        "title_uk": title_uk,
        "title_ru": title_ru,
        "meta_title_uk": article.get("meta_title_uk") or _meta(title_uk),
        "meta_title_ru": article.get("meta_title_ru") or _meta(title_ru),
        "desc_uk": article["excerpt"],
        "desc_ru": article["excerpt_ru"],
        "og_desc_uk": article.get("og_desc_uk") or article["excerpt"],
        "og_desc_ru": article.get("og_desc_ru") or article["excerpt_ru"],
        "cta": tuple(article["cta"]) if article.get("cta") else DEFAULT_CTA,
        "blocks": [("html", strip_html_ext(article["content"]),
                    strip_html_ext(article["content_ru"]))],
        "emoji": article.get("coverEmoji") or "🦊",
        "catKey": cat_key(article),
        "accent": article.get("accent") or "fox",
        "_from_queue": True,
    }
    if article.get("modified"):
        art["modified"] = article["modified"]
    if article.get("faq"):
        art["faq"] = [tuple(q) for q in article["faq"]]
    return art


def _meta(title):
    """Заголовок для <title>: сайт у кінці, але не довше 60 символів."""
    tail = " — FluentFox"
    room = 60 - len(tail)
    return (title if len(title) <= room else title[:room - 1].rstrip() + "…") + tail


def load():
    """Усі статті з черги, у порядку дати публікації."""
    if not os.path.isdir(CONTENT_DIR):
        return []
    out = []
    for name in sorted(os.listdir(CONTENT_DIR)):
        if not name.endswith(".json"):
            continue
        raw = io.open(os.path.join(CONTENT_DIR, name), encoding="utf-8").read()
        out.append(json.loads(raw))
    return out
