'use strict';

/* Сбор показателей FluentFox из Search Console в своё хранилище.
 *
 *   node tools/seo-metrics/collect-gsc.js              # добрать хвост (14 дней) и окно запросов
 *   node tools/seo-metrics/collect-gsc.js --days 90    # добрать глубже
 *   node tools/seo-metrics/collect-gsc.js --backfill   # первый заход: вся доступная история
 *   node tools/seo-metrics/collect-gsc.js --check      # только проверить доступ, ничего не писать
 *   node tools/seo-metrics/collect-gsc.js --key путь.json
 *
 * Почему хвост, а не «вчера»: данные Search Console отстают на два-три дня и
 * ещё несколько дней дозаполняются задним числом. Забрав один день, мы бы
 * навсегда сохранили его неполным. Записи перезаписываются по ключу, поэтому
 * повторный сбор того же периода безопасен.
 *
 * Сервисному аккаунту видны и ресурсы соседней сети — он один на оба проекта.
 * Берём только наши: чужие строки в этой базе были бы мусором, который потом
 * молча попадёт в отчёт.
 */

const os = require('os');
const path = require('path');
const { tokenSource } = require('./lib/google-auth');
const gsc = require('./lib/gsc-api');
const store = require('./lib/store');

const DEFAULT_KEY = process.env.GSC_KEY_FILE || path.join(os.homedir(), 'secrets', 'gsc.json');
const TAIL_DAYS = 14;
const QUERY_WINDOW = 28;
// Search Console хранит 16 месяцев, но ресурс копит статистику только с момента
// подтверждения. Берём с запасом внутрь окна, а не на границе: на самом краю
// дни отдаются неполными.
const BACKFILL_DAYS = 480;
const CHUNK_DAYS = 30;

/** Ресурс наш, если это fluent-fox.site — доменный (`sc-domain:`) или адресный. */
const OURS = /(^sc-domain:(www\.)?fluent-fox\.site$)|(^https?:\/\/(www\.)?fluent-fox\.site\/?$)/i;

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  return i === -1 ? fallback : (process.argv[i + 1] || fallback);
}
const has = name => process.argv.includes(name);

async function collectPages(token, property, startDate, endDate) {
  let saved = 0, foreign = 0;
  let cursorEnd = endDate;

  while (cursorEnd >= startDate) {
    const s = gsc.daysBefore(cursorEnd, CHUNK_DAYS - 1);
    const chunkStart = s < startDate ? startDate : s;

    const rows = await gsc.queryAll(token, property, {
      startDate: chunkStart,
      endDate: cursorEnd,
      dimensions: ['date', 'page'],
      type: 'web',
    });
    const res = store.savePageRows(rows);
    saved += res.saved;
    foreign += res.foreign;
    console.log(`    ${chunkStart} … ${cursorEnd}: ${rows.length} строк`
      + (res.foreign ? `, чужих хостов отброшено ${res.foreign}` : ''));

    if (chunkStart === startDate) break;
    cursorEnd = gsc.daysBefore(chunkStart, 1);
  }
  if (foreign) console.log(`    всего отброшено чужих строк: ${foreign}`);
  return saved;
}

async function collectQueries(token, property, endDate, days) {
  const startDate = gsc.daysBefore(endDate, days - 1);
  const rows = await gsc.queryAll(token, property, {
    startDate,
    endDate,
    dimensions: ['query', 'page'],
    type: 'web',
  });
  const groups = store.saveQueryRows(rows, endDate, days);
  console.log(`    запросы ${startDate} … ${endDate}: ${rows.length} строк → ${groups} запросов`);
  return groups;
}

async function main() {
  const keyFile = arg('--key', DEFAULT_KEY);
  const auth = tokenSource(keyFile);
  const token = await auth.get();

  const endDate = gsc.lastSettledDate();
  console.log(`Сервисный аккаунт: ${auth.email}`);
  console.log(`Последний день с данными: ${endDate}`);
  console.log(`Хранилище: ${store.DB_FILE}\n`);

  const visible = await gsc.listSites(token);
  const ours = visible.filter(v => OURS.test(v.url));

  if (!ours.length) {
    console.error('Ресурс fluent-fox.site аккаунту не виден.');
    console.error(`Аккаунт ${auth.email} надо добавить пользователем в Search Console.`);
    if (visible.length) {
      console.error(`\nЧто ему видно сейчас (${visible.length}):`);
      for (const v of visible) console.error(`  ${v.url}  [${v.level}]`);
    }
    store.logRun('gsc', false, null, 'ресурс fluent-fox.site не виден');
    process.exit(1);
  }

  /* Проверка доступа отдельным лёгким запросом: если ресурс виден, но данные
     не отдаёт, узнать это надо на первой секунде, а не после всего сбора. */
  let failures = 0;
  const properties = [];
  for (const { url, level } of ours) {
    try {
      const probe = await gsc.queryAll(token, url, {
        startDate: gsc.daysBefore(endDate, 6),
        endDate,
        dimensions: ['date'],
        type: 'web',
      });
      const clicks = probe.reduce((s, r) => s + (r.clicks | 0), 0);
      const imps = probe.reduce((s, r) => s + (r.impressions | 0), 0);
      console.log(`✓ ${url}  [${level}] — за неделю ${imps} показов, ${clicks} кликов`);
      properties.push(url);
    } catch (err) {
      console.log(`✗ ${url}  [${level}] — ${err.message}`);
      failures++;
    }
  }
  console.log('');

  if (has('--check')) {
    store.logRun('gsc-check', failures === 0, null, `недоступно ресурсов: ${failures}`);
    process.exit(failures ? 1 : 0);
  }
  if (!properties.length) {
    store.logRun('gsc', false, null, 'ресурс недоступен');
    console.error('Ресурс не отдал данные — сбор не начинаем.');
    process.exit(1);
  }

  const days = has('--backfill') ? BACKFILL_DAYS : Number(arg('--days', TAIL_DAYS));
  const startDate = gsc.daysBefore(endDate, days - 1);
  console.log(`Собираем ${startDate} … ${endDate} (${days} дн.)\n`);

  let totalPages = 0, totalQueries = 0;
  for (const property of properties) {
    console.log(`  ${property}`);
    try {
      totalPages += await collectPages(token, property, startDate, endDate);
      totalQueries += await collectQueries(token, property, endDate, QUERY_WINDOW);
    } catch (err) {
      console.log(`    ! ${err.message}`);
      failures++;
    }
    console.log('');
  }

  store.logRun('gsc', failures === 0, totalPages + totalQueries,
    `страниц ${totalPages}, запросов ${totalQueries}, ошибок ${failures}`);

  console.log(`Готово: строк по страницам ${totalPages}, запросов ${totalQueries}.`);
  process.exit(failures ? 1 : 0);
}

main().catch(err => {
  try { store.logRun('gsc', false, null, String(err.message).slice(0, 300)); } catch { /* база могла не открыться */ }
  console.error('Сбор не удался:', err.message);
  process.exit(1);
});
