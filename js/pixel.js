/* Згода на cookie, піксель Meta і дані для серверної події Lead.

   Чому окремий файл, а не вставка в <head> кожного шаблону, як радить
   майстер у Events Manager. Сторінки народжуються в трьох генераторах, і
   один з них — tools/landing/build.py — складає <head> через f-рядок. Код
   пікселя рясніє фігурними дужками, і в f-рядку кожну довелося б подвоювати.
   Файл збоку цієї проблеми не має: у шаблонах лишається один тег <script src>.

   ЗГОДА (з 21.11.2026, контракт мережі «пиксель Meta + CAPI»). До цього дня
   піксель вантажився кожному відвідувачу без жодного питання, а політика
   cookie при цьому обіцяла «Cookie Banner», якого на сайті не було. Тепер:
     • вибір — cookie `ff_cookie_consent` ('all' | 'necessary') на
       `.fluent-fox.site`, тобто спільний для fluent-fox.site і
       lp.fluent-fox.site; копія в localStorage (cookie може не записатись);
     • до вибору 'all' — ні fbevents.js, ні жодного запиту до facebook;
     • дали згоду пізніше на тій самій сторінці — піксель піднімається
       в цю ж мить, перезавантаження не треба;
     • плашку малює цей же файл (обидві мови), тож шаблони не чіпались.
   Зразок — плашка мережі «Мій комп'ютер» (sites/main/index.html, mcaConsent).

   Google Analytics ця згода поки НЕ вмикає і не вимикає — він вантажиться
   як і раніше. Перевести його на Consent Mode — окреме рішення власника.

   ПОДІЮ Lead цей файл сам не шле: її шле js/lead.js після підтвердження від
   сервера, з eventID із ffPixel.meta(). Той самий id сервер кладе в
   Conversions API — так Meta склеює браузерну й серверну подію в одну. */
(function () {
  'use strict';

  var PIXEL_ID = '931791603129774';
  var KEY = 'ff_cookie_consent';
  var FBCLID_KEY = 'ff-fbclid';
  var FBCLID_TTL = 90 * 24 * 60 * 60 * 1000;
  var MAX_AGE = 180 * 24 * 60 * 60; // пів року — далі питаємо знову
  var host = location.hostname;
  var DOMAIN = /(^|\.)fluent-fox\.site$/.test(host) ? '.fluent-fox.site' : '';

  var choice = null;
  var loaded = false;

  function readCookie() {
    var m = document.cookie.match(/(?:^|;\s*)ff_cookie_consent=(all|necessary)(?:;|$)/);
    return m ? m[1] : null;
  }

  function writeCookie(v) {
    try {
      document.cookie = KEY + '=' + v + '; Path=/; Max-Age=' + MAX_AGE + '; SameSite=Lax'
        + (DOMAIN ? '; Domain=' + DOMAIN : '')
        + (location.protocol === 'https:' ? '; Secure' : '');
    } catch (e) { /* cookie вимкнені — лишається localStorage */ }
  }

  choice = readCookie();
  if (!choice) {
    try {
      var l = localStorage.getItem(KEY);
      if (l === 'all' || l === 'necessary') { choice = l; writeCookie(l); }
    } catch (e) { /* приватне вікно */ }
  }

  function loadPixel() {
    if (loaded) return;
    loaded = true;
    /* eslint-disable */
    !function(f,b,e,v,n,t,s)
    {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)};
    if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
    n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];
    s.parentNode.insertBefore(t,s)}(window, document,'script',
    'https://connect.facebook.net/en_US/fbevents.js');
    /* eslint-enable */
    window.fbq('init', PIXEL_ID);
    window.fbq('track', 'PageView');
  }

  function setChoice(v) {
    if (v !== 'all' && v !== 'necessary') return;
    choice = v;
    writeCookie(v);
    try { localStorage.setItem(KEY, v); } catch (e) { /* приватне вікно */ }
    if (v === 'all') loadPixel();
  }

  if (choice === 'all') loadPixel();

  /* ── fbclid: перше торкання ────────────────────────────────────────────
     Meta дописує його до адреси переходу з реклами. Зберігаємо так само, як
     js/track.js зберігає gclid: localStorage + sessionStorage, 90 днів.
     Внутрішній перехід (адреса без fbclid) нічого не перезаписує; новий
     fbclid — це новий клік, і він замінює старий. Час першого торкання
     потрібен для fbc: 'fb.1.<ms>.<fbclid>'. */
  function readBox(key, ttl) {
    var stores = [];
    try { stores.push(localStorage); } catch (e) { /* приватне вікно */ }
    try { stores.push(sessionStorage); } catch (e) { /* і тут */ }
    for (var i = 0; i < stores.length; i++) {
      try {
        var box = JSON.parse(stores[i].getItem(key) || 'null');
        if (box && box.id && box.at && Date.now() - box.at <= ttl) return box;
      } catch (e) { /* зіпсований запис */ }
    }
    return null;
  }

  function writeBox(key, box) {
    var raw = JSON.stringify(box);
    try { localStorage.setItem(key, raw); } catch (e) { /* приватне вікно */ }
    try { sessionStorage.setItem(key, raw); } catch (e) { /* і тут */ }
  }

  (function captureFbclid() {
    var id = '';
    try { id = (new URLSearchParams(location.search).get('fbclid') || '').trim(); } catch (e) { return; }
    if (!id || id.length > 500) return;
    var old = readBox(FBCLID_KEY, FBCLID_TTL);
    if (old && old.id === id) return;   // та сама адреса ще раз — час не чіпаємо
    writeBox(FBCLID_KEY, { id: id, at: Date.now() });
  })();

  function cookie(name) {
    var m = document.cookie.match(new RegExp('(?:^|;\\s*)' + name + '=([^;]*)'));
    if (!m) return '';
    try { return decodeURIComponent(m[1]); } catch (e) { return m[1]; }
  }

  function uuid() {
    try { if (window.crypto && crypto.randomUUID) return crypto.randomUUID(); } catch (e) { /* старий браузер */ }
    var s = '';
    for (var i = 0; i < 32; i++) s += Math.floor(Math.random() * 16).toString(16);
    return s.slice(0, 8) + '-' + s.slice(8, 12) + '-4' + s.slice(13, 16) + '-a' + s.slice(17, 20) + '-' + s.slice(20);
  }

  /* Об'єкт для тіла заявки. Новий event_id на кожну спробу відправки:
     він же піде в fbq('track','Lead',…,{eventID}) — див. js/lead.js. */
  function meta() {
    var click = readBox(FBCLID_KEY, FBCLID_TTL);
    var fbclid = click ? click.id : '';
    var fbc = cookie('_fbc');
    if (!fbc && fbclid) fbc = 'fb.1.' + click.at + '.' + fbclid;
    var out = {
      event_id: uuid(),
      consent: choice === 'all' ? 'all' : (choice || ''),
      url: location.href.split('#')[0]
    };
    var fbp = cookie('_fbp');
    if (fbp) out.fbp = fbp;
    if (fbc) out.fbc = fbc;
    if (fbclid) out.fbclid = fbclid;
    return out;
  }

  /* Lead — тільки якщо піксель справді піднятий, тобто є згода. */
  function trackLead(eventId, contentName) {
    if (!loaded || typeof window.fbq !== 'function') return false;
    try {
      window.fbq('track', 'Lead', { content_name: contentName || 'trial_lesson' }, { eventID: eventId });
      return true;
    } catch (e) { return false; }
  }

  /* ── Плашка згоди ──────────────────────────────────────────────────────
     Стилі — через CSSOM (el.style), а не атрибутом style: так їх пропускає
     будь-яка CSP, і в зібраному Tailwind не треба шукати потрібних класів. */
  var TEXT = {
    uk: {
      text: 'Ми використовуємо обов’язкові cookie для роботи сайту, а з вашої згоди — рекламні (піксель Meta), щоб міряти рекламу. ',
      more: 'Політика cookie',
      accept: 'Прийняти всі',
      decline: 'Лише обов’язкові',
      label: 'Згода на cookie'
    },
    ru: {
      text: 'Мы используем обязательные cookie для работы сайта, а с вашего согласия — рекламные (пиксель Meta), чтобы измерять рекламу. ',
      more: 'Политика cookie',
      accept: 'Принять все',
      decline: 'Только обязательные',
      label: 'Согласие на cookie'
    }
  };

  var banner = null;

  function css(el, rules) {
    for (var k in rules) if (Object.prototype.hasOwnProperty.call(rules, k)) el.style[k] = rules[k];
  }

  function button(label, primary, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    css(b, {
      font: 'inherit', fontWeight: '700', fontSize: '14px', cursor: 'pointer',
      borderRadius: '12px', padding: '10px 16px', lineHeight: '1.2',
      border: primary ? '1px solid #FF6B35' : '1px solid #D1D5DB',
      background: primary ? '#FF6B35' : '#FFFFFF',
      color: primary ? '#FFFFFF' : '#1F2937'
    });
    b.addEventListener('click', onClick);
    return b;
  }

  function hideBanner() {
    if (!banner) return;
    var b = banner;
    banner = null;
    css(b, { transform: 'translateY(110%)', opacity: '0' });
    setTimeout(function () { if (b.parentNode) b.parentNode.removeChild(b); }, 320);
  }

  function showBanner() {
    if (banner || !document.body) return;
    var lang = (document.documentElement.lang || 'uk').slice(0, 2) === 'ru' ? 'ru' : 'uk';
    var t = TEXT[lang];
    banner = document.createElement('div');
    banner.setAttribute('role', 'region');
    banner.setAttribute('aria-label', t.label);
    banner.setAttribute('data-cookie-banner', '');
    css(banner, {
      position: 'fixed', left: '12px', right: '12px', bottom: '12px', zIndex: '2147483000',
      maxWidth: '720px', margin: '0 auto', boxSizing: 'border-box',
      background: '#FFFFFF', color: '#1F2937', border: '1px solid #E5E7EB',
      borderRadius: '16px', boxShadow: '0 10px 30px rgba(17,24,39,.18)',
      padding: '16px', fontSize: '14px', lineHeight: '1.5',
      transition: 'transform .3s ease, opacity .3s ease',
      transform: 'translateY(110%)', opacity: '0'
    });
    var p = document.createElement('p');
    css(p, { margin: '0 0 12px' });
    p.appendChild(document.createTextNode(t.text));
    var a = document.createElement('a');
    /* На lp.fluent-fox.site своєї /cookies немає — ведемо на основний сайт. */
    a.href = DOMAIN ? 'https://fluent-fox.site/cookies.html' : '/cookies.html';
    a.textContent = t.more;
    css(a, { color: '#E8551F', textDecoration: 'underline' });
    p.appendChild(a);
    var row = document.createElement('div');
    css(row, { display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'flex-end' });
    row.appendChild(button(t.decline, false, function () { setChoice('necessary'); hideBanner(); }));
    row.appendChild(button(t.accept, true, function () { setChoice('all'); hideBanner(); }));
    banner.appendChild(p);
    banner.appendChild(row);
    document.body.appendChild(banner);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () { if (banner) css(banner, { transform: 'none', opacity: '1' }); });
    });
  }

  function onReady() {
    if (choice !== 'all' && choice !== 'necessary') setTimeout(showBanner, 800);
    /* Кнопка «Змінити налаштування cookie» на /cookies. */
    var els = document.querySelectorAll('[data-cookie-settings]');
    for (var i = 0; i < els.length; i++) {
      els[i].addEventListener('click', function (e) { e.preventDefault(); showBanner(); });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', onReady);
  else onReady();

  window.ffConsentValue = function () { return choice; };
  window.ffConsent = setChoice;
  window.ffPixel = {
    meta: meta,
    trackLead: trackLead,
    loaded: function () { return loaded; },
    showBanner: showBanner
  };
})();
