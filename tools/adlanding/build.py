# -*- coding: utf-8 -*-
"""Міні-лендінг під рекламу: три блоки, форма вище згину.

Навіщо окрема сторінка, коли є головна і /probnyi-urok. Обидві — сторінки під
пошук, і це видно з заміру: головна 16,4 екрана телефона, /probnyi-urok — 15,8,
причому форма в ній аж на 11-му екрані. Для органіки це нормально: людина
прийшла читати. Людина з реклами прийшла з однією думкою — «безкоштовний
перший урок» — і або лишає заявку на першому екрані, або йде.

Що підглянули в конкурентів (21.10.2026, замір на 375px):
  AllRight  — головна 22,2 екрана, але в ПЕРШОМУ екрані не форма, а один
              легкий крок: «Оберіть вік дитини» кнопками. Телефон питають уже
              після нього;
  Novakid   — 16,3 екрана, у H1 одразу вік («4–12 років»), у шапці кнопка
              «Пробний урок»;
  JustSchool, Englishdom — той самий оффер слово в слово: безкоштовний
              демо-урок, 30 хвилин, діагностика рівня, без зобов'язань.

Звідси три блоки і жодного зайвого:
  1. Герой: вік у заголовку + форма одразу, без скролу;
  2. Що буде на уроці — знімає страх перед дзвінком і «розводом»;
  3. Два відгуки, ціна одним рядком і повтор заклику.

Чого тут навмисно НЕМА: меню (воно веде геть зі сторінки), блогу, розділів
про методику, каруселі цін. Усе це є на головній, і туди ведуть органіку.

Розмітку форми НЕ пишемо свою — вирізаємо з уже зібраної index.html. Так
працює правило власника «спільний блок успадковує UI головної»: ті самі класи,
ті самі id, та сама логіка в js/lead.js, і сторінка не старіє окремо від сайту.
Перекладу теж не пишемо: російський текст живе в data-ru, як на решті
посадкових, і підставляється js/lang.js на ?lang=ru.

Сторінка **noindex** і не йде в sitemap: вона дублює оффер головної, і в
пошуку їй робити нема чого — інакше це канібалізація з головною.

Збирається ПІСЛЯ tools/home/build.py (бере з його результату форму):
    python tools/home/build.py && python tools/adlanding/build.py
"""
from __future__ import unicode_literals

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
HOME = os.path.join(ROOT, "index.html")
OUT_DIR = os.path.join(ROOT, "lp", "probnyi-urok")
OUT = os.path.join(OUT_DIR, "index.html")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from assets import ASSET_VERSION  # noqa: E402

PIXEL_ID = "931791603129774"
GA_ID = "G-K60LSESFTV"
BASE = "https://fluent-fox.site"


def read_home():
    if not os.path.exists(HOME):
        sys.exit("Немає index.html — спочатку `python tools/home/build.py`")
    return io.open(HOME, encoding="utf-8").read()


def cut_form(home):
    """Форма заявки з блоку контактів головної, цілком.

    Шукаємо по data-lead-form, а не по класу: класи Tailwind міняються при
    кожній перевёрстці, атрибут — це контракт із js/lead.js.
    """
    i = home.find("data-lead-form")
    if i < 0:
        sys.exit("На головній не знайдено форму з data-lead-form")
    start = home.rfind("<form", 0, i)
    end = home.find("</form>", i)
    if start < 0 or end < 0:
        sys.exit("Розмітка форми на головній виглядає інакше, ніж очікували")
    return home[start:end + len("</form>")]


def cut_reviews(home, want=2):
    """Два відгуки з головної — текст і підпис автора.

    Беремо з JSON-LD (`reviewBody` + `author.name`), а не з розмітки. Два
    прорахунки, яких це уникає. Перший: та сама цитата лежить у розмітці двічі
    — українською в тексті й російською в data-ru, і вибірка «по лапках»
    приносила російський дубль як другий відгук. Другий: усередині відгуків є
    вкладені лапки («мамо, не хочу», «відмінно»), і нежадібний пошук обривав
    цитату на середині речення. У JSON-LD текст лежить цілим полем.

    Відгуки справжні — правити чиюсь оцінку чи ім'я було б підробкою від
    імені школи, тож нічого, крім вибору двох перших, тут не відбувається.
    """
    bodies = re.findall(r'"reviewBody":\s*"((?:[^"\\]|\\.)*)"', home)
    authors = re.findall(r'"author":\s*\{\s*"@type":\s*"Person",\s*"name":\s*"([^"]+)"', home)
    found = []
    for i, raw in enumerate(bodies):
        text = raw.encode().decode("unicode_escape") if "\\u" in raw else raw
        text = re.sub(r"\s+", " ", text.replace('\\"', '"')).strip()
        if len(text) < 80:
            continue
        found.append((text, authors[i] if i < len(authors) else ""))
        if len(found) >= want:
            break
    if len(found) < want:
        sys.exit("Не вдалося дістати %d відгуки з JSON-LD головної" % want)
    return found


HEAD = """<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<!-- Сторінка під рекламу: у пошуку їй робити нема чого, вона дублює оффер
     головної. Без noindex це була б канібалізація з index.html. -->
<meta name="robots" content="noindex, nofollow">

<title>Безкоштовний пробний урок англійської для дитини — FluentFox</title>
<meta name="description" content="Безкоштовний пробний урок англійської для дитини 6–18 років. Онлайн, малі групи до 5 учнів. Залиште заявку — передзвонимо протягом 30 хвилин.">

<script async src="https://www.googletagmanager.com/gtag/js?id=%(ga)s"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','%(ga)s');</script>

<!-- Піксель Meta -->
<script src="/js/pixel.js?v=%(v)s"></script>
<noscript><img height="1" width="1" style="display:none" alt=""
  src="https://www.facebook.com/tr?id=%(pixel)s&amp;ev=PageView&amp;noscript=1"></noscript>

<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="preload" as="style" href="/css/style.css?v=%(v)s">
<link rel="stylesheet" href="/css/style.css?v=%(v)s" fetchpriority="high">

<style>
  /* Три правила, без яких форма з головної тут не працює як треба. */

  /* 1. Форма і модалка ховаються атрибутом hidden, а їхні класи ставлять
        flex — і flex перемагає типовий display браузера. */
  [hidden] { display: none !important; }

  /* 2. Кільце фокуса — те саме, що на головній. */
  :root { --fox-ring: rgba(255, 107, 53, .18); --fox-500: #FF6B35; }
  .form-input:focus {
    outline: none;
    border-color: var(--fox-500);
    box-shadow: 0 0 0 4px var(--fox-ring);
  }

  /* 3. 16px у полях — НЕ косметика. iOS Safari автоматично збільшує сторінку,
        коли тапають у поле зі шрифтом менше 16px: людина провалюється в зум,
        частина форми їде за екран. На головній там 14px (клас text-sm), і це
        треба полагодити й там; тут ставимо одразу, бо сюди йде реклама. */
  .form-input { font-size: 16px; }

  /* 4. Жовтого тексту в скомпільованому css/style.css немає жодного
        відтінку — Tailwind кладе туди лише ті класи, що вже зустрілися
        в розмітці сайту. Тому колір зірок свій, а не text-yellow-400:
        такий клас просто не існував би. */
  .lp-stars { color: #FACC15; letter-spacing: .05em; }
</style>
</head>
<body class="bg-white text-gray-900 antialiased">
"""

HERO = """
<!-- ═══ Блок 1. Герой: вік у заголовку і форма одразу ═══════════════════ -->
<header class="border-b border-gray-100">
  <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
    <span class="flex items-center gap-2">
      <img src="/logo.svg" alt="" class="w-9 h-9" width="36" height="36" fetchpriority="high">
      <span class="font-black text-lg">Fluent<span class="text-fox-500">Fox</span></span>
    </span>
    <a href="tel:+380954624672" class="text-sm font-bold text-gray-700 whitespace-nowrap">095 462-46-72</a>
  </div>
</header>

<section class="bg-gradient-to-b from-fox-50 to-white">
  <div class="max-w-5xl mx-auto px-4 py-8 md:py-14 grid md:grid-cols-2 gap-8 items-start">

    <div>
      <p class="inline-block bg-fox-500 text-white text-xs font-black uppercase tracking-wide rounded-full px-3 py-1 mb-4"
         data-ru="Первый урок — бесплатно">Перший урок — безкоштовно</p>

      <h1 class="text-3xl md:text-4xl font-black leading-tight mb-4"
          data-ru="Пробный урок английского для ребёнка 6–18 лет">
        Пробний урок англійської для дитини 6–18 років</h1>

      <p class="text-gray-600 mb-6 leading-relaxed"
         data-ru="Онлайн, малые группы до 5 учеников, живой учитель. На пробном уроке познакомимся, определим уровень и покажем, как проходит занятие.">
        Онлайн, малі групи до 5 учнів, живий учитель. На пробному уроці
        познайомимось, визначимо рівень і покажемо, як іде заняття.</p>

      <ul class="space-y-2 mb-6">
        <li class="flex items-start gap-2"><span class="text-fox-500 font-black">✓</span>
          <span data-ru="Без обязательств и без оплаты">Без зобов'язань і без оплати</span></li>
        <li class="flex items-start gap-2"><span class="text-fox-500 font-black">✓</span>
          <span data-ru="Подберём учителя под характер ребёнка">Підберемо вчителя під характер дитини</span></li>
        <li class="flex items-start gap-2"><span class="text-fox-500 font-black">✓</span>
          <span data-ru="Любой уровень — от нуля до подготовки к НМТ">Будь-який рівень — від нуля до підготовки до НМТ</span></li>
      </ul>

      <div class="flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-500 font-medium">
        <span><strong class="text-gray-900">500+</strong>
          <span data-ru="учеников">учнів</span></span>
        <span><strong class="text-gray-900">4.9</strong>
          <span data-ru="рейтинг">рейтинг</span></span>
        <span><strong class="text-gray-900">12+</strong>
          <span data-ru="лет опыта">років досвіду</span></span>
      </div>
    </div>

    <!-- Форма — та сама, що на головній: вирізана звідти цілим шматком -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-5 md:p-6">
      <h2 class="text-xl font-black mb-1" data-ru="Запишитесь на пробный урок">Запишіться на пробний урок</h2>
      <p class="text-sm text-gray-500 mb-5" data-ru="Передзвоним в течение 30 минут">Передзвонимо протягом 30 хвилин</p>
%(form)s
    </div>

  </div>
</section>
"""

WHAT = """
<!-- ═══ Блок 2. Що буде на уроці — знімає страх ═════════════════════════ -->
<section class="py-10 md:py-14">
  <div class="max-w-5xl mx-auto px-4">
    <h2 class="text-2xl md:text-3xl font-black text-center mb-8 leading-tight"
        data-ru="Что будет на пробном уроке">Що буде на пробному уроці</h2>

    <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
      %(cards)s
    </div>

    <p class="text-center text-sm text-gray-500 mt-6"
       data-ru="Урок длится 30–40 минут. Нужны только ноутбук или планшет и наушники.">
      Урок триває 30–40 хвилин. Потрібні лише ноутбук чи планшет і навушники.</p>
  </div>
</section>
"""

CARD = """<div class="bg-gray-50 rounded-2xl p-5">
        <div class="w-9 h-9 rounded-xl bg-fox-500 text-white font-black flex items-center justify-center mb-3">%(n)s</div>
        <h3 class="font-bold mb-1" data-ru="%(title_ru)s">%(title)s</h3>
        <p class="text-sm text-gray-600 leading-relaxed" data-ru="%(text_ru)s">%(text)s</p>
      </div>"""

PROOF = """
<!-- ═══ Блок 3. Відгуки, ціна і повтор заклику ══════════════════════════ -->
<section class="bg-gray-50 py-10 md:py-14">
  <div class="max-w-5xl mx-auto px-4">
    <h2 class="text-2xl md:text-3xl font-black text-center mb-8 leading-tight"
        data-ru="Что говорят родители">Що кажуть батьки</h2>

    <div class="grid md:grid-cols-2 gap-4 mb-8">
      %(reviews)s
    </div>

    <div class="bg-white rounded-2xl border border-gray-100 p-6 text-center">
      <p class="text-gray-600 mb-1" data-ru="После бесплатного урока — если понравится:">
        Після безкоштовного уроку — якщо сподобається:</p>
      <p class="text-2xl font-black mb-4">1 800 <span class="text-base font-bold text-gray-500">грн /
        <span data-ru="месяц">місяць</span></span></p>
      <a href="#form" class="inline-block bg-fox-500 hover:bg-fox-600 text-white font-black rounded-full px-7 py-4 transition-colors"
         data-ru="Записаться на урок">Записатися на урок</a>
      <p class="text-xs text-gray-400 mt-4"
         data-ru="Группы до 5 учеников · скидка 15%% на второго ребёнка">
        Групи до 5 учнів · знижка 15%% на другу дитину</p>
    </div>
  </div>
</section>

<footer class="py-8 text-center text-sm text-gray-500">
  <p class="mb-2">
    <a href="tel:+380954624672" class="font-bold text-gray-700">095 462-46-72</a>
  </p>
  <p>
    <a href="/privacy.html" class="underline" data-ru="Политика конфиденциальности">Політика конфіденційності</a>
    ·
    <a href="/terms.html" class="underline" data-ru="Публичная оферта">Публічна оферта</a>
  </p>
</footer>

<script src="/js/lang.js?v=%(v)s" defer></script>
<script src="/js/lead.js?v=%(v)s" defer></script>
<script src="/js/track.js?v=%(v)s" defer></script>
</body>
</html>
"""

CARDS = [
    ("1", "Знайомство", "Знакомство",
     "Учитель поговорить з дитиною англійською й українською, щоб їй було спокійно.",
     "Учитель поговорит с ребёнком по-английски и по-украински, чтобы ему было спокойно."),
    ("2", "Визначимо рівень", "Определим уровень",
     "Без тестів і оцінок — у розмові та грі. Скажемо рівень за шкалою CEFR.",
     "Без тестов и оценок — в разговоре и игре. Скажем уровень по шкале CEFR."),
    ("3", "Покажемо урок", "Покажем урок",
     "Дитина побачить, як виглядає заняття: завдання, ігри, робота на екрані.",
     "Ребёнок увидит, как выглядит занятие: задания, игры, работа на экране."),
    ("4", "Без зобов'язань", "Без обязательств",
     "Не сподобалось — нічого не платите й нікуди не записуєтесь.",
     "Не понравилось — ничего не платите и никуда не записываетесь."),
]


def main():
    home = read_home()
    form = cut_form(home)
    reviews = cut_reviews(home)

    cards = "\n      ".join(
        CARD % {"n": n, "title": t, "title_ru": tru, "text": x, "text_ru": xru}
        for n, t, tru, x, xru in CARDS)

    review_html = "\n      ".join(
        '<figure class="bg-white rounded-2xl p-5 border border-gray-100">'
        '<div class="lp-stars mb-2">★★★★★</div>'
        '<blockquote class="text-gray-700 leading-relaxed italic">«%s»</blockquote>'
        '<figcaption class="mt-3 text-sm font-bold text-gray-500">%s</figcaption>'
        '</figure>' % (text, author) for text, author in reviews)

    page = (
        HEAD % {"ga": GA_ID, "v": ASSET_VERSION, "pixel": PIXEL_ID}
        + (HERO % {"form": form}).replace('<form', '<form id="form"', 1)
        + WHAT % {"cards": cards}
        + PROOF % {"reviews": review_html, "v": ASSET_VERSION}
    )

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    io.open(OUT, "w", encoding="utf-8", newline="").write(page)

    print("lp/probnyi-urok/index.html — %d байт" % len(page.encode("utf-8")))
    print("  форма з головної: %d байт" % len(form.encode("utf-8")))
    print("  відгуків узято: %d" % len(reviews))
    print("  адреса: %s/lp/probnyi-urok/" % BASE)


if __name__ == "__main__":
    main()
