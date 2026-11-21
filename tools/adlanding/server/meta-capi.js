/* Серверна подія Lead у Meta (Conversions API) для лендінга lp.fluent-fox.site.
 *
 * Той самий контракт, що й api/meta-capi.php основного сайту (21.11.2026):
 *   • тільки за згодою (meta.consent === 'all');
 *   • немає META_CAPI_TOKEN або META_PIXEL_ID — модуль вимкнений, одна
 *     строка в лог на старті, заявки працюють як раніше;
 *   • fire-and-forget: відповідь відвідувачу не чекає на Meta, таймаут 5 с,
 *     помилки — у лог;
 *   • телефон і пошта — лише SHA-256 від нормалізованого значення.
 * META_TEST_EVENT_CODE — якщо задано, подія йде в «Тестові події».
 */
'use strict';

const crypto = require('crypto');

const GRAPH_VERSION = 'v23.0';
const TIMEOUT_MS = 5000;

const sha256 = s => crypto.createHash('sha256').update(s).digest('hex');

/* Цифри E.164 без «+»: 0671234567 / 671234567 / +380671234567 → 380671234567. */
function phoneDigits(raw) {
  const d = String(raw || '').replace(/\D/g, '');
  if (d.length === 10 && d[0] === '0') return '38' + d;
  if (d.length === 9) return '380' + d;
  if (d.length === 11 && d.startsWith('80')) return '3' + d;
  return d;
}

const LIMITS = { event_id: 100, fbp: 300, fbc: 600, fbclid: 500, consent: 20, url: 1000 };

/* Поле `meta` із тіла заявки (JSON-рядок) → чистий об'єкт. */
function parseMeta(raw) {
  if (!raw || raw.length > 4000) return {};
  let j;
  try { j = JSON.parse(raw); } catch (e) { return {}; }
  if (!j || typeof j !== 'object') return {};
  const out = {};
  for (const [k, max] of Object.entries(LIMITS)) {
    if (typeof j[k] !== 'string') continue;
    const v = j[k].replace(/[\u0000-\u001f\u007f]/g, '').trim();
    if (v && v.length <= max) out[k] = v;
  }
  return out;
}

/* Тіло запиту в Graph API або null, якщо слати не можна. Поля без значення
   не передаються. lead: { phone, email?, contentName, ip, ua, time? } */
function buildBody(meta, lead, testCode) {
  if (!meta || meta.consent !== 'all' || !meta.event_id) return null;
  const user = {};
  const ph = phoneDigits(lead.phone);
  if (ph) user.ph = [sha256(ph)];
  const em = String(lead.email || '').trim().toLowerCase();
  if (em) user.em = [sha256(em)];
  if (lead.ip) user.client_ip_address = String(lead.ip);
  if (lead.ua) user.client_user_agent = String(lead.ua);
  if (meta.fbp) user.fbp = meta.fbp;
  if (meta.fbc) user.fbc = meta.fbc;
  const event = {
    event_name: 'Lead',
    event_time: lead.time || Math.floor(Date.now() / 1000),
    event_id: meta.event_id,
    action_source: 'website',
  };
  if (meta.url) event.event_source_url = meta.url;
  event.user_data = user;
  if (lead.contentName) event.custom_data = { content_name: String(lead.contentName) };
  const body = { data: [event] };
  if (testCode) body.test_event_code = testCode;
  return body;
}

/* Налаштування з оточення. readKey — функція сервера, що дивиться і в
   process.env, і в .env-файли (див. server.js). */
function config(readKey) {
  const token = (readKey('META_CAPI_TOKEN') || '').trim();
  const pixel = (readKey('META_PIXEL_ID') || '').trim();
  const testCode = (readKey('META_TEST_EVENT_CODE') || '').trim();
  const enabled = Boolean(token) && /^\d{5,20}$/.test(pixel);
  return { enabled, token, pixel, testCode };
}

/* Відправка без очікування. Повертає проміс (для тестів), який ніколи не
   відхиляється: усе, що пішло не так, — рядок у лог. */
function sendLead(cfg, body, fetchImpl, log) {
  const doFetch = fetchImpl || fetch;
  const logger = log || console;
  if (!cfg || !cfg.enabled || !body) return Promise.resolve(false);
  const url = `https://graph.facebook.com/${GRAPH_VERSION}/${cfg.pixel}/events?access_token=${encodeURIComponent(cfg.token)}`;
  return Promise.resolve()
    .then(() => doFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    }))
    .then(async r => {
      if (r.ok) return true;
      const text = await r.text().catch(() => '');
      logger.error(`[META] Graph API відмовив: HTTP ${r.status} ${text.slice(0, 200)}`);
      return false;
    })
    .catch(err => {
      logger.error(`[META] не відправлено: ${err && err.message}`);
      return false;
    });
}

module.exports = { phoneDigits, parseMeta, buildBody, config, sendLead, sha256 };
