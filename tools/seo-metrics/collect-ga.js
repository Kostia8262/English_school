'use strict';

/* Сбор показателей FluentFox из Google Analytics (GA4) в своё хранилище.
 *
 *   node tools/seo-metrics/collect-ga.js             # добрать хвост (7 дней) и окно страниц
 *   node tools/seo-metrics/collect-ga.js --days 90   # добрать глубже
 *   node tools/seo-metrics/collect-ga.js --backfill  # первый заход: вся доступная история
 *   node tools/seo-metrics/collect-ga.js --check     # только проверить доступ
 *   node tools/seo-metrics/collect-ga.js --key путь.json
 *
 * Зачем он рядом с collect-gsc.js. Search Console отвечает на вопрос «как нас
 * находят в поиске» и про переходы из ChatGPT не знает в принципе. GA закрывает
 * ровно эту дыру: что делают люди, придя откуда угодно. Для сайта, у которого
 * главный нерешённый вопрос — упоминания в ИИ, это не второй источник, а первый.
 *
 * Почему хвост, а не «вчера»: GA дозаполняет сутки задним числом, и забрав один
 * день, мы бы навсегда сохранили его неполным.
 */

const os = require('os');
const path = require('path');
const { tokenSource, SCOPE_ANALYTICS } = require('./lib/google-auth');
const ga = require('./lib/ga-api');
const store = require('./lib/store');

const DEFAULT_KEY = process.env.GSC_KEY_FILE || path.join(os.homedir(), 'secrets', 'gsc.json');
const TAIL_DAYS = 7;
const PAGE_WINDOW = 28;
// GA4 хранит события 14 месяцев, но ресурс копит их только с момента установки
// счётчика — задним числом история не появляется.
const BACKFILL_DAYS = 400;

/* Ресурс GA4 сайта. Идентификатор — не секрет (секрет только ключ), поэтому
   живёт в коде: так видно, что именно собирается. Счётчик на страницах —
   G-K60LSESFTV, но Data API просит числовой идентификатор ресурса, это разные
   вещи. Переопределяется через GA_PROPERTY. */
const PROPERTY = process.env.GA_PROPERTY || '545484974';

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  return i === -1 ? fallback : (process.argv[i + 1] || fallback);
}
const has = name => process.argv.includes(name);

/** Наш ли хост. Ресурс заведён под fluent-fox.site, но проверяем всё равно:
 *  чужой счётчик на своей странице — ошибка, которую лучше увидеть строкой
 *  «отброшено», чем найти потом в отчёте. */
function keep(host) {
  if (store.NOT_A_SITE.test(host)) return false;
  return store.OUR_HOST.test(host);
}

/* Сутки: сессии, люди, просмотры, вовлечённые сессии и время.
   `averageSessionDuration` приходит секундами с дробью — храним как есть,
   округление это дело отчёта. */
async function collectDaily(token, startDate, endDate) {
  const rows = await ga.reportAll(token, PROPERTY, {
    dateRanges: [{ startDate, endDate }],
    dimensions: ['date', 'hostName'],
    metrics: ['sessions', 'totalUsers', 'screenPageViews', 'engagedSessions', 'averageSessionDuration'],
  });

  /* Один и тот же день приходит несколькими строками — по хосту (голый домен и
     www). Складываем: в хранилище сутки это одна строка. Среднее время
     взвешиваем по сессиям, иначе день с одной сессией весил бы как день с сотней. */
  const byDate = new Map();
  let skipped = 0;
  for (const r of rows) {
    const [rawDate, host] = r.keys;
    if (!keep(host)) { skipped++; continue; }
    const date = `${rawDate.slice(0, 4)}-${rawDate.slice(4, 6)}-${rawDate.slice(6, 8)}`;
    const acc = byDate.get(date) || { date, sessions: 0, users: 0, views: 0, engaged: 0, secSum: 0 };
    acc.sessions += r.values[0];
    acc.users += r.values[1];
    acc.views += r.values[2];
    acc.engaged += r.values[3];
    acc.secSum += r.values[4] * r.values[0];
    byDate.set(date, acc);
  }
  const out = [...byDate.values()].map(a => ({
    date: a.date, sessions: a.sessions, users: a.users, views: a.views,
    engaged: a.engaged, avgSec: a.sessions ? a.secSum / a.sessions : 0,
  }));

  const saved = store.saveGaSiteRows(out, PROPERTY);
  console.log(`    сутки ${startDate} … ${endDate}: ${saved} строк${skipped ? `, чужих/своих визитов отсеяно: ${skipped}` : ''}`);
  return saved;
}

async function collectSources(token, startDate, endDate) {
  const rows = await ga.reportAll(token, PROPERTY, {
    dateRanges: [{ startDate, endDate }],
    dimensions: ['date', 'hostName', 'sessionDefaultChannelGroup', 'sessionSource'],
    metrics: ['sessions', 'totalUsers'],
  });

  const byKey = new Map();
  for (const r of rows) {
    const [rawDate, host, channel, source] = r.keys;
    if (!keep(host)) continue;
    const date = `${rawDate.slice(0, 4)}-${rawDate.slice(4, 6)}-${rawDate.slice(6, 8)}`;
    const ch = channel || '(не визначено)';
    const src = source || '(не визначено)';
    const k = `${date}\u0000${ch}\u0000${src}`;
    const acc = byKey.get(k) || { date, channel: ch, source: src, sessions: 0, users: 0 };
    acc.sessions += r.values[0];
    acc.users += r.values[1];
    byKey.set(k, acc);
  }
  const saved = store.saveGaSourceRows([...byKey.values()], PROPERTY);
  console.log(`    источники: ${saved} строк`);
  return saved;
}

/* Страницы берём окном, без разбивки по дням: разрез «дата × страница» даёт
   строк на порядок больше при той же пользе — вопрос к нему всегда «что читают
   сейчас», а не «что читали 14 августа». */
async function collectPages(token, endDate, days) {
  const startDate = ga.daysBefore(endDate, days - 1);
  const rows = await ga.reportAll(token, PROPERTY, {
    dateRanges: [{ startDate, endDate }],
    dimensions: ['hostName', 'pagePath'],
    metrics: ['screenPageViews', 'totalUsers', 'userEngagementDuration'],
    orderBys: [{ metric: { metricName: 'screenPageViews' }, desc: true }],
  });

  const byPath = new Map();
  for (const r of rows) {
    const [host, p] = r.keys;
    if (!keep(host)) continue;
    const acc = byPath.get(p) || { path: p, views: 0, users: 0, secSum: 0 };
    acc.views += r.values[0];
    acc.users += r.values[1];
    // userEngagementDuration — сумма секунд по всем просмотрам, а не среднее.
    // Делим сами: среднее от GA считается по сессиям и к странице не подходит.
    acc.secSum += r.values[2];
    byPath.set(p, acc);
  }
  const out = [...byPath.values()].map(a => ({
    path: a.path, views: a.views, users: a.users, avgSec: a.views ? a.secSum / a.views : 0,
  }));

  const saved = store.saveGaPageRows(out, endDate, days, PROPERTY);
  console.log(`    страницы ${startDate} … ${endDate}: ${saved} строк`);
  return saved;
}

async function main() {
  const keyFile = arg('--key', DEFAULT_KEY);
  const auth = tokenSource(keyFile, SCOPE_ANALYTICS);
  const token = await auth.get();

  const endDate = ga.lastSettledDate();
  console.log(`Сервисный аккаунт: ${auth.email}`);
  console.log(`Последний день с данными: ${endDate}`);
  console.log(`Хранилище: ${store.DB_FILE}\n`);

  try {
    const p = await ga.probe(token, PROPERTY);
    console.log(`✓ ресурс ${PROPERTY} — за неделю ${p.sessions} сессий, ${p.users} человек (пояс ${p.timeZone})\n`);
  } catch (err) {
    console.error(`✗ ресурс ${PROPERTY} — ${err.message}`);
    console.error(`Аккаунт ${auth.email} должен быть читателем этого ресурса GA4.`);
    store.logRun('ga', false, null, err.message.slice(0, 200));
    process.exit(1);
  }

  if (has('--check')) {
    store.logRun('ga-check', true, null, null);
    process.exit(0);
  }

  const days = has('--backfill') ? BACKFILL_DAYS : Number(arg('--days', TAIL_DAYS));
  const startDate = ga.daysBefore(endDate, days - 1);
  console.log(`Собираем ${startDate} … ${endDate} (${days} дн.)\n`);

  let total = 0, failures = 0;
  try {
    total += await collectDaily(token, startDate, endDate);
    total += await collectSources(token, startDate, endDate);
    total += await collectPages(token, endDate, PAGE_WINDOW);
  } catch (err) {
    console.log(`    ! ${err.message}`);
    failures++;
  }

  console.log(`\nВсего записано строк: ${total}`);
  store.logRun('ga', failures === 0, total, failures ? `ошибок: ${failures}` : null);
  process.exit(failures ? 1 : 0);
}

main().catch(err => {
  try { store.logRun('ga', false, null, err.message.slice(0, 200)); } catch { /* база могла не открыться */ }
  console.error(err.message);
  process.exit(1);
});
