/* Анімації внутрішніх сторінок FluentFox: посадкові, статті й лістинг блогу.

   Що тут, а що в CSS. Поява героя при завантаженні — чистий CSS
   (`.ffm-hero-text`, `.ffm-hero-art` у src/tailwind.css): скрипт підключено з
   `defer`, і якби героя ховав він, перший кадр показав би текст, а другий —
   порожнечу. Скрипт бере на себе те, що залежить від прокрутки: поява блоків,
   лічильники, тінь шапки, смуга прочитаного.

   Три правила, які тримають анімацію нешкідливою:
   1. Ховаємо (opacity) лише те, що на старті нижче екрана. Що вже видно —
      лишається як є: ні миготіння, ні затримки LCP.
   2. Без IntersectionObserver або при «зменшити рух» скрипт нічого не ховає.
      Сторінка без скрипта — це та сама сторінка, просто нерухома.
   3. Після появи класи анімації знімаються: у карток і кнопок свої
      hover-переходи (`hover:-translate-y-1`), і наш `transition` їх би
      перебивав. */
(function () {
  'use strict';

  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce || !('IntersectionObserver' in window)) return;

  var doc = document.documentElement;
  var mobile = window.matchMedia('(max-width: 767px)').matches;
  var STEP = mobile ? 0.06 : 0.08;      // крок «драбинки» між сусідами, с
  var MAX_DELAY = mobile ? 0.3 : 0.45;  // далі драбинка не росте — довгі списки не повзуть

  function $$(sel, root) { return [].slice.call((root || document).querySelectorAll(sel)); }
  function below(el) { return el.getBoundingClientRect().top > window.innerHeight - 8; }
  function inChrome(el) { return !!el.closest('header, footer, #leadModal, [role="dialog"], .ffm-hero-text, .ffm-hero-art'); }

  /* ── Поява на прокрутці ───────────────────────────────────────── */
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      var el = e.target;
      io.unobserve(el);
      el.classList.add('ffm-in');
      if (el.dataset.ffmCount) countUp(el);
      var d = parseFloat(el.style.getPropertyValue('--ffm-d')) || 0;
      // Прибираємо за собою, коли перехід скінчився: див. правило 3.
      setTimeout(function () {
        el.classList.remove('ffm', 'ffm-in', 'ffm--scale', 'ffm--left', 'ffm--pop');
        el.style.removeProperty('--ffm-d');
      }, (d + 0.9) * 1000);
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

  function reveal(el, kind, delay) {
    if (!el || el.classList.contains('ffm') || inChrome(el) || !below(el)) return;
    el.classList.add('ffm');
    if (kind) el.classList.add('ffm--' + kind);
    if (delay) el.style.setProperty('--ffm-d', Math.min(delay, MAX_DELAY).toFixed(2) + 's');
    io.observe(el);
  }

  // Драбинка: сусіди одного батька з'являються по черзі, а не всі разом.
  function stagger(list, kind) {
    var byParent = new Map();
    list.forEach(function (el) {
      var p = el.parentNode, i = byParent.get(p) || 0;
      byParent.set(p, i + 1);
      reveal(el, kind, i * STEP);
    });
  }

  function scan() {
    // Заголовки секцій: підпис-«пігулка», h2 і підзаголовок під ним.
    $$('main h2, section h2').forEach(function (h) {
      if (h.closest('a, details, [data-card-cat]')) return;
      var wrap = h.parentElement;
      if (wrap && /\btext-center\b/.test(wrap.className) && wrap.children.length <= 4) {
        stagger([].slice.call(wrap.children));
      } else {
        reveal(h);
      }
    });

    // Картки в сітках: про нас, вікові групи, контакти, лістинг блогу.
    stagger($$('main .grid > *, section .grid > *').filter(function (el) {
      return !el.closest('footer, form') && el.offsetHeight > 40;
    }), 'scale');

    // Кроки «Як це працює» на мобільному йдуть стовпчиком, а не сіткою.
    stagger($$('#about .md\\:hidden > .relative'), 'left');

    // Списки з галочками, пункти й кроки в тексті сторінки.
    stagger($$('main ul.flex-col > li, main ol.flex-col > li, .prose > ul > li, .prose > ol > li'), 'left');

    // Питання FAQ і питання-відповіді в статтях.
    stagger($$('#faq details, .prose details'));

    // Самостійні блоки тексту: таблиці, врізки, цитати, ілюстрації.
    $$('main table, .table-wrap, main blockquote, main figure, .course-link, .prose img').forEach(function (el) {
      if (el.closest('.table-wrap') && el.tagName === 'TABLE') return;
      reveal(el, el.tagName === 'FIGURE' || el.tagName === 'IMG' ? 'scale' : null);
    });

    // Помаранчевий банер наприкінці: вміст по черзі, кнопки з відблиском.
    $$('section.bg-gradient-to-br').forEach(function (s) {
      var box = s.querySelector('.relative');
      if (box) stagger([].slice.call(box.children));
      $$('.absolute[aria-hidden="true"]', s).forEach(function (b, i) {
        b.classList.add('ffm-float');
        if (i % 2) b.classList.add('ffm-float--slow');
      });
    });
  }

  /* ── Пунктир між кроками «прорисовується» ────────────────────── */
  // Стежимо за батьком, а не за лінією: IntersectionObserver враховує
  // clip-path, і повністю обрізана лінія для нього ніколи не «видна».
  var lineIo = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      lineIo.unobserve(e.target);
      $$('.ffm-draw', e.target).forEach(function (l) { l.classList.add('ffm-in'); });
    });
  }, { threshold: 0.3 });
  $$('#about .border-dashed.absolute').forEach(function (line) {
    if (!below(line)) return;
    line.classList.add('ffm-draw');
    lineIo.observe(line.parentElement);
  });

  /* ── Лічильники в смузі цифр ──────────────────────────────────── */
  function countUp(el) {
    var target = parseFloat(el.dataset.ffmCount), dec = +el.dataset.ffmDec || 0;
    var suffix = el.dataset.ffmSuffix || '', t0 = null, dur = 1400;
    function frame(ts) {
      if (t0 === null) t0 = ts;
      var p = Math.min((ts - t0) / dur, 1), e = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * e).toFixed(dec) + suffix;
      if (p < 1) requestAnimationFrame(frame); else el.textContent = el.dataset.ffmFinal;
    }
    requestAnimationFrame(frame);
  }
  $$('.bg-british .grid > div > div:first-child').forEach(function (el) {
    var m = /^\s*(\d+(?:[.,]\d+)?)(\D*)$/.exec(el.textContent);
    if (!m) return;
    var num = m[1].replace(',', '.');
    el.dataset.ffmFinal = el.textContent;
    el.dataset.ffmCount = num;
    el.dataset.ffmDec = (num.split('.')[1] || '').length;
    el.dataset.ffmSuffix = m[2];
    el.style.fontVariantNumeric = 'tabular-nums';
    // Справжнє число лишається в розмітці для краулера; нуль ставимо тільки
    // тому, що зараз піде анімація.
    el.textContent = (0).toFixed(+el.dataset.ffmDec) + m[2];
    io.observe(el);
  });

  /* ── Відблиск на головних кнопках ─────────────────────────────── */
  $$('main a.bg-fox-500, .ffm-hero-text a.bg-fox-500, section.bg-gradient-to-br a.bg-white').forEach(function (a) {
    a.classList.add('ffm-shine');
    if (a.classList.contains('bg-white')) a.classList.add('ffm-shine--warm');
  });

  /* ── Картки піднімаються під курсором ─────────────────────────── */
  $$('main .grid > *').forEach(function (el) {
    if (/rounded-(2xl|3xl|4xl)/.test(el.className) && !/hover:-?translate|card-lift/.test(el.className)) {
      el.classList.add('ffm-card');
    }
  });

  /* ── FAQ: відповідь розгортається плавно ──────────────────────── */
  $$('#faq details, .prose details').forEach(function (d) { d.classList.add('ffm-faq'); });

  /* ── Тінь шапки після прокрутки ───────────────────────────────── */
  var header = document.querySelector('body > header, header.sticky, header.fixed');
  if (header) {
    header.classList.add('ffm-hdr');
    var onScroll = function () { header.classList.toggle('ffm-scrolled', window.scrollY > 12); };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ── Смуга прочитаного у статті ───────────────────────────────── */
  var prose = document.querySelector('.prose');
  if (prose) {
    var bar = document.createElement('div');
    bar.className = 'ffm-progress';
    bar.setAttribute('aria-hidden', 'true');
    document.body.appendChild(bar);
    var ticking = false;
    var update = function () {
      ticking = false;
      var r = prose.getBoundingClientRect();
      var total = r.height - window.innerHeight * 0.6;
      var p = total > 0 ? Math.min(Math.max(-r.top / total, 0), 1) : 0;
      bar.style.transform = 'scaleX(' + p.toFixed(4) + ')';
    };
    window.addEventListener('scroll', function () {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }, { passive: true });
    update();
  }

  /* ── Лістинг блогу: перемикання категорії ─────────────────────── */
  $$('[data-cat]').forEach(function (tab) {
    tab.addEventListener('click', function () {
      setTimeout(function () {
        var i = 0;
        $$('[data-card-cat]').forEach(function (c) {
          if (c.hidden) return;
          c.classList.remove('ffm-flash');
          void c.offsetWidth;                       // перезапуск анімації
          c.style.animationDelay = Math.min(i++ * 0.05, 0.4) + 's';
          c.classList.add('ffm-flash');
        });
      }, 0);
    });
  });

  scan();
  doc.classList.add('ffm-ready');
})();
