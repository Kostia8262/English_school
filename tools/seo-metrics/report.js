'use strict';

/* Отчёт по собранному. У сети «Мой компьютер» это вкладка «SEO» в админке;
 * здесь админки нет и не будет — сайт статический, — поэтому панель заменяет
 * печать в терминал.
 *
 *   node tools/seo-metrics/report.js            # окно 28 дней против предыдущих 28
 *   node tools/seo-metrics/report.js --days 7
 *
 * Ничего не запрашивает у Google: читает только то, что сложили сборщики.
 * Поэтому первым делом печатает, когда они отрабатывали — «нуля показов» и
 * «сбор не запускался» иначе не различить.
 */

const store = require('./lib/store');
const db = store.db;

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  return i === -1 ? fallback : (process.argv[i + 1] || fallback);
}

const WINDOW = Number(arg('--days', 28));

function daysBefore(dateStr, n) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - n);
  return d.toISOString().slice(0, 10);
}

/** Знак изменения словами. «+3 %» рядом с цифрой читается быстрее, чем две
 *  цифры в разных строках, но при нуле в основе процент бессмыслен. */
function delta(now, was) {
  if (!was) return now ? '  (было 0)' : '';
  const pct = Math.round(((now - was) / was) * 100);
  const sign = pct > 0 ? '+' : '';
  return `  (${sign}${pct} % к прошлому периоду)`;
}

function pad(s, n) { return String(s).padEnd(n); }
function num(s, n) { return String(s).padStart(n); }

function head(title) {
  console.log(`\n${title}`);
  console.log('─'.repeat(Math.max(title.length, 40)));
}

/* Сначала — когда собирали. Пустой отчёт из-за незапущенного сборщика выглядит
   ровно как отсутствие трафика, и это самая дорогая ошибка чтения. */
function runs() {
  const rows = db.prepare(`
    SELECT source, MAX(ran_at) AS last, ok, note FROM collector_runs
    GROUP BY source ORDER BY source
  `).all();
  head('Когда собирали');
  if (!rows.length) {
    console.log('Сборщики ни разу не отрабатывали — сначала collect-gsc.js и collect-ga.js.');
    return false;
  }
  for (const r of rows) {
    console.log(`  ${pad(r.source, 12)} ${r.last.slice(0, 16).replace('T', ' ')}  ${r.ok ? 'ок' : 'ОШИБКА'}${r.note ? ' — ' + r.note : ''}`);
  }
  return true;
}

function gsc() {
  const last = db.prepare('SELECT MAX(date) AS d FROM gsc_page_daily').get();
  if (!last || !last.d) { head('Search Console'); console.log('  данных нет'); return; }

  const end = last.d;
  const start = daysBefore(end, WINDOW - 1);
  const prevEnd = daysBefore(start, 1);
  const prevStart = daysBefore(prevEnd, WINDOW - 1);

  const totals = range => db.prepare(`
    SELECT SUM(clicks) AS clicks, SUM(impressions) AS imps,
           SUM(position * impressions) AS wpos, COUNT(DISTINCT page) AS pages
    FROM gsc_page_daily WHERE date BETWEEN ? AND ?
  `).get(range[0], range[1]);

  const now = totals([start, end]);
  const was = totals([prevStart, prevEnd]);

  head(`Search Console · ${start} … ${end} (${WINDOW} дн.)`);
  if (!now.imps) { console.log('  показов нет'); return; }

  const ctr = now.clicks / now.imps * 100;
  const pos = now.wpos / now.imps;
  console.log(`  Клики        ${num(now.clicks, 6)}${delta(now.clicks, was.clicks || 0)}`);
  console.log(`  Показы       ${num(now.imps, 6)}${delta(now.imps, was.imps || 0)}`);
  console.log(`  CTR          ${num(ctr.toFixed(2) + ' %', 6)}`);
  // Позиция усреднена по показам: среднее от средних дало бы строке с одним
  // показом тот же вес, что строке с тысячей.
  console.log(`  Позиция      ${num(pos.toFixed(1), 6)}   (меньше — лучше)`);
  console.log(`  Страниц в выдаче ${now.pages}`);

  const pages = db.prepare(`
    SELECT page, SUM(clicks) AS clicks, SUM(impressions) AS imps,
           SUM(position * impressions) / SUM(impressions) AS pos
    FROM gsc_page_daily WHERE date BETWEEN ? AND ?
    GROUP BY page ORDER BY imps DESC LIMIT 15
  `).all(start, end);

  console.log('\n  Страницы по показам');
  console.log(`  ${pad('адрес', 52)}${num('показы', 8)}${num('клики', 7)}${num('поз.', 7)}`);
  for (const p of pages) {
    const short = p.page.replace(/^https?:\/\/[^/]+/, '') || '/';
    console.log(`  ${pad(short.slice(0, 51), 52)}${num(p.imps, 8)}${num(p.clicks, 7)}${num(p.pos.toFixed(1), 7)}`);
  }

  const qWin = db.prepare(`
    SELECT window_end, window_days FROM gsc_query_window
    ORDER BY window_end DESC, window_days DESC LIMIT 1
  `).get();
  if (!qWin) return;

  const queries = db.prepare(`
    SELECT query, clicks, impressions AS imps, position AS pos FROM gsc_query_window
    WHERE window_end = ? AND window_days = ?
    ORDER BY imps DESC LIMIT 20
  `).all(qWin.window_end, qWin.window_days);

  console.log(`\n  Запросы (окно ${qWin.window_days} дн. до ${qWin.window_end})`);
  console.log(`  ${pad('запрос', 52)}${num('показы', 8)}${num('клики', 7)}${num('поз.', 7)}`);
  for (const q of queries) {
    console.log(`  ${pad(q.query.slice(0, 51), 52)}${num(q.imps, 8)}${num(q.clicks, 7)}${num(q.pos.toFixed(1), 7)}`);
  }

  /* Вторая страница выдачи — самая дешёвая точка роста: показы уже есть,
     кликов ещё нет, и до первой десятки ближе, чем с тридцатой позиции. */
  const near = db.prepare(`
    SELECT query, impressions AS imps, position AS pos FROM gsc_query_window
    WHERE window_end = ? AND window_days = ? AND position > 10 AND position <= 20
    ORDER BY imps DESC LIMIT 10
  `).all(qWin.window_end, qWin.window_days);
  if (near.length) {
    console.log('\n  На второй странице выдачи — ближе всего к кликам');
    for (const q of near) {
      console.log(`  ${pad(q.query.slice(0, 51), 52)}${num(q.imps, 8)}${num('', 7)}${num(q.pos.toFixed(1), 7)}`);
    }
  }
}

function analytics() {
  const last = db.prepare('SELECT MAX(date) AS d FROM ga_site_daily').get();
  if (!last || !last.d) { head('Google Analytics'); console.log('  данных нет'); return; }

  const end = last.d;
  const start = daysBefore(end, WINDOW - 1);
  const prevEnd = daysBefore(start, 1);
  const prevStart = daysBefore(prevEnd, WINDOW - 1);

  const totals = (a, b) => db.prepare(`
    SELECT SUM(sessions) AS sessions, SUM(users) AS users, SUM(views) AS views,
           SUM(engaged) AS engaged
    FROM ga_site_daily WHERE date BETWEEN ? AND ?
  `).get(a, b);

  const now = totals(start, end);
  const was = totals(prevStart, prevEnd);

  head(`Google Analytics · ${start} … ${end} (${WINDOW} дн.)`);
  console.log(`  Сессии       ${num(now.sessions || 0, 6)}${delta(now.sessions || 0, was.sessions || 0)}`);
  console.log(`  Люди         ${num(now.users || 0, 6)}${delta(now.users || 0, was.users || 0)}`);
  console.log(`  Просмотры    ${num(now.views || 0, 6)}`);
  if (now.sessions) {
    console.log(`  Вовлечённость ${num(Math.round(now.engaged / now.sessions * 100) + ' %', 5)}`);
  }

  const channels = db.prepare(`
    SELECT channel, SUM(sessions) AS sessions FROM ga_source_daily
    WHERE date BETWEEN ? AND ? GROUP BY channel ORDER BY sessions DESC
  `).all(start, end);
  const chWas = new Map(db.prepare(`
    SELECT channel, SUM(sessions) AS sessions FROM ga_source_daily
    WHERE date BETWEEN ? AND ? GROUP BY channel
  `).all(prevStart, prevEnd).map(r => [r.channel, r.sessions]));

  if (channels.length) {
    console.log('\n  Откуда приходят');
    for (const c of channels) {
      console.log(`  ${pad(c.channel, 24)}${num(c.sessions, 6)}${delta(c.sessions, chWas.get(c.channel) || 0)}`);
    }
    /* Отдельной строкой: ради ИИ и писались статьи, и ноль здесь — это ответ,
       а не отсутствие данных. */
    const ai = channels.find(c => /AI /i.test(c.channel));
    if (!ai) console.log(`  ${pad('AI Assistant', 24)}${num(0, 6)}   — переходов из ИИ нет`);
  }

  const pWin = db.prepare(`
    SELECT window_end, window_days FROM ga_page_window
    ORDER BY window_end DESC, window_days DESC LIMIT 1
  `).get();
  if (!pWin) return;

  const pages = db.prepare(`
    SELECT path, views, users, avg_sec FROM ga_page_window
    WHERE window_end = ? AND window_days = ?
    ORDER BY views DESC LIMIT 15
  `).all(pWin.window_end, pWin.window_days);

  console.log(`\n  Страницы по просмотрам (окно ${pWin.window_days} дн. до ${pWin.window_end})`);
  console.log(`  ${pad('адрес', 52)}${num('просм.', 8)}${num('люди', 7)}${num('сек.', 7)}`);
  for (const p of pages) {
    console.log(`  ${pad(p.path.slice(0, 51), 52)}${num(p.views, 8)}${num(p.users, 7)}${num(Math.round(p.avg_sec), 7)}`);
  }
}

console.log(`Хранилище: ${store.DB_FILE}`);
if (runs()) {
  gsc();
  analytics();
}
console.log('');
