/* Замір: дотик до форми і відходи в месенджери.

   Навіщо окремий файл. До 19.10.2026 сайт рахував рівно дві речі —
   `generate_lead` (відправлену заявку) і `newsletter_subscribe`. Усе, що
   відбувається ДО відправки, і всі відходи в Telegram, WhatsApp та на телефон
   не рахував ніхто, хоча контакти стоять у шапці й підвалі кожної сторінки.
   Через це неможливо було відповісти на два питання, від яких залежить решта:
   скільки людей кидає форму на півдорозі і скільки йде писати в месенджер
   замість того, щоб її заповнювати.

   Чому слухачі делеговані, а не атрибути в розмітці. Посилання на месенджери
   народжуються в трьох різних генераторах (tools/home, tools/landing,
   tools/blog) плюс у сторінках, які ніхто не генерує. Дописувати гачок у
   кожному місці означало б чотири копії, які розійдуться з першою ж правкою.
   Один слухач на документ ловить будь-яке посилання, звідки б воно не
   приїхало, і переживає перезбирання сторінок.

   Чому кожна подія спрацьовує один раз на перегляд. У сусідній школі
   німецької, чий кабінет ми розбирали, `telegram_click` стоїть з обліком
   «кожен раз»: 1 910 подій від 1 051 людини, тобто 1,82 на людину. Ставки в
   Google Ads училися на цьому числі, і ціна заявки виглядала втричі нижчою за
   справжню. Тут подія кожного виду йде один раз зі сторінки: нас цікавить
   «скільки людей пішло в Telegram», а не «скільки разів вони туди тицьнули».

   Файл навмисно не знає нічого про решту сайту: ні про форму зсередини, ні
   про мову, ні про верстку. Якщо він не виконається, сторінка працює як
   раніше — просто без заміру. */
(function () {
  'use strict';

  /* gtag може ще не існувати: снипет GA асинхронний. Черга dataLayer при
     цьому вже створена синхронно в тому ж снипеті, тож звернення безпечне —
     але перевіряємо, щоб файл не падав на сторінках, де аналітики немає. */
  function send(name, label) {
    if (typeof gtag === 'undefined') return;
    try {
      gtag('event', name, {
        event_category: 'engagement',
        event_label: label || location.pathname
      });
    } catch (e) { /* замір не має права ламати сторінку */ }
  }

  var fired = {};

  function once(name, label) {
    if (fired[name]) return;
    fired[name] = true;
    send(name, label);
  }

  /* ── 1. Дотик до форми ──────────────────────────────────────────────────

     Подія потрібна як знаменник: `generate_lead` без неї — число без бази
     порівняння. У школи німецької доходимість форми 5% (10 018 дотиків проти
     496 заявок), і саме це в них найдешевша точка зростання. Поки ми свою
     цифру не знаємо, лагодити форму немає сенсу — невідомо, що лагодити.

     Ловимо focusin, а не input: людина, яка клацнула в поле й передумала
     друкувати, теж почала заповнювати. Третім аргументом true — бо focus
     не спливає, і без фази захоплення слухач на документі його не побачить. */
  document.addEventListener('focusin', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    if (!t.closest('[data-lead-form]')) return;
    once('form_start');
  }, true);

  /* ── 2. Відходи в месенджери і на телефон ───────────────────────────────

     Перелік навмисно за протоколом і доменом, а не за класом чи текстом:
     розмітка цих посилань у трьох генераторах різна, а адреса однакова. */
  var KINDS = [
    [/^tel:/i,                                     'phone_click'],
    [/^https?:\/\/(t|telegram)\.me\//i,            'telegram_click'],
    [/^https?:\/\/(wa\.me|api\.whatsapp\.com)\//i, 'whatsapp_click'],
    [/^viber:/i,                                   'viber_click'],
    [/^https?:\/\/(www\.)?instagram\.com\//i,      'instagram_click'],
    [/^mailto:/i,                                  'email_click']
  ];

  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    var href = a.getAttribute('href') || '';
    for (var i = 0; i < KINDS.length; i++) {
      if (KINDS[i][0].test(href)) {
        once(KINDS[i][1]);
        return;
      }
    }
  });

  /* ── 3. Атрибуція: звідки людина прийшла ────────────────────────────────

     До 19.10.2026 заявка з цього сайту приходила в CRM без жодної мітки:
     ім'я, телефон, вік і рядок «Заявка з fluent-fox.site». Тобто відповісти,
     яка сторінка чи яка реклама привела людину, було нічим — при тому, що в
     самій CRM колонки під це є й сусідні шістнадцять сайтів їх заповнюють.

     Збирати треба саме тут, а не у формі: людина частіше приходить на статтю
     чи на сторінку країни, а форму бачить уже на третьому кроці. js/lead.js
     живе тільки там, де форма є, і початок шляху він би не застав.

     Клік зберігаємо окремо від решти й надовго: мітка gclid потрібна, щоб
     потім вивантажити в Google Ads саме ОПЛАТИ, а не відправлені форми.
     Шлях від заявки до оплати довший за вікно utm-міток. */
  var ATTR_KEY = 'ff-attr';
  var CLICK_KEY = 'ff-click';
  var ATTR_TTL = 30 * 24 * 60 * 60 * 1000;
  var CLICK_TTL = 90 * 24 * 60 * 60 * 1000;
  /* gclid — звичайний клік; gbraid і wbraid — його замінники там, де Apple не
     дає передати gclid. Назва параметра вирішує, в яку колонку піде
     вивантаження, тому зберігаємо саме її, а не лише значення. */
  var CLICK_PARAMS = ['gclid', 'gbraid', 'wbraid'];
  var OUR_HOST = /(^|\.)(fluent-fox\.site|mycomputer\.(education|school))$/i;

  function read(key, ttl) {
    var stores = [];
    try { stores.push(localStorage); } catch (e) { /* приватне вікно */ }
    try { stores.push(sessionStorage); } catch (e) { /* і тут теж */ }
    for (var i = 0; i < stores.length; i++) {
      try {
        var raw = stores[i].getItem(key);
        if (!raw) continue;
        var box = JSON.parse(raw);
        if (!box || !box.at) continue;
        if (Date.now() - box.at > ttl) continue;
        return box;
      } catch (e) { /* зіпсований запис — поводимось як із порожнім */ }
    }
    return null;
  }

  function write(key, box) {
    var raw;
    try { raw = JSON.stringify(box); } catch (e) { return; }
    try { localStorage.setItem(key, raw); } catch (e) { /* приватне вікно */ }
    try { sessionStorage.setItem(key, raw); } catch (e) { /* і тут теж */ }
  }

  function query() {
    try { return new URLSearchParams(location.search); } catch (e) { return null; }
  }

  /* Чи є цей візит НОВИМ приводом прийти. Внутрішній перехід не привід:
     інакше друга ж сторінка перезаписала б джерело нашою власною адресою, і
     кожна заявка виглядала б прямим заходом. */
  function externalTouch() {
    var q = query();
    if (!q) return false;
    if (q.get('utm_source') || q.get('utm_medium') || q.get('utm_campaign')) return true;
    /* Автопозначка Ads кладе в адресу лише gclid, без utm-міток, а referrer
       частину разів приходить порожнім. Без цієї перевірки рекламний захід
       виглядав би внутрішнім переходом. */
    for (var i = 0; i < CLICK_PARAMS.length; i++) {
      if ((q.get(CLICK_PARAMS[i]) || '').trim()) return true;
    }
    var ref = document.referrer || '';
    if (!ref) return false;
    try { return !OUR_HOST.test(new URL(ref).hostname); } catch (e) { return false; }
  }

  function capture() {
    var q = query();
    if (!q) return;

    var kind = null;
    for (var i = 0; i < CLICK_PARAMS.length; i++) {
      if ((q.get(CLICK_PARAMS[i]) || '').trim()) { kind = CLICK_PARAMS[i]; break; }
    }
    if (kind) {
      write(CLICK_KEY, { id: q.get(kind).trim(), kind: kind, at: Date.now() });
    }

    /* Перше торкання бережемо, але нове ЗОВНІШНЄ перекриває його: людина
       прийшла ще раз і вже іншою дорогою — саме ця дорога й привела. */
    if (read(ATTR_KEY, ATTR_TTL) && !externalTouch()) return;
    write(ATTR_KEY, {
      utm_source:   q.get('utm_source')   || '',
      utm_medium:   q.get('utm_medium')   || '',
      utm_campaign: q.get('utm_campaign') || '',
      referrer:     document.referrer     || '',
      landing_path: location.pathname + location.search,
      at:           Date.now()
    });
  }

  /* Поля для форми. Клік живе довше за мітку джерела, тож заявка з живим
     кліком і згаслим джерелом — нормальний стан, а не порожній результат. */
  function fields() {
    var out = {};
    var box = read(ATTR_KEY, ATTR_TTL);
    if (box) {
      ['utm_source', 'utm_medium', 'utm_campaign', 'referrer', 'landing_path']
        .forEach(function (k) { if (box[k]) out[k] = box[k]; });
    }
    var click = read(CLICK_KEY, CLICK_TTL);
    if (click && click.id) {
      out.click_id = click.id;
      out.click_type = click.kind;
    }
    return out;
  }

  capture();
  window.ffTrack = { fields: fields, capture: capture };
})();
