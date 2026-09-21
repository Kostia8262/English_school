/* Кнопки оплати на /oplata.

   Скрипт лежить на всіх сторінках поруч із lang.js і subscribe.js, але робить
   щось тільки там, де є [data-pay]: окремий бандл на одну сторінку статичний
   сайт зібрати не вміє, а важить це кілька сотень байт.

   Що відбувається. Сума й призначення йдуть на свій же /api/pay.php, той
   створює рахунок на боці шлюзу (WayForPay або MonoPay) і повертає адресу
   його сторінки оплати. Далі — звичайний перехід за адресою. Ні віджета, ні
   iframe: секрет мерчанта в браузер не потрапляє взагалі, а CSP чіпати не
   довелось — перехід за адресою вона не обмежує.

   «Успіх» показуємо тільки на справжній pageUrl у відповіді. На цьому сайті
   вже був випадок, коли сторінка казала «Заявку прийнято» на запит, який
   сервер відхилив (opaque-відповідь no-cors), і коштувало це двох місяців
   мовчазно втрачених заявок. */
(function () {
  var form = document.querySelector('[data-pay]');
  if (!form) return;

  var TEXT = {
    uk: {
      amount: 'Введіть суму від 1 до 100 000 грн',
      network: 'Не вдалося зв’язатися з сервером. Перевірте інтернет і спробуйте ще раз.',
      wait: 'Зачекайте…',
    },
    ru: {
      amount: 'Введите сумму от 1 до 100 000 грн',
      network: 'Не удалось связаться с сервером. Проверьте интернет и попробуйте ещё раз.',
      wait: 'Подождите…',
    },
  };

  function lang() {
    return document.documentElement.lang === 'ru' ? 'ru' : 'uk';
  }

  var amountEl = form.querySelector('[data-pay-amount]');
  var purposeEl = form.querySelector('[data-pay-purpose]');
  var statusEl = form.querySelector('[data-pay-status]');
  var buttons = [].slice.call(form.querySelectorAll('[data-pay-provider]'));

  function setStatus(message, state) {
    if (!statusEl) return;
    statusEl.textContent = message || '';
    if (state) statusEl.setAttribute('data-state', state);
    else statusEl.removeAttribute('data-state');
  }

  function lock(on, pressed) {
    buttons.forEach(function (b) {
      b.disabled = on;
      if (on && b === pressed) {
        b.dataset.label = b.textContent;
        b.textContent = TEXT[lang()].wait;
      } else if (!on && b.dataset.label) {
        b.textContent = b.dataset.label;
        delete b.dataset.label;
      }
    });
  }

  function pay(provider, button) {
    var t = TEXT[lang()];
    var amount = parseFloat(String(amountEl ? amountEl.value : '').replace(',', '.'));

    if (!amount || amount < 1 || amount > 100000) {
      setStatus(t.amount, 'error');
      if (amountEl) {
        amountEl.setAttribute('aria-invalid', 'true');
        amountEl.focus();
      }
      return;
    }
    if (amountEl) amountEl.removeAttribute('aria-invalid');

    setStatus('', null);
    lock(true, button);

    fetch('/api/pay.php', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: provider,
        amount: amount,
        description: purposeEl ? purposeEl.value : '',
      }),
    })
      .then(function (r) {
        return r.json().then(function (data) { return { ok: r.ok, data: data }; });
      })
      .then(function (res) {
        if (res.ok && res.data && res.data.pageUrl) {
          window.location.href = res.data.pageUrl;
          return;
        }
        lock(false);
        setStatus((res.data && res.data.error) || TEXT[lang()].network, 'error');
      })
      .catch(function () {
        lock(false);
        setStatus(TEXT[lang()].network, 'error');
      });
  }

  buttons.forEach(function (b) {
    b.addEventListener('click', function (e) {
      e.preventDefault();
      pay(b.getAttribute('data-pay-provider'), b);
    });
  });
})();
