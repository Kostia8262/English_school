/* node --test tools/adlanding/server/meta-capi.test.js
   Без жодного запиту в Meta: fetch підміняється. */
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('crypto');
const m = require('./meta-capi');

const sha = s => crypto.createHash('sha256').update(s).digest('hex');
const META = { event_id: 'e-1', consent: 'all', fbp: 'fb.1.1.2', fbc: 'fb.1.1700000000000.abc', url: 'https://lp.fluent-fox.site/?utm_source=fb' };
const LEAD = { phone: '+380671234567', contentName: 'trial_lesson', ip: '1.2.3.4', ua: 'UA', time: 1763700000 };

test('номер нормалізується в E.164-цифри', () => {
  assert.equal(m.phoneDigits('0671234567'), '380671234567');
  assert.equal(m.phoneDigits('+38 (067) 123-45-67'), '380671234567');
  assert.equal(m.phoneDigits('671234567'), '380671234567');
  assert.equal(m.phoneDigits('80671234567'), '380671234567');
  assert.equal(m.phoneDigits('+48 600 100 200'), '48600100200');
});

test('тіло за контрактом: хеші, ip/ua, fbp/fbc, custom_data', () => {
  const b = m.buildBody(META, { ...LEAD, email: '  Mail@Example.COM ' });
  assert.deepEqual(b, { data: [{
    event_name: 'Lead', event_time: 1763700000, event_id: 'e-1', action_source: 'website',
    event_source_url: META.url,
    user_data: { ph: [sha('380671234567')], em: [sha('mail@example.com')],
      client_ip_address: '1.2.3.4', client_user_agent: 'UA', fbp: 'fb.1.1.2', fbc: 'fb.1.1700000000000.abc' },
    custom_data: { content_name: 'trial_lesson' },
  }] });
});

test('поля без значення не передаються; test_event_code додається', () => {
  const b = m.buildBody({ event_id: 'e-2', consent: 'all' }, { phone: '0671234567' }, 'TEST123');
  const ev = b.data[0];
  assert.deepEqual(Object.keys(ev.user_data), ['ph']);
  assert.equal(ev.event_source_url, undefined);
  assert.equal(ev.custom_data, undefined);
  assert.equal(b.test_event_code, 'TEST123');
});

test('без згоди або без event_id — нічого', () => {
  assert.equal(m.buildBody({ ...META, consent: 'necessary' }, LEAD), null);
  assert.equal(m.buildBody({ ...META, consent: '' }, LEAD), null);
  assert.equal(m.buildBody({ consent: 'all' }, LEAD), null);
});

test('parseMeta: битий JSON і зайві поля відкидаються', () => {
  assert.deepEqual(m.parseMeta('{oops'), {});
  assert.deepEqual(m.parseMeta(''), {});
  assert.deepEqual(m.parseMeta(JSON.stringify({ event_id: 'x', consent: 'all', evil: 'y', fbp: 5 })), { event_id: 'x', consent: 'all' });
});

test('без токена модуль вимкнений і fetch не викликається', async () => {
  const cfg = m.config(k => ({ META_PIXEL_ID: '931791603129774' }[k] || ''));
  assert.equal(cfg.enabled, false);
  let called = 0;
  const ok = await m.sendLead(cfg, m.buildBody(META, LEAD), () => { called++; });
  assert.equal(ok, false);
  assert.equal(called, 0);
});

test('з токеном — один POST на graph.facebook.com/v23.0/<pixel>/events', async () => {
  const cfg = m.config(k => ({ META_PIXEL_ID: '931791603129774', META_CAPI_TOKEN: 'tok en' }[k] || ''));
  assert.equal(cfg.enabled, true);
  const calls = [];
  const ok = await m.sendLead(cfg, m.buildBody(META, LEAD), async (url, opts) => { calls.push([url, opts]); return { ok: true }; });
  assert.equal(ok, true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], 'https://graph.facebook.com/v23.0/931791603129774/events?access_token=tok%20en');
  assert.equal(JSON.parse(calls[0][1].body).data[0].event_id, 'e-1');
});

test('збій Meta не кидає виняток — лише рядок у лог', async () => {
  const cfg = { enabled: true, token: 't', pixel: '931791603129774' };
  const lines = [];
  const log = { error: l => lines.push(l) };
  assert.equal(await m.sendLead(cfg, m.buildBody(META, LEAD), async () => { throw new Error('boom'); }, log), false);
  assert.equal(await m.sendLead(cfg, m.buildBody(META, LEAD), async () => ({ ok: false, status: 400, text: async () => 'bad' }), log), false);
  assert.equal(lines.length, 2);
});
