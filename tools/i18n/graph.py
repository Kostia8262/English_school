# -*- coding: utf-8 -*-
"""Російська версія розмітки Schema.org.

Навіщо. Коли російські сторінки стали окремими файлами, розмітка ld+json у них
лишилася українською: `inLanguage: uk`, українські назви й ті самі `@id`, що в
українській версії. Тобто російська сторінка описувала себе як українську, а
дві різні адреси оголошували себе однією сутністю. Пост-процесор
`ru_pages.py` цього виправити не може й не повинен: перекласти назви йому
нізвідки, а вгадувати він не має права.

Тут інакше — переклад береться зі словника `graph_ru.json`, а не вигадується.
Дві третини словника — це рядки, які вже є на сайті російською (тексти
відгуків, питання FAQ, назви розділів); решту перекладено руками один раз.

**Рядок без перекладу валить складання.** Це головне правило модуля: мовчки
пропустити його означало б віддати російську сторінку з українською назвою в
розмітці — рівно та біда, заради якої все це й робиться. Нова сторінка з новим
текстом у графі не збереться, доки переклад не допишуть у словник.

Що ще робиться, крім тексту:

  * `inLanguage` скрізь стає `ru`;
  * адреси самої сторінки (`@id`, `url`) отримують `?lang=ru` — інакше
    українська й російська версії оголошують себе однією сутністю;
  * адреси спільних сутностей (`#organization`, `#website`, `#teacher-…`) не
    чіпаються: школа й вчитель — ті самі, якою б мовою про них не писали.
"""
from __future__ import unicode_literals

import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://fluent-fox.site"
WORDS_PATH = os.path.join(HERE, "graph_ru.json")

# Ключі, значення яких — не текст для читача, а адреси, коди й типи.
NOT_TEXT = {"@id", "@type", "@context", "url", "image", "sameAs", "logo",
            "availability", "priceCurrency", "hasMap", "contentUrl",
            "identifier", "email", "telephone"}

CYRILLIC = re.compile(r"[А-Яа-яІіЇїЄєҐґ]")

_words = None


def words():
    global _words
    if _words is None:
        _words = json.load(io.open(WORDS_PATH, encoding="utf-8"))
    return _words


def _is_file(path):
    """Останній сегмент адреси з крапкою — це файл (og-image.jpg), а не
    сторінка. Рахуємо тільки хвіст після домену: у самому домені крапки є
    завжди, і без цієї умови «https://fluent-fox.site/» вважалося б файлом."""
    rel = path[len(BASE):].strip("/")
    return "." in rel.rsplit("/", 1)[-1] if rel else False


def ru_url(url, own):
    """Додає `?lang=ru`, якщо адреса веде на цю саму сторінку.

    Спільні сутності лишаються зі своїми адресами: посилання на
    `#organization` з російської сторінки має вести на ту саму школу, що й з
    української, — інакше в графі заведеться друга.

    Файл (щось із крапкою в останньому сегменті) не чіпаємо взагалі: `?lang=ru`
    у адресі картинки — це вже не картинка."""
    if not isinstance(url, str) or not url.startswith(BASE) or "lang=ru" in url:
        return url
    path, sep, frag = url.partition("#")
    if path.rstrip("/") != own.rstrip("/"):
        return url
    if _is_file(path):
        return url
    return path + ("&" if "?" in path else "?") + "lang=ru" + sep + frag


def ru_link(url):
    """Внутрішнє посилання російською. На відміну від `ru_url`, працює для
    будь-якої адреси сайту: у крихтах `@id` — це не сутність, а посилання, і
    з російської сторінки воно має вести на російську ж головну."""
    if not isinstance(url, str) or not url.startswith(BASE) or "lang=ru" in url:
        return url
    path, sep, frag = url.partition("#")
    if _is_file(path):
        return url
    return path + ("&" if "?" in path else "?") + "lang=ru" + sep + frag


def localize(node, own, shared=(), link_ids=False):
    """Повертає копію вузла (чи списку вузлів) російською.

    `own` — адреса сторінки, чиї сутності перейменовуються на `?lang=ru`.
    `shared` — фрагменти, які лишаються спільними попри те, що формально
    належать цій сторінці: на головній це `#organization`, `#website` і
    картки вчителів."""
    if isinstance(node, list):
        return [localize(v, own, shared, link_ids) for v in node]
    if not isinstance(node, dict):
        return node

    # Усередині крихт `@id` — це посилання, а не сутність.
    crumb = node.get("@type") == "ListItem"

    out = {}
    for key, value in node.items():
        if key == "inLanguage" and isinstance(value, str):
            out[key] = "ru"
        elif key in ("@id", "url") and isinstance(value, str):
            frag = "#" + value.partition("#")[2] if "#" in value else ""
            if frag in shared:
                out[key] = value
            else:
                out[key] = ru_link(value) if link_ids else ru_url(value, own)
        elif key in NOT_TEXT:
            out[key] = value
        elif isinstance(value, (dict, list)):
            out[key] = localize(value, own, shared, link_ids or crumb)
        elif isinstance(value, str) and CYRILLIC.search(value):
            out[key] = translate(value)
        else:
            out[key] = value
    return out


def translate(text):
    ru = words().get(text.strip())
    if ru is None:
        raise SystemExit(
            "у графі є рядок без російського перекладу — допишіть його в\n"
            "tools/i18n/graph_ru.json:\n\n  %s\n" % text)
    return ru


def dumps(graph):
    return json.dumps({"@context": "https://schema.org", "@graph": graph},
                      ensure_ascii=False, separators=(",", ":"))


def replace(html, graph_json):
    """Підміняє перший блок ld+json у готовій сторінці."""
    m = re.search(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
                  html, re.S)
    if not m:
        raise SystemExit("у сторінці немає блоку ld+json")
    return html[:m.start(1)] + graph_json + html[m.end(1):]


def read(html):
    """Граф зі сторінки — списком вузлів."""
    m = re.search(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
                  html, re.S)
    if not m:
        raise SystemExit("у сторінці немає блоку ld+json")
    return json.loads(m.group(1))["@graph"]
