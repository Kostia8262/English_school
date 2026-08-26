/* Перемикач мови для посадкових сторінок.

   Головна сторінка будує текст через Alpine (`x-text="t.hero.title"`), і це
   означає, що в самому HTML тексту немає: краулер, який не виконує JS, бачить
   порожні теги. Тут інший контракт — український текст лежить у розмітці як
   звичайний текст, а російський живе в атрибуті `data-ru` і підставляється
   лише тоді, коли в адресі є `?lang=ru`. Так само влаштована сусідня школа
   програмування, і саме тому її сторінки читаються без запуску скриптів.

   Підтримуються: data-ru (текст), data-ru-content (мета-теги),
   data-ru-alt, data-ru-aria, data-ru-placeholder. */
(function () {
  'use strict';

  var RU = 'ru';
  var UK = 'uk';

  function currentLang() {
    return new URLSearchParams(location.search).get('lang') === RU ? RU : UK;
  }

  function withLang(href, lang) {
    // Через URL, а не конкатенацію: половина посилань має #якір, і дописаний
    // у хвіст ?lang=ru опинився б усередині фрагмента, а не в запиті.
    var u = new URL(href, location.href);
    if (u.origin !== location.origin) return href;
    if (lang === RU) u.searchParams.set('lang', RU);
    else u.searchParams.delete('lang');
    return u.pathname + u.search + u.hash;
  }

  function withLangAbs(href, lang) {
    // Для canonical і og:url перевірка на чужий домен не годиться: вони завжди
    // вказують на fluent-fox.site, і на будь-якому іншому origin (локальний
    // сервер, прев'ю) withLang мовчки повертав би адресу без ?lang=ru — саме так
    // російська версія й лишалася без самопосилального canonical.
    var u = new URL(href, location.href);
    if (lang === RU) u.searchParams.set('lang', RU);
    else u.searchParams.delete('lang');
    return u.toString();
  }

  function applyRu() {
    document.documentElement.lang = RU;

    document.querySelectorAll('[data-ru]').forEach(function (el) {
      el.textContent = el.dataset.ru;
    });
    document.querySelectorAll('[data-ru-content]').forEach(function (el) {
      el.setAttribute('content', el.dataset.ruContent);
    });
    document.querySelectorAll('[data-ru-alt]').forEach(function (el) {
      el.setAttribute('alt', el.dataset.ruAlt);
    });
    document.querySelectorAll('[data-ru-aria]').forEach(function (el) {
      el.setAttribute('aria-label', el.dataset.ruAria);
    });
    document.querySelectorAll('[data-ru-placeholder]').forEach(function (el) {
      el.setAttribute('placeholder', el.dataset.ruPlaceholder);
    });

    // Canonical і og:url мають вказувати самі на себе: інакше російська версія
    // каже Google «канонічна — українська», і в російській видачі сторінка
    // просто не з'являється.
    var canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) canonical.setAttribute('href', withLangAbs(canonical.href, RU));
    var ogUrl = document.querySelector('meta[property="og:url"]');
    if (ogUrl) ogUrl.content = withLangAbs(ogUrl.content, RU);
    var ogLocale = document.querySelector('meta[property="og:locale"]');
    if (ogLocale) ogLocale.content = 'ru_UA';

    document.querySelectorAll('a[href]').forEach(function (a) {
      var raw = a.getAttribute('href');
      if (!raw || raw.charAt(0) === '#') return;
      if (/^(https?:)?\/\//.test(raw) && new URL(raw, location.href).origin !== location.origin) return;
      if (/^(tel:|mailto:)/.test(raw)) return;
      a.setAttribute('href', withLang(raw, RU));
    });
  }

  function wireSwitcher() {
    document.querySelectorAll('[data-lang-btn]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        location.href = withLang(location.href, btn.dataset.langBtn);
      });
    });
  }

  function wireBurger() {
    var burger = document.getElementById('burger');
    var menu = document.getElementById('mobileMenu');
    if (!burger || !menu) return;
    burger.addEventListener('click', function () {
      var open = menu.hasAttribute('hidden');
      if (open) menu.removeAttribute('hidden');
      else menu.setAttribute('hidden', '');
      burger.setAttribute('aria-expanded', String(open));
    });
  }

  function markActive() {
    var lang = currentLang();
    document.querySelectorAll('[data-lang-btn]').forEach(function (btn) {
      var on = btn.dataset.langBtn === lang;
      btn.classList.toggle('bg-white', on);
      btn.classList.toggle('shadow', on);
      btn.classList.toggle('text-fox-600', on);
      btn.classList.toggle('text-gray-400', !on);
    });
  }

  function init() {
    if (currentLang() === RU) applyRu();
    markActive();
    wireSwitcher();
    wireBurger();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
