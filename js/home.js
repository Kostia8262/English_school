/* Інтерактив головної сторінки.

   Раніше все це робив Alpine прямо в розмітці: `@click`, `x-show`, `:class`.
   Разом із поведінкою він же підставляв і текст — через `x-text` та цикли
   `x-for`. Через це в HTML тексту не було взагалі, і сторінка, яка бореться за
   найчастотніші запити, приходила до пошуковика майже порожньою.

   Тепер текст лежить у розмітці статично (складає tools/home/build.py), а сюди
   переїхала сама поведінка. Прив'язка — через `data-*`-атрибути, які проставляє
   складальник. Мова перемикається окремим скриптом js/lang.js, тим самим, що на
   посадкових сторінках.

   Порядок підключення важливий: lang.js іде першим і встигає підставити
   російські рядки до того, як тут зчитуються класи. */
(function () {
  'use strict';

  function all(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function one(sel, root) {
    return (root || document).querySelector(sel);
  }

  /* Показ і приховування — через атрибут hidden, а не через клас. У стилях
     сторінки на нього є правило з !important: у більшості цих вузлів у класах
     стоїть flex або grid, і без нього display:none не спрацював би. */
  function show(el, on) {
    if (!el) return;
    if (on) el.removeAttribute('hidden');
    else el.setAttribute('hidden', '');
  }

  function swapClasses(el, on, whenOn, whenOff) {
    if (!el) return;
    (on ? whenOff : whenOn).forEach(function (c) { el.classList.remove(c); });
    (on ? whenOn : whenOff).forEach(function (c) { el.classList.add(c); });
  }

  /* ── Шапка: тінь і фон після прокрутки ──────────────────────────────── */

  var header = one('[data-header]');
  var menuOpen = false;

  var HEADER_ON = ['shadow-md', 'bg-white/95', 'backdrop-blur-sm'];
  var HEADER_OFF = ['bg-transparent'];

  function paintHeader() {
    swapClasses(header, window.scrollY > 60 || menuOpen, HEADER_ON, HEADER_OFF);
  }

  /* ── Мобільне меню ──────────────────────────────────────────────────── */

  function setMenu(open) {
    menuOpen = open;
    all('[data-menu-when="open"]').forEach(function (el) { show(el, open); });
    all('[data-menu-when="closed"]').forEach(function (el) { show(el, !open); });
    paintHeader();
  }

  /* ── Модальне вікно із формою ───────────────────────────────────────── */

  function setModal(open) {
    all('[data-modal-panel]').forEach(function (el) { show(el, open); });
    // Прокрутка сторінки під відкритою модалкою збиває позицію на мобільних:
    // закривши вікно, відвідувач опинявся не там, звідки його відкрив.
    document.body.style.overflow = open ? 'hidden' : '';
  }

  /* ── Вкладки програми ───────────────────────────────────────────────── */

  var TAB_ON = ['bg-fox-500', 'text-white', 'shadow-fox-sm'];
  var TAB_OFF = ['text-gray-500', 'hover:text-gray-800', 'hover:bg-gray-50'];

  function setProgTab(key) {
    all('[data-prog-tab-btn]').forEach(function (btn) {
      swapClasses(btn, btn.dataset.progTabBtn === key, TAB_ON, TAB_OFF);
    });
    all('[data-prog-panel]').forEach(function (panel) {
      show(panel, panel.dataset.progPanel === key);
    });
    // Вкладку відкрито заново — модулі згортаємо, щоб довга сторінка не
    // стрибала під курсором. На десктопі лишаємо розгорнутим перший.
    currentModule = window.innerWidth < 768 ? null : 0;
    setModule(currentModule);
  }

  /* ── Акордеон модулів усередині вкладки ─────────────────────────────── */

  function setModule(index) {
    var eq = function (el, name) {
      return index !== null && Number(el.dataset[name]) === index;
    };
    all('[data-mod-card]').forEach(function (el) {
      swapClasses(el, eq(el, 'modCard'),
                  ['border-fox-300', 'shadow-fox-sm'],
                  ['border-gray-200', 'hover:border-gray-300']);
    });
    all('[data-mod-head]').forEach(function (el) {
      swapClasses(el, eq(el, 'modHead'), ['bg-fox-50'], ['hover:bg-gray-50']);
    });
    all('[data-mod-badge]').forEach(function (el) {
      swapClasses(el, eq(el, 'modBadge'),
                  ['bg-fox-500', 'shadow-fox-sm'], ['bg-gray-100']);
    });
    all('[data-mod-num]').forEach(function (el) {
      swapClasses(el, eq(el, 'modNum'), ['text-white'], ['text-gray-500']);
    });
    all('[data-mod-title]').forEach(function (el) {
      swapClasses(el, eq(el, 'modTitle'), ['text-gray-900'], ['text-gray-700']);
    });
    all('[data-mod-chevron]').forEach(function (el) {
      swapClasses(el, eq(el, 'modChevron'),
                  ['rotate-180', 'text-fox-500'], ['text-gray-400']);
    });
    all('[data-mod-panel]').forEach(function (el) {
      show(el, eq(el, 'modPanel'));
    });
  }

  /* ── Часті питання ──────────────────────────────────────────────────── */

  var openFaq = null;

  function setFaq(index) {
    openFaq = index;
    all('[data-faq-panel]').forEach(function (el) {
      show(el, index !== null && Number(el.dataset.faqPanel) === index);
    });
    all('[data-faq-icon]').forEach(function (el) {
      el.classList.toggle('rotate-45',
                          index !== null && Number(el.dataset.faqIcon) === index);
    });
  }

  /* ── Відгуки: посторінково по три ───────────────────────────────────── */

  var REVIEWS_PER_PAGE = 3;

  var reviewPage = 0;
  var reviewCards = all('[data-review-card]');
  var reviewGrid = one('[data-review-grid]');
  var reviewPages = Math.ceil(reviewCards.length / REVIEWS_PER_PAGE);

  function paintReviewCards(page) {
    reviewCards.forEach(function (card) {
      var i = Number(card.dataset.reviewCard);
      show(card, i >= page * REVIEWS_PER_PAGE
                 && i < page * REVIEWS_PER_PAGE + REVIEWS_PER_PAGE);
    });
  }

  /* Висота сітки фіксується по найвищій сторінці.

     Відгуки різної довжини, а сторінка показує рівно три з них, тож без
     цього блок підстрибував угору-вниз на кожному перемиканні: сторінка з
     довгим відгуком вища за сторінку з короткими, і разом із сіткою
     смикався весь низ екрана.

     Міряємо, а не задаємо число руками: тексти відгуків живуть у
     trans.json і змінюються, а висота залежить ще й від ширини вікна та
     від того, чи вже підвантажився шрифт. */
  function lockReviewHeight() {
    if (!reviewGrid || !reviewPages) return;
    reviewGrid.style.minHeight = '';
    // offsetParent === null означає, що сітка схована зовсім: на телефоні
    // замість неї працює свайп-слайдер, і міряти там нічого.
    if (!reviewGrid.offsetParent) return;
    var tallest = 0;
    for (var p = 0; p < reviewPages; p++) {
      paintReviewCards(p);
      tallest = Math.max(tallest, reviewGrid.offsetHeight);
    }
    paintReviewCards(reviewPage);
    reviewGrid.style.minHeight = tallest + 'px';
  }

  function setReviewPage(page) {
    reviewPage = Math.max(0, Math.min(page, reviewPages - 1));
    paintReviewCards(reviewPage);
    all('[data-review-dot]').forEach(function (dot) {
      swapClasses(dot, Number(dot.dataset.reviewDot) === reviewPage,
                  ['bg-fox-500', 'w-5'], ['bg-gray-200', 'w-2']);
    });
    var prev = one('[data-review="prev"]');
    var next = one('[data-review="next"]');
    if (prev) prev.disabled = reviewPage === 0;
    if (next) next.disabled = reviewPage >= reviewPages - 1;
  }

  /* ── Паралакс декоративних деталей у герої ──────────────────────────── */

  function wireParallax() {
    var root = one('[data-parallax]');
    if (!root) return;
    var items = all('[data-parallax-xy]', root).map(function (el) {
      var xy = el.dataset.parallaxXy.split(',');
      return { el: el, x: Number(xy[0]), y: Number(xy[1]) };
    });
    if (!items.length) return;
    // Ефект суто декоративний: тим, хто просив прибрати анімації, він не
    // потрібен, а на дотику мишки немає взагалі.
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    window.addEventListener('mousemove', function (e) {
      var px = (e.clientX / window.innerWidth) - 0.5;
      var py = (e.clientY / window.innerHeight) - 0.5;
      items.forEach(function (it) {
        it.el.style.transform =
          'translate(' + (px * it.x) + 'px, ' + (py * it.y) + 'px)';
      });
    }, { passive: true });
  }

  /* ── Форма запису ───────────────────────────────────────────────────── */

  /* Свій же домен. Раніше тут був прямий адрес Google Apps Script — і
     заявка жила рядком у таблиці, без статусу, без «передзвонили»
     і без будь-якого нагадування. Тепер заявка йде в api/lead.php, а той
     розкладає її в CRM «Мій комп'ютер» і дублює в ту саму таблицю. */
  var LEAD_URL = '/api/lead.php';

  var INPUT_BAD = ['border-red-400', 'bg-red-50'];
  var INPUT_OK = ['border-gray-200', 'bg-gray-50'];

  function markField(form, field, bad) {
    swapClasses(one('[data-form-input="' + field + '"]', form), bad,
                INPUT_BAD, INPUT_OK);
    show(one('[data-form-error-for="' + field + '"]', form), bad);
  }

  function normalizePhone(raw) {
    var d = String(raw).replace(/\D/g, '');
    if (d.length === 12 && d.indexOf('380') === 0) d = d.slice(3);
    else if (d.length === 10 && d.charAt(0) === '0') d = d.slice(1);
    return d;
  }

  function wireForm(form) {
    var box = form.parentElement;
    var success = one('[data-form-success]', box);
    var failed = one('[data-form-failed]', form);
    var submit = form.querySelector('button[type="submit"]');

    all('[data-form-input]', form).forEach(function (input) {
      input.addEventListener('input', function () {
        markField(form, input.dataset.formInput, false);
      });
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();

      var name = form.querySelector('[name="name"]');
      var phone = form.querySelector('[name="phone"]');
      var age = form.querySelector('[name="childAge"]');
      var format = form.querySelector('[name="format"]');

      var nameOk = name && name.value.trim().length >= 2;
      var phoneOk = phone && normalizePhone(phone.value).length === 9;
      markField(form, 'name', !nameOk);
      markField(form, 'phone', !phoneOk);
      if (!nameOk || !phoneOk) return;

      show(failed, false);
      if (submit) submit.disabled = true;
      show(one('[data-submit-label]', form), false);
      show(one('[data-submit-spinner]', form), true);

      var body = new URLSearchParams();
      body.append('name', name.value.trim());
      body.append('phone', phone.value.trim());
      body.append('childAge', age ? age.value : '');
      body.append('format', format ? format.value : 'group');
      body.append('lang', document.documentElement.lang || 'uk');
      body.append('timestamp', new Date().toLocaleString('uk-UA'));

      /* Запит свій-до-свого: ні CORS, ні preflight, ні редиректів — відповідь
         читається завжди. Це й було головною причиною переїзду: раніше тут
         стояв mode: 'no-cors', відповідь була непрозорою, і форма показувала
         «Заявку прийнято» навіть тоді, коли сервер відмовив. */
      fetch(LEAD_URL, { method: 'POST', body: body })
        .then(function (res) {
          return res.text().then(function (text) {
            var data = null;
            try { data = JSON.parse(text); } catch (e) { /* розберемо нижче */ }
            /* Успіх — тільки за явним підтвердженням. Двісті від
               сторінки хостингу чи від невиконаного PHP не має
               читатись як «заявка прийнята». */
            if (!res.ok || !data || data.result !== 'success') {
              throw new Error((data && data.message) || ('HTTP ' + res.status + ' ' + text.slice(0, 160)));
            }
            return data;
          });
        })
        .then(function () {
          show(form, false);
          show(success, true);
          if (typeof gtag !== 'undefined') {
            gtag('event', 'generate_lead',
                 { event_category: 'form', event_label: 'trial_lesson' });
          }
          form.reset();
        })
        .catch(function (err) {
          show(failed, true);
          if (window.console) console.error('[lead] заявка не пройшла:', err && err.message);
        })
        .then(function () {
          if (submit) submit.disabled = false;
          show(one('[data-submit-label]', form), true);
          show(one('[data-submit-spinner]', form), false);
        });
    });
  }

  function resetForms() {
    all('[data-form-success]').forEach(function (el) { show(el, false); });
    all('[data-form-body]').forEach(function (el) { show(el, true); });
  }

  /* ── Один обробник кліку на всю сторінку ────────────────────────────── */

  function onClick(e) {
    var el;

    if ((el = e.target.closest('[data-modal="open"]'))) {
      e.preventDefault();
      setMenu(false);
      setModal(true);
      return;
    }
    if ((el = e.target.closest('[data-modal="close"]'))) {
      e.preventDefault();
      setModal(false);
      if (el.hasAttribute('data-form-reset')) resetForms();
      return;
    }
    if (e.target.hasAttribute && e.target.hasAttribute('data-modal-backdrop')) {
      setModal(false);
      return;
    }
    if ((el = e.target.closest('[data-menu="toggle"]'))) {
      setMenu(!menuOpen);
      return;
    }
    if (e.target.closest('[data-menu="close"]')) {
      setMenu(false);
      return;
    }
    if ((el = e.target.closest('[data-prog-tab-btn]'))) {
      setProgTab(el.dataset.progTabBtn);
      return;
    }
    if ((el = e.target.closest('[data-mod-toggle]'))) {
      var mod = Number(el.dataset.modToggle);
      currentModule = currentModule === mod ? null : mod;
      setModule(currentModule);
      return;
    }
    if ((el = e.target.closest('[data-faq-toggle]'))) {
      var faq = Number(el.dataset.faqToggle);
      setFaq(openFaq === faq ? null : faq);
      return;
    }
    if ((el = e.target.closest('[data-review-page]'))) {
      setReviewPage(Number(el.dataset.reviewPage));
      return;
    }
    if ((el = e.target.closest('[data-review]'))) {
      setReviewPage(reviewPage + (el.dataset.review === 'next' ? 1 : -1));
    }
  }

  var currentModule = 0;

  function init() {
    paintHeader();
    window.addEventListener('scroll', paintHeader, { passive: true });
    document.addEventListener('click', onClick);
    window.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') setModal(false);
    });

    currentModule = window.innerWidth < 768 ? null : 0;
    setModule(currentModule);
    setReviewPage(0);
    lockReviewHeight();
    // Шрифт локальний, але приїжджає окремим файлом: до нього рядки вужчі, і
    // заміряна висота була б меншою за справжню.
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(lockReviewHeight);
    }
    var reviewResize;
    window.addEventListener('resize', function () {
      clearTimeout(reviewResize);
      reviewResize = setTimeout(lockReviewHeight, 150);
    });
    wireParallax();
    all('[data-lead-form]').forEach(wireForm);
  }
  /* Автогортання відгуків прибрано свідомо. В Alpine воно стояло під умовою
     `innerWidth < 768`, а посторінкова сітка на цій ширині схована зовсім —
     гортався блок, якого ніхто не бачив. Заводити його на десктопі означало б
     додати нову поведінку замість того, щоб перенести наявну. */

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
