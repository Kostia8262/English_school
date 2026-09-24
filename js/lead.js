/* Форма запису на пробний урок.

   Жила в js/home.js, бо форма була тільки на головній. Тепер той самий блок
   контактів стоїть і на посадкових сторінках, тож логіка переїхала сюди —
   один файл на обидві. js/home.js цього коду більше не тримає: він викликає
   window.ffLead.wire() для кожної форми, яку знайде.

   Порядок підключення: цей файл іде перед home.js (обидва defer, тому
   виконуються в порядку документа). На посадкових сторінках home.js немає
   зовсім — там форму заводить сам цей файл на DOMContentLoaded.

   Головне правило, заради якого форма взагалі переїхала на свій домен:
   успіх показуємо ТІЛЬКИ за явним підтвердженням від сервера. Раніше тут
   стояв прямий адрес Google Apps Script із mode:'no-cors' — відповідь була
   непрозорою, і сторінка казала «Заявку прийнято» навіть тоді, коли сервер
   відмовив. Не повертати таку поведінку. */
(function () {
  'use strict';

  var LEAD_URL = '/api/lead.php';

  var INPUT_BAD = ['border-red-400', 'bg-red-50'];
  var INPUT_OK = ['border-gray-200', 'bg-gray-50'];

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
    if (!form || form.dataset.leadWired === '1') return;
    form.dataset.leadWired = '1';

    var box = form.parentElement;
    var success = one('[data-form-success]', box);
    var failed = one('[data-form-failed]', form);
    var submit = form.querySelector('button[type="submit"]');

    all('[data-form-input]', form).forEach(function (input) {
      input.addEventListener('input', function () {
        markField(form, input.dataset.formInput, false);
      });
    });

    /* Перевірку браузера вимикаємо звідси, а не в розмітці: тут вона зайва —
       нижче своя, з підсвіткою полів. Але якщо цей скрипт не виконався,
       форма лишається зі своїм `required` і браузер перевірить сам. */
    form.noValidate = true;

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
      /* Тільки якщо поле справді є. Запасне 'group' означало не «обрали
         групу», а «поля немає» — і йшло в CRM як вибір батьків. */
      if (format) body.append('format', format.value);
      body.append('lang', document.documentElement.lang || 'uk');
      body.append('timestamp', new Date().toLocaleString('uk-UA'));
      /* Сторінка, з якої прийшла заявка. На головній це завжди була вона
         сама, а тепер форма стоїть на п'ятнадцяти посадкових, і без цього
         рядка в CRM не видно, яка з них привела людину. */
      body.append('page', location.pathname + location.search);

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

  /* Повертає картку у вихідний стан: потрібно модалці на головній, яка
     відкривається вдруге вже після успішної відправки. */
  function resetForms() {
    all('[data-form-success]').forEach(function (el) { show(el, false); });
    all('[data-form-body]').forEach(function (el) { show(el, true); });
  }

  /* ── Модальне вікно з формою ────────────────────────────────────────── */

  /* Переїхало сюди з js/home.js разом із формою: модалку відкриває кнопка
     «Пробний урок» у шапці, а шапка однакова на головній і на посадкових.
     Меню на головній закриває сама головна — див. window.ffHome. */
  function setModal(open) {
    all('[data-modal-panel]').forEach(function (el) { show(el, open); });
    // Прокрутка сторінки під відкритою модалкою збиває позицію на мобільних:
    // закривши вікно, відвідувач опинявся не там, звідки його відкрив.
    document.body.style.overflow = open ? 'hidden' : '';
  }

  function onClick(e) {
    var el = e.target.closest ? e.target.closest('[data-modal="open"]') : null;
    if (el) {
      /* preventDefault, бо це посилання на /probnyi-urok: зі скриптом
         відкривається модалка, без нього людина просто йде на сторінку
         пробного уроку. Мертвих кнопок на сайті не лишаємо. */
      e.preventDefault();
      if (window.ffHome && window.ffHome.closeMenu) window.ffHome.closeMenu();
      setModal(true);
      return;
    }
    el = e.target.closest ? e.target.closest('[data-modal="close"]') : null;
    if (el) {
      e.preventDefault();
      setModal(false);
      if (el.hasAttribute('data-form-reset')) resetForms();
      return;
    }
    if (e.target.hasAttribute && e.target.hasAttribute('data-modal-backdrop')) {
      setModal(false);
    }
  }

  function wireAll() {
    all('[data-lead-form]').forEach(wireForm);
  }

  window.ffLead = {
    wire: wireForm, wireAll: wireAll, reset: resetForms, modal: setModal
  };

  document.addEventListener('click', onClick);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') setModal(false);
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireAll);
  } else {
    wireAll();
  }
})();
