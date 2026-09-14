/* Підписка на листи у підвалі.

   Форма [data-subscribe] надсилає адресу в панель розсилки мережі
   (data-endpoint, https://smm.mycomputer.education/s/subscribe). Панель одразу
   додає людину в базу «Подписка с сайта» й надсилає вітальний лист (тим, хто
   раніше відписувався, — лист із кнопкою підтвердження). Той самий приймач, що
   на сайтах «Мій комп'ютер»; тут — своя копія скрипта під Tailwind.

   Оформлення не в скрипті: Tailwind збирає лише класи з HTML, тому скрипт
   ставить data-state="ok|error" на [data-subscribe-status] і aria-invalid на
   поле, а кольори задають варіанти data-[state=…] / aria-[invalid=true] у
   розмітці. data-consent — код версії тексту згоди біля форми; змінили текст
   згоди — змінюйте код.

   «Успіх» показуємо лише на справжню відповідь панелі: форма заявки тут уже
   одного разу казала «Заявку прийнято», коли запит відхиляли (no-cors). */
(function () {
  var TEXT = {
    uk: {
      accepted: 'Дякуємо! Перевірте пошту — ми надіслали вам лист.',
      consent_missing: 'Оновіть сторінку й спробуйте ще раз.',
      invalid_email: 'Схоже, в адресі помилка. Перевірте, будь ласка.',
      empty: 'Впишіть адресу пошти.',
      typo: 'Можливо, ви мали на увазі {s}?',
      fix: 'Виправити',
      too_many: 'Забагато спроб. Спробуйте за годину.',
      unavailable: 'Підписка тимчасово не працює. Спробуйте пізніше.',
      network: 'Не вдалося з\'єднатися. Перевірте інтернет і спробуйте ще раз.',
      sending: 'Надсилаємо…',
    },
    ru: {
      accepted: 'Спасибо! Проверьте почту — мы отправили вам письмо.',
      consent_missing: 'Обновите страницу и попробуйте ещё раз.',
      invalid_email: 'Похоже, в адресе ошибка. Проверьте, пожалуйста.',
      empty: 'Впишите адрес почты.',
      typo: 'Возможно, вы имели в виду {s}?',
      fix: 'Исправить',
      too_many: 'Слишком много попыток. Попробуйте через час.',
      unavailable: 'Подписка временно не работает. Попробуйте позже.',
      network: 'Не удалось соединиться. Проверьте интернет и попробуйте ещё раз.',
      sending: 'Отправляем…',
    },
  };

  // Мова — та, якою показана сторінка: .ru.html мають lang="ru" у розмітці,
  // js/lang.js перемикає <html lang> для ?lang=ru.
  function lang() {
    return document.documentElement.lang === 'ru' ? 'ru' : 'uk';
  }

  function t(key) { return TEXT[lang()][key] || TEXT[lang()].unavailable; }

  function setup(form) {
    var input = form.querySelector('input[name="email"]');
    var trap = form.querySelector('input[name="website"]');
    var button = form.querySelector('button[type="submit"]');
    var status = form.querySelector('[data-subscribe-status]');
    var busy = false;

    function show(state, text) {
      if (state) status.setAttribute('data-state', state);
      else status.removeAttribute('data-state');
      status.textContent = text || '';
    }

    function invalid(on) {
      if (on) input.setAttribute('aria-invalid', 'true');
      else input.removeAttribute('aria-invalid');
    }

    input.addEventListener('input', function () {
      invalid(false);
      if (status.getAttribute('data-state') === 'error') show('', '');
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (busy) return;
      var email = input.value.trim();
      if (!email) { invalid(true); show('error', t('empty')); input.focus(); return; }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) { invalid(true); show('error', t('invalid_email')); input.focus(); return; }

      busy = true;
      button.disabled = true;
      var label = button.textContent;
      button.textContent = t('sending');
      show('', '');

      var body = new URLSearchParams({
        email: email,
        school: form.dataset.school || '',
        page: location.href.split('#')[0],
        website: trap ? trap.value : '',
        consent_version: (form.dataset.consent || 'footer') + '-' + lang(),
        lang: lang(),
      });

      fetch(form.dataset.endpoint, {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
        credentials: 'omit',
      })
        .then(function (res) {
          return res.json().catch(function () { return { ok: false, code: 'unavailable' }; });
        })
        .then(function (data) {
          if (data.ok) {
            show('ok', t('accepted'));
            input.value = '';
            try {
              if (typeof window.gtag === 'function') window.gtag('event', 'newsletter_subscribe');
            } catch (err) { /* аналітика не повинна ламати форму */ }
            return;
          }
          if (data.code === 'typo' && data.suggestion) {
            invalid(true);
            show('error', t('typo').replace('{s}', data.suggestion) + ' ');
            var fix = document.createElement('button');
            fix.type = 'button';
            fix.textContent = t('fix');
            fix.addEventListener('click', function () {
              input.value = data.suggestion;
              invalid(false);
              show('', '');
              input.focus();
            });
            status.appendChild(fix);
            return;
          }
          if (data.code === 'invalid_email') invalid(true);
          show('error', t(data.code));
        })
        .catch(function () {
          show('error', t('network'));
        })
        .then(function () {
          busy = false;
          button.disabled = false;
          button.textContent = label;
        });
    });
  }

  function run() {
    document.querySelectorAll('form[data-subscribe]').forEach(setup);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
})();
