/* Міні-сервіс лендінга FluentFox на VPS.
 *
 * Навіщо. Основний сайт живе на Hostinger, і 22.10.2026 їхній CDN увімкнув
 * «Checking your browser before accessing»: замість сторінки людина отримує
 * заглушку з JS-перевіркою. За добу — 105 сеансів реклами, 0 секунд на сеанс,
 * жодної заявки. Вимкнути це можна лише в їхній панелі, тому лендінг
 * переїжджає сюди, де тієї перевірки немає.
 *
 * Чому не Express. У сусідніх сайтів мережі він є, але тягнути сюди
 * node_modules заради віддачі 200 КБ статики і одного POST — зайве. Тут
 * чистий http: менше рухомих частин, нічого оновлювати.
 *
 * Заявка йде тим самим контрактом, що й у решти шістнадцяти сайтів:
 * POST https://mycomputer.education/api/leads/admin із заголовком
 * x-admin-token. Поле source лишає слід «fluent-fox.site», щоб у CRM було
 * видно, звідки заявка, а utm-мітки доїжджають у notes.
 */
'use strict';

const http = require('http');
const fs = require('fs');
const crypto = require('crypto');
const path = require('path');

const PORT = Number(process.env.PORT) || 3030;
const PUBLIC = path.join(__dirname, 'public');
const CRM = 'https://mycomputer.education/api/leads/admin';

/* Токен CRM не копіюємо сюди окремим файлом: зайва копія секрета — це ще одне
   місце, де його можна забути при ротації. Читаємо з конфіга сусіднього сайта
   мережі, який уже цим токеном користується. Якщо його колись перенесуть,
   сервіс скаже про це в лог при старті, а не мовчки загубить заявку. */
function readEnvKey(key) {
  if (process.env[key]) return process.env[key];
  const candidates = [
    '/var/www/mycomputer-new/sites/python/.env',
    '/var/www/mycomputer-new/sites/main/.env',
  ];
  const re = new RegExp('^' + key + '=(.+)$', 'm');
  for (const file of candidates) {
    try {
      const m = fs.readFileSync(file, 'utf8').match(re);
      if (m) return m[1].trim().replace(/^["']|["']$/g, '');
    } catch (e) { /* немає файла — пробуємо наступний */ }
  }
  return '';
}

const TOKEN = readEnvKey('MAIN_ADMIN_TOKEN');

/* Канарейка сторожа доставки заявок (tools/watchdogs/check-lead-delivery.js
   мережі). Контракт той самий, що в api/lead.php основного сайту й у
   server/canary.js мережі: запит із заголовком x-canary НЕ створює заявку
   НІКОЛИ. Секрет збігся — форвард у CRM справжній, із тим самим заголовком,
   і CRM теж нічого не пише; не збігся або не заданий — 503 і жодного форварду.
   До 20.11.2026 канарейки тут не було: GET казав лише «токен знайдено», і
   ніхто не знав, чи CRM його приймає. */
const CANARY = readEnvKey('CANARY_TOKEN');
const CANARY_MIN_LEN = 16;

function safeEq(a, b) {
  const x = Buffer.from(String(a));
  const y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.png': 'image/png',
  '.webp': 'image/webp',
  '.json': 'application/json; charset=utf-8',
};

/* Та сама політика, що на основному сайті, плюс домени Meta: без frame-src і
   www.facebook.com у form-action піксель мовчки не шле жодної події — подія
   йде прихованою формою в кадрі на facebook.com/tr/. */
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://www.google-analytics.com https://connect.facebook.net",
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self' data:",
  "img-src 'self' data: https:",
  "connect-src 'self' https://www.google-analytics.com https://*.google-analytics.com https://analytics.google.com https://*.analytics.google.com https://stats.g.doubleclick.net https://www.googletagmanager.com https://www.facebook.com https://connect.facebook.net",
  "frame-ancestors 'self'",
  "frame-src 'self' https://www.facebook.com",
  "form-action 'self' https://www.facebook.com",
  "base-uri 'self'",
  "object-src 'none'",
].join('; ');

function normalizePhone(raw) {
  let d = String(raw || '').replace(/\D/g, '');
  if (d.length === 12 && d.startsWith('380')) d = d.slice(3);
  else if (d.length === 10 && d[0] === '0') d = d.slice(1);
  return d;
}

function send(res, code, body, type) {
  res.writeHead(code, {
    'Content-Type': type || 'application/json; charset=utf-8',
    'Content-Security-Policy': CSP,
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
  });
  res.end(body);
}

/* Заявка. Відповідь строго {result:'success'} — саме це поле читає js/lead.js,
   і саме через опрацювання відповіді, а не «просто відправили», сторінка не
   показує «дякуємо» там, де заявка не дійшла. */
function handleLead(req, res) {
  let raw = '';
  req.on('data', c => {
    raw += c;
    if (raw.length > 8192) req.destroy();
  });
  req.on('end', async () => {
    const isCanary = req.headers['x-canary'] !== undefined;
    if (isCanary) return handleCanary(req, res);
    const p = new URLSearchParams(raw);
    const name = (p.get('name') || '').trim().slice(0, 120);
    const phone = normalizePhone(p.get('phone'));

    if (name.length < 2 || phone.length !== 9) {
      return send(res, 400, JSON.stringify({ result: 'error', message: 'Перевірте імʼя та телефон' }));
    }
    if (!TOKEN) {
      console.error('[LEAD] MAIN_ADMIN_TOKEN не заданий — заявка нікуди не піде');
      return send(res, 502, JSON.stringify({ result: 'error', message: 'Сервіс тимчасово недоступний' }));
    }

    const marks = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'referrer', 'landing_path', 'page']
      .map(k => (p.get(k) ? `${k}=${p.get(k)}` : null))
      .filter(Boolean)
      .join(' · ');

    const payload = {
      child_name: name,
      phone: '+380' + phone,
      source: 'fluent-fox.site',
      notes: 'Заявка з лендінга lp.fluent-fox.site' + (marks ? ' · ' + marks : ''),
    };
    const age = parseInt(p.get('childAge'), 10);
    if (age >= 3 && age <= 18) payload.age = age;

    try {
      const r = await fetch(CRM, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-admin-token': TOKEN },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const text = await r.text();
        console.error(`[LEAD] CRM відмовила: HTTP ${r.status} ${text.slice(0, 200)} | ${payload.phone}`);
        return send(res, 502, JSON.stringify({ result: 'error', message: 'Не вдалося передати заявку' }));
      }
      console.log(`[LEAD] ${name} | ${payload.phone} | ${marks || 'без міток'}`);
      send(res, 200, JSON.stringify({ result: 'success', stored: ['crm'] }));
    } catch (err) {
      console.error(`[LEAD] CRM недоступна: ${err.message} | ${payload.phone}`);
      send(res, 502, JSON.stringify({ result: 'error', message: 'Не вдалося передати заявку' }));
    }
  });
}

/* Канарейка: перевіряє рівно той шлях, яким іде справжня заявка (токен цього
   сервісу → CRM), але нічого не записує ні тут, ні в CRM. Відповідь — у форматі,
   який розбирає checkStaticSite сторожа. */
async function handleCanary(req, res) {
  if (CANARY.length < CANARY_MIN_LEN || !safeEq(req.headers['x-canary'], CANARY)) {
    return send(res, 503, JSON.stringify({ canary: false, error: 'CANARY_TOKEN не заданий на лендінгу або не збігся' }));
  }
  const crm = { configured: Boolean(TOKEN), reached: false, accepted: false };
  if (!TOKEN) return send(res, 200, JSON.stringify({ canary: true, written: false, crm }));
  const started = Date.now();
  try {
    const r = await fetch(CRM, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-admin-token': TOKEN, 'x-canary': req.headers['x-canary'] },
      body: JSON.stringify({ child_name: 'Canary Watchdog', phone: '+380990000000', age: 9, source: 'fluent-fox.site',
        notes: 'Канарейка сторожа · лендінг lp.fluent-fox.site' }),
    });
    const text = await r.text();
    let json = null;
    try { json = JSON.parse(text); } catch (e) { /* розберемо нижче */ }
    crm.reached = true;
    crm.status = r.status;
    crm.ms = Date.now() - started;
    /* Прийнято — лише за явним підтвердженням CRM, як в api/lead.php. */
    crm.accepted = Boolean(json && json.canary === true && json.accepted === true);
    if (!crm.accepted) crm.error = String((json && json.error) || text).slice(0, 200);
  } catch (err) {
    crm.error = err.message;
  }
  send(res, 200, JSON.stringify({ canary: true, written: false, crm }));
}

function serveStatic(req, res) {
  let rel = decodeURIComponent(req.url.split('?')[0]);
  if (rel.endsWith('/')) rel += 'index.html';
  /* Жодних ../: шлях збираємо від PUBLIC і перевіряємо, що не вийшли назовні. */
  const file = path.normalize(path.join(PUBLIC, rel));
  if (!file.startsWith(PUBLIC)) return send(res, 403, 'Forbidden', 'text/plain');

  fs.readFile(file, (err, data) => {
    if (err) return send(res, 404, 'Not found', 'text/plain');
    const ext = path.extname(file).toLowerCase();
    const immutable = /\.(css|js|woff2|svg|ico|png|webp)$/.test(ext);
    res.writeHead(200, {
      'Content-Type': TYPES[ext] || 'application/octet-stream',
      'Content-Security-Policy': CSP,
      'X-Content-Type-Options': 'nosniff',
      'Cache-Control': immutable ? 'public, max-age=31536000' : 'public, max-age=300',
    });
    res.end(data);
  });
}

http.createServer((req, res) => {
  if (req.method === 'POST' && req.url.split('?')[0] === '/api/lead.php') return handleLead(req, res);
  if (req.method !== 'GET' && req.method !== 'HEAD') return send(res, 405, 'Method not allowed', 'text/plain');
  /* Сторож доставки заявок сусідньої мережі стукає GET-ом. */
  if (req.url.split('?')[0] === '/api/lead.php') {
    /* canary/probe — те самі поля, що віддає api/lead.php основного сайту:
       за ними сторож вирішує, чи можна слати канарейку. */
    return send(res, 200, JSON.stringify({ ok: true, crm: Boolean(TOKEN), canary: CANARY.length >= CANARY_MIN_LEN, probe: true }));
  }
  serveStatic(req, res);
}).listen(PORT, '127.0.0.1', () => {
  console.log(`FluentFox лендінг слухає 127.0.0.1:${PORT}, CRM-токен ${TOKEN ? 'є' : 'ВІДСУТНІЙ'}`);
});
