# -*- coding: utf-8 -*-
"""Міні-лендінг під рекламу: три блоки, форма вище згину.

Навіщо окрема сторінка, коли є головна і /probnyi-urok. Обидві — сторінки під
пошук, і це видно з заміру: головна 16,4 екрана телефона, /probnyi-urok — 15,8,
причому форма в ній аж на 11-му екрані. Для органіки це нормально: людина
прийшла читати. Людина з реклами прийшла з однією думкою — «безкоштовний
перший урок» — і або лишає заявку на першому екрані, або йде.

Що підглянули в конкурентів (21.10.2026, замір на 375px):
  AllRight  — веде рекламу не на лендінг, а у квіз на 21 крок, і перший крок
              найлегший: «Скільки років дитині?» емодзі-звірятами;
  Novakid   — /free-trial: форма в нульовому екрані й ОДНЕ поле;
  JustSchool, Englishdom — той самий оффер слово в слово: демо-урок,
              30 хвилин, діагностика рівня, без зобов'язань.

Три блоки і жодного зайвого:
  1. Герой: вік у заголовку + форма одразу, без скролу;
  2. Що буде на уроці — знімає страх перед дзвінком і «розводом»;
  3. Два відгуки, ціна одним рядком і повтор заклику.

Чого тут навмисно НЕМА: меню (воно веде геть зі сторінки), блогу, розділів
про методику, каруселі цін. Усе це є на головній, і туди ведуть органіку.

Оформлення НЕ вигадуємо: картки з іконкою в білому квадраті, рамка fox-100,
номер у кружечку і підйом на hover — це розмітка блоку «Почніть навчання за
4 кроки» з головної, один в один. Правило власника: спільний блок успадковує
UI головної, своїм лишається тільки текст.

Розмітку форми теж не пишемо свою — вирізаємо з уже зібраної index.html, тож
js/lead.js підхоплює її сам. Переклад — у data-ru, як на решті посадкових.

ПАСТКА, що коштувала зламаної кнопки: у скомпільованому css/style.css існують
лише ті класи Tailwind, які вже зустрічалися в розмітці сайту. `px-8` мовчки
дав нульовий падінг. Перед версткою перевіряти клас у css/style.css. Відомо
відсутні: px-8, text-5xl, py-14, ring-1, shadow-fox-lg, bg-fox-600,
text-yellow-*. Тому колір зірок і дрібні штрихи — власним правилом у <style>.

Сторінка **noindex** і не йде в sitemap: вона дублює оффер головної.

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
    frag = home[start:end + len("</form>")]
    # Відносні посилання всередині форми («privacy.html») з будь-якого шляху
    # ведуть у 404 — робимо абсолютними.
    frag = frag.replace('href="privacy.html"', 'href="/privacy.html"')
    frag = frag.replace('href="offer.html"', 'href="/offer.html"')
    return frag


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


def cut_footer(home):
    """Підвал головної — цілком, з переписаними посиланнями.

    Лендінг живе на ПІДДОМЕНІ (lp.fluent-fox.site), а підвал головної повний
    відносних адрес («/tsiny», «blog/», «#prices»). Залишити їх як є —
    означає 38 посилань у 404. Тому всі внутрішні переписуємо на абсолютні
    до основного сайта; якір #form — наш власний, його не чіпаємо.
    """
    i = home.find("<footer")
    j = home.find("</footer>", i)
    if i < 0 or j < 0:
        sys.exit("На головній не знайдено <footer>")
    f = home[i:j + len("</footer>")]

    def fix(m):
        href = m.group(1)
        if href.startswith(("http://", "https://", "tel:", "mailto:", "viber:")):
            return m.group(0)
        if href == "#form":
            return m.group(0)
        if href.startswith("#"):
            return 'href="%s/%s"' % (BASE, href)
        if href.startswith("/"):
            return 'href="%s%s"' % (BASE, href)
        return 'href="%s/%s"' % (BASE, href)

    return re.sub(r'href="([^"]*)"', fix, f)


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
  /* Правила, без яких сторінка виглядає чи поводиться не так. Усе інше —
     класи з css/style.css, тобто та сама дизайн-система, що й на головній. */

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
        частина форми їде за екран. На головній там 14px (клас text-sm). */
  .form-input { font-size: 16px; }

  /* 4. Жовтого тексту в скомпільованому css/style.css немає жодного відтінку
        — Tailwind кладе туди лише ті класи, що вже зустрілися в розмітці
        сайту. Тому колір зірок свій, а не text-yellow-400. */
  .lp-stars { color: #FACC15; letter-spacing: .08em; }

  /* 5. Два м'яких кола на тлі героя. Чисто декоративні, тому aria-hidden і
        pointer-events:none — вони не повинні ловити тапи по формі. */
  .lp-blob { position: absolute; border-radius: 9999px; pointer-events: none; }

  /* 6. Тінь картки форми: shadow-fox-lg у css немає, а shadow-fox-sm надто
        слабка, щоб картка читалась як головний елемент екрана. */
  .lp-card { box-shadow: 0 18px 40px -12px rgba(17, 24, 39, .18); }

  /* 7. Слайдер відгуків. Шість карток у рядок на телефоні не поміщаються,
        а сітка 2x3 — це три екрани тексту, які ніхто не читає. Горизонтальна
        стрічка зі scroll-snap гортається пальцем звично й не потребує жодної
        бібліотеки: сам скрол робить браузер, скрипт лише підсвічує крапку. */
  .lp-slider {
    display: flex; gap: 1rem; overflow-x: auto;
    scroll-snap-type: x mandatory; scroll-behavior: smooth;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none; padding-bottom: .25rem;
  }
  .lp-slider::-webkit-scrollbar { display: none; }
  .lp-slide { flex: 0 0 86%%; scroll-snap-align: center; }
  @media (min-width: 768px) {
    .lp-slide { flex-basis: 47%%; }
    /* Тарифів три — на десктопі вони мають поміститися всі одразу, інакше
       людина порівнює ціни гортанням, а це найгірше місце для гортання. */
    .lp-slide-3 { flex-basis: 31.5%%; }
  }

  .lp-dot {
    width: 8px; height: 8px; border-radius: 9999px;
    background: #E5E7EB; transition: width .25s, background .25s;
  }
  .lp-dot[aria-current="true"] { width: 26px; background: var(--fox-500); }

  /* 8. Порядок героя. На телефоні форма має йти ОДРАЗУ за заголовком: саме
        заради неї людина прийшла з реклами, і гортати заради неї екран вона
        не стане. Переваги й цифри — під формою, вони дочитуються вже потім.
        На десктопі місця вистачає на дві колонки: текст ліворуч, форма
        праворуч на всю висоту. Робимо власним правилом, бо потрібних
        класів (md:col-start-*, md:row-span-*) у css/style.css немає. */
  .lp-hero { display: grid; gap: 1.75rem; }
  @media (min-width: 768px) {
    .lp-hero { grid-template-columns: 1fr 1fr; gap: 2rem; align-items: start; }
    .lp-hero-top  { grid-column: 1; grid-row: 1; }
    .lp-hero-more { grid-column: 1; grid-row: 2; }
    .lp-hero-form { grid-column: 2; grid-row: 1 / span 2; }
  }
</style>
</head>
<body class="bg-white text-gray-900 antialiased">
"""

HERO = """
<!-- ═══ Блок 1. Герой: вік у заголовку і форма одразу ═══════════════════ -->
<header class="border-b border-gray-100 bg-white">
  <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
    <span class="flex items-center gap-2">
      <img src="/logo.svg" alt="" class="w-9 h-9" width="36" height="36" fetchpriority="high">
      <span class="font-black text-lg leading-none">Fluent<span class="text-fox-500">Fox</span></span>
    </span>
    <span class="flex flex-col items-end leading-tight">
      <a href="tel:+380954624672" class="text-sm font-black text-gray-700 whitespace-nowrap">095 462-46-72</a>
      <a href="tel:+380682522876" class="text-sm font-black text-gray-700 whitespace-nowrap">068 252-28-76</a>
    </span>
  </div>
</header>

<section class="relative overflow-hidden bg-gradient-to-b from-fox-50 to-white">
  <div class="lp-blob" style="width:260px;height:260px;background:#FFE8DD;top:-90px;left:-70px" aria-hidden="true"></div>
  <div class="lp-blob" style="width:200px;height:200px;background:#FFF1E8;bottom:-80px;right:-60px" aria-hidden="true"></div>

  <div class="lp-hero relative max-w-5xl mx-auto px-4 py-8 md:py-16">

    <div class="lp-hero-top">
      <p class="inline-flex items-center gap-2 bg-white border-2 border-fox-100 rounded-full px-3 py-1.5 mb-5 shadow-fox-sm">
        <img src="/icons/gift.webp" alt="" width="28" height="28" class="w-6 h-6" loading="lazy" decoding="async">
        <span class="text-xs font-black uppercase tracking-tight text-fox-600"
              data-ru="Первый урок — бесплатно">Перший урок — безкоштовно</span>
      </p>

      <h1 class="text-3xl md:text-4xl font-black leading-tight tracking-tight mb-4"
          data-ru="Пробный урок английского для ребёнка 6–18 лет">
        Пробний урок англійської<br class="hidden md:inline"> для дитини 6–18 років</h1>

      <p class="text-gray-500 text-base md:text-lg mb-6 leading-relaxed"
         data-ru="Онлайн, малые группы до 5 учеников, живой учитель. На пробном уроке познакомимся, определим уровень и покажем, как проходит занятие.">
        Онлайн, малі групи до 5 учнів, живий учитель. На пробному уроці
        познайомимось, визначимо рівень і покажемо, як іде заняття.</p>
    </div>

    <!-- Форма — та сама, що на головній: вирізана звідти цілим шматком -->
    <div class="lp-hero-form lp-card bg-white rounded-3xl border-2 border-fox-200 p-5 md:p-6">
      <h2 class="text-xl md:text-2xl font-black mb-1 leading-tight"
          data-ru="Запишитесь на пробный урок">Запишіться на пробний урок</h2>
      <p class="text-sm text-gray-400 mb-5 font-medium"
         data-ru="Передзвоним в течение 30 минут">Передзвонимо протягом 30 хвилин</p>
%(form)s
    </div>

    <div class="lp-hero-more">
      <ul class="space-y-3 mb-6">
        %(bullets)s
      </ul>
      <div class="grid grid-cols-2 gap-3">
        %(trust)s
      </div>
    </div>

  </div>
</section>
"""

BULLET = """<li class="flex items-start gap-3">
          <span class="shrink-0 w-6 h-6 rounded-full bg-fox-100 text-fox-600 font-black text-xs flex items-center justify-center mt-0.5">✓</span>
          <span class="min-w-0 flex-1 text-gray-700 font-medium" data-ru="%(ru)s">%(uk)s</span>
        </li>"""

TRUST = """<div class="flex items-center gap-2.5 bg-white border border-gray-100 rounded-2xl px-3 py-2.5 shadow-fox-sm">
          <img src="/icons/%(icon)s" alt="" width="32" height="32" class="w-7 h-7 shrink-0" loading="lazy" decoding="async">
          <span class="leading-tight">
            <strong class="block text-gray-900 font-black text-sm">%(big)s</strong>
            <span class="block text-gray-400 text-xs font-medium" data-ru="%(ru)s">%(small)s</span>
          </span>
        </div>"""

WHAT = """
<!-- ═══ Блок 2. Що буде на уроці — знімає страх ═════════════════════════ -->
<section class="bg-gray-900 py-12 md:py-16">
  <div class="max-w-5xl mx-auto px-4">
    <p class="text-center text-xs font-black uppercase tracking-tight text-fox-500 mb-2"
       data-ru="Как это проходит">Як це проходить</p>
    <h2 class="text-2xl md:text-3xl font-black text-center text-white mb-10 leading-tight tracking-tight"
        data-ru="Что будет на пробном уроке">Що буде на пробному уроці</h2>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-6 md:gap-10">
      %(cards)s
    </div>

    <p class="text-center text-sm text-gray-300 mt-10 font-medium"
       data-ru="Урок длится 30–40 минут. Нужны только ноутбук или планшет и наушники.">
      Урок триває 30–40 хвилин. Потрібні лише ноутбук чи планшет і навушники.</p>
  </div>
</section>
"""

# Картка — розмітка блоку «Почніть навчання за 4 кроки» з головної.
CARD = """<div class="flex flex-col items-center text-center group cursor-default">
        <div class="relative mb-5">
          <div class="w-[72px] h-[72px] rounded-2xl bg-white/10 flex items-center justify-center border-2 border-white/10 group-hover:border-fox-400 group-hover:-translate-y-1.5 transition-all duration-300 select-none">
            <img src="/icons/%(icon)s" alt="" width="64" height="64" class="w-10 h-10" loading="lazy" decoding="async">
          </div>
          <div class="absolute -bottom-2.5 -right-2.5 w-7 h-7 rounded-full bg-gradient-to-br from-fox-500 to-fox-600 text-white text-xs font-black flex items-center justify-center shadow-fox-sm">%(n)s</div>
        </div>
        <h3 class="font-black text-white mb-1.5 leading-tight text-base" data-ru="%(title_ru)s">%(title)s</h3>
        <p class="text-gray-400 text-sm leading-relaxed" data-ru="%(text_ru)s">%(text)s</p>
      </div>"""

PROOF = """
<!-- ═══ Блок 3. Тарифи — усі три, цифри з головної ══════════════════════ -->
<section class="bg-gradient-to-b from-white to-fox-50 py-12 md:py-16">
  <div class="max-w-5xl mx-auto px-4">
    <p class="text-center text-xs font-black uppercase tracking-tight text-fox-600 mb-2"
       data-ru="Цены">Ціни</p>
    <h2 class="text-2xl md:text-3xl font-black text-center mb-3 leading-tight tracking-tight"
        data-ru="Сколько стоит обучение">Скільки коштує навчання</h2>
    <p class="text-center text-gray-400 text-sm font-medium mb-10"
       data-ru="После бесплатного урока — если понравится">Після безкоштовного уроку — якщо сподобається</p>

    <div class="lp-slider" data-slider="plans">
      %(plans)s
    </div>
    <div class="flex items-center justify-center gap-2 mt-6" data-dots="plans">
      %(plan_dots)s
    </div>

    <p class="text-center text-sm text-gray-400 mt-8 font-medium"
       data-ru="Первый пробный урок — бесплатно. При записи двух детей из семьи — скидка 15%% на второго ребёнка.">
      Перший пробний урок — безкоштовно. При записі двох дітей з родини —
      знижка 15%% на другу дитину.</p>
  </div>
</section>

"""

# Підвал головної цілком — власник попросив «нормальний, з сайта».
FOOT = """%(footer)s

<script>
/* Підсвічування крапки під слайдером. Гортання робить браузер (scroll-snap),
   тут лише дві речі: яка картка зараз по центру і перехід по кліку. */
(function () {
  /* Слайдер може бути не один, тож крапки прив'язані до стрічки за іменем
     (data-slider="x" ↔ data-dots="x"), а не беремо перший-ліпший елемент. */
  [].slice.call(document.querySelectorAll('[data-slider]')).forEach(function (box) {
  var holder = document.querySelector('[data-dots="' + box.getAttribute('data-slider') + '"]');
  if (!holder) return;
  var dots = [].slice.call(holder.querySelectorAll('[data-dot]'));
  var slides = [].slice.call(box.querySelectorAll('.lp-slide'));
  if (!dots.length || !slides.length) return;

  function mark() {
    var center = box.scrollLeft + box.clientWidth / 2, best = 0, bestDist = Infinity;
    slides.forEach(function (s, i) {
      var d = Math.abs(s.offsetLeft + s.offsetWidth / 2 - center);
      if (d < bestDist) { bestDist = d; best = i; }
    });
    dots.forEach(function (d, i) { d.setAttribute('aria-current', i === best ? 'true' : 'false'); });
  }

  var ticking = false;
  box.addEventListener('scroll', function () {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(function () { mark(); ticking = false; });
  }, { passive: true });

  dots.forEach(function (dot, i) {
    dot.addEventListener('click', function () {
      var s = slides[i];
      box.scrollTo({ left: s.offsetLeft - (box.clientWidth - s.offsetWidth) / 2, behavior: 'smooth' });
    });
  });

  mark();
  });
})();
</script>

<script src="/js/lang.js?v=%(v)s" defer></script>
<script src="/js/lead.js?v=%(v)s" defer></script>
<script src="/js/track.js?v=%(v)s" defer></script>
<script src="/js/subscribe.js?v=%(v)s" defer></script>
</body>
</html>
"""

PLAN = """<div class="lp-slide lp-slide-3 lp-card bg-white rounded-3xl border-2 %(border)s p-6 flex flex-col">
        %(badge)s
        <h3 class="font-black text-lg mb-1 leading-tight" data-ru="%(name_ru)s">%(name)s</h3>
        <p class="text-gray-400 text-sm font-medium mb-4" data-ru="%(sub_ru)s">%(sub)s</p>
        <p class="text-3xl font-black mb-5 tracking-tight">%(price)s
          <span class="text-sm font-black text-gray-400">грн / <span data-ru="месяц">місяць</span></span></p>
        <ul class="space-y-2 mb-6 flex-1">
          %(features)s
        </ul>
        <a href="#form" class="block text-center bg-gradient-to-br from-fox-500 to-fox-600 text-white font-black rounded-full px-6 py-3 shadow-fox-sm transition-all duration-300 hover:-translate-y-0.5"
           data-ru="Записаться">Записатись</a>
      </div>"""

PLAN_FEATURE = """<li class="flex items-start gap-2">
            <span class="shrink-0 w-5 h-5 rounded-full bg-fox-100 text-fox-600 font-black text-xs flex items-center justify-center mt-0.5">✓</span>
            <span class="min-w-0 flex-1 text-gray-600 text-sm" data-ru="%(ru)s">%(uk)s</span>
          </li>"""

PLAN_BADGE = """<p class="inline-block self-start bg-fox-500 text-white text-xs font-black uppercase tracking-tight rounded-full px-3 py-1 mb-3"
           data-ru="Популярный">Популярний</p>"""

DOT = """<button type="button" class="lp-dot" data-dot aria-current="%(cur)s" aria-label="Відгук %(n)s"></button>"""

BULLETS = [
    ("Без зобов'язань і без оплати", "Без обязательств и без оплаты"),
    ("Підберемо вчителя під характер дитини", "Подберём учителя под характер ребёнка"),
    ("Будь-який рівень — від нуля до підготовки до НМТ", "Любой уровень — от нуля до подготовки к НМТ"),
]

TRUSTS = [
    ("group.webp", "500+", "учнів навчаються", "учеников учатся"),
    ("star.webp", "4.9", "середній рейтинг", "средний рейтинг"),
    ("medal.webp", "12+", "років досвіду", "лет опыта"),
    ("cap.webp", "15", "вчителів", "учителей"),
]

# Цифри взяті з блоку «Скільки коштує навчання» на головній, а не з пам'яті:
# ціна живе у восьми місцях, і розходження тут помітила б тільки людина, яка
# прийшла з реклами й побачила на сайті інше число.
PLANS = [
    ("Група 1×/тиждень", "Группа 1×/неделю", "4 заняття на місяць · до 5 учнів",
     "4 занятия в месяц · до 5 учеников", "1 800", False,
     [("300 грн за 1 годину", "300 грн за 1 час"),
      ("4 уроки по 1,5 години", "4 урока по 1,5 часа"),
      ("Група до 5 учнів", "Группа до 5 учеников")]),
    ("Група 2×/тиждень", "Группа 2×/неделю", "8 занять на місяць · до 5 учнів",
     "8 занятий в месяц · до 5 учеников", "3 600", True,
     [("300 грн за 1 годину", "300 грн за 1 час"),
      ("8 уроків по 1,5 години", "8 уроков по 1,5 часа"),
      ("Група до 5 учнів", "Группа до 5 учеников"),
      ("Максимальний прогрес", "Максимальный прогресс")]),
    ("Індивідуально", "Индивидуально", "8 занять на місяць · особистий підхід",
     "8 занятий в месяц · личный подход", "4 800", False,
     [("600 грн за 1 годину", "600 грн за 1 час"),
      ("8 уроків по 1 годині", "8 уроков по 1 часу"),
      ("Повна увага вчителя", "Полное внимание учителя"),
      ("Індивідуальний план навчання", "Индивидуальный план обучения")]),
]

CARDS = [
    ("1", "chat.webp", "Знайомство", "Знакомство",
     "Учитель поговорить з дитиною англійською й українською, щоб їй було спокійно.",
     "Учитель поговорит с ребёнком по-английски и по-украински, чтобы ему было спокойно."),
    ("2", "target.webp", "Визначимо рівень", "Определим уровень",
     "Без тестів і оцінок — у розмові та грі. Скажемо рівень за шкалою CEFR.",
     "Без тестов и оценок — в разговоре и игре. Скажем уровень по шкале CEFR."),
    ("3", "laptop.webp", "Покажемо урок", "Покажем урок",
     "Дитина побачить, як виглядає заняття: завдання, ігри, робота на екрані.",
     "Ребёнок увидит, как выглядит занятие: задания, игры, работа на экране."),
    ("4", "shield.webp", "Без зобов'язань", "Без обязательств",
     "Не сподобалось — нічого не платите й нікуди не записуєтесь.",
     "Не понравилось — ничего не платите и никуда не записываетесь."),
]


def main():
    home = read_home()
    form = cut_form(home)

    bullets = "\n        ".join(BULLET % {"uk": uk, "ru": ru} for uk, ru in BULLETS)
    trust = "\n        ".join(
        TRUST % {"icon": i, "big": b, "small": s, "ru": r} for i, b, s, r in TRUSTS)
    cards = "\n      ".join(
        CARD % {"n": n, "icon": ic, "title": t, "title_ru": tru, "text": x, "text_ru": xru}
        for n, ic, t, tru, x, xru in CARDS)
    plans = "\n      ".join(
        PLAN % {
            "name": n, "name_ru": nru, "sub": sub, "sub_ru": subru, "price": price,
            "border": "border-fox-300" if top else "border-gray-100",
            "badge": PLAN_BADGE if top else "",
            "features": "\n          ".join(
                PLAN_FEATURE % {"uk": u, "ru": r} for u, r in feats),
        }
        for n, nru, sub, subru, price, top, feats in PLANS)
    plan_dots = "\n      ".join(
        DOT % {"n": i + 1, "cur": "true" if i == 0 else "false"}
        for i in range(len(PLANS)))

    page = (
        HEAD % {"ga": GA_ID, "v": ASSET_VERSION, "pixel": PIXEL_ID}
        + (HERO % {"form": form, "bullets": bullets, "trust": trust}
           ).replace('<form', '<form id="form"', 1)
        + WHAT % {"cards": cards}
        + PROOF % {"plans": plans, "plan_dots": plan_dots}
        + FOOT % {"footer": cut_footer(home), "v": ASSET_VERSION}
    )

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    io.open(OUT, "w", encoding="utf-8", newline="").write(page)

    print("lp/probnyi-urok/index.html — %d байт" % len(page.encode("utf-8")))
    print("  форма з головної: %d байт" % len(form.encode("utf-8")))
    print("  адреса реклами: https://lp.fluent-fox.site/")


if __name__ == "__main__":
    main()
