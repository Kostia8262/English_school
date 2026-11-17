/**
 * Отчёт «Індексування → Сторінки» без інтерфейсу Search Console.
 *
 *   node tools/seo-metrics/inspect-index.js               # усі адреси карти + те, що мало покази
 *   node tools/seo-metrics/inspect-index.js --json out.json
 *   node tools/seo-metrics/inspect-index.js --only kyiv,dnipro   # лише адреси, що містять ці шматки
 *   node tools/seo-metrics/inspect-index.js --sitemaps    # тільки стан карти (lastDownloaded, errors)
 *
 * Навіщо. 13.11.2026 на питання «сайт мертвий?» відповідь дала саме перевірка
 * кожної адреси карти (73/81 у індексі, canonical свій, обхід щодня) — і скрипт
 * для неї писали заново в scratchpad. URL Inspection API віддає той самий
 * coverageState, що малює звіт, а сервісний акаунт має рівень siteFullUser.
 *
 * Список адрес — карта сайту плюс сторінки з показами в seo.db за 120 днів:
 * карта каже, що ми вважаємо своїм, а база — що Google уже знає. Розходяться
 * вони якраз там, де цікаво (зняті сторінки з 301, старі .html).
 *
 * Як читати:
 *  - сортувати за lastCrawlTime, а не за причиною: «погане» зі старою датою
 *    обходу — це знімок минулого, правки ще не переобійдено;
 *  - нова сторінка одразу після викатки дає NEUTRAL / unknown — «ще не
 *    обходив», а не «заборонено»;
 *  - у sitemaps API поле indexed завжди 0 — не ознака проблеми.
 * Кнопки «Запросити індексування» в API немає: адреси, які треба
 * підштовхнути, скрипт друкує посиланнями на інспекцію в інтерфейсі (≈10 на день).
 * Квота — 2000 перевірок на добу на ресурс.
 */
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { tokenSource } = require('./lib/google-auth');

const SITE = 'https://fluent-fox.site/';
const SITEMAP = SITE + 'sitemap.xml';
const API = 'https://searchconsole.googleapis.com/v1/urlInspection/index:inspect';
const DB_FILE = process.env.SEO_DB_FILE || path.join(__dirname, 'data', 'seo.db');

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > -1 && process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[i + 1] : fallback;
}

async function sitemapUrls() {
  const res = await fetch(SITEMAP + '?cb=' + Date.now());  // HTML/xml кешується на edge
  if (!res.ok) throw new Error(`${SITEMAP} — HTTP ${res.status}`);
  return [...(await res.text()).matchAll(/<loc>\s*([^<\s]+)\s*<\/loc>/g)].map(m => m[1]);
}

function pagesFromDb() {
  if (!fs.existsSync(DB_FILE)) return [];
  try {
    const { DatabaseSync } = require('node:sqlite');
    const db = new DatabaseSync(DB_FILE, { readOnly: true });
    return db.prepare("SELECT DISTINCT page FROM gsc_page_daily WHERE date >= date('now','-120 day')")
      .all().map(r => r.page).filter(u => u.startsWith(SITE));
  } catch (err) {
    console.error(`seo.db не прочитана (${err.message}) — іду лише по карті`);
    return [];
  }
}

async function inspect(auth, url) {
  for (let attempt = 0; attempt < 4; attempt++) {
    const res = await fetch(API, {
      method: 'POST',
      headers: { Authorization: `Bearer ${await auth.get()}`, 'Content-Type': 'application/json' },
      // coverageState перекладається мовою запиту — порівнюємо з англійським
      body: JSON.stringify({ inspectionUrl: url, siteUrl: SITE, languageCode: 'en-US' }),
    });
    if (res.status === 429 || res.status >= 500) {   // «прийди пізніше», не відмова
      await new Promise(r => setTimeout(r, 2000 * (attempt + 1)));
      continue;
    }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) return { url, error: (body.error && body.error.message) || `HTTP ${res.status}` };
    const s = (body.inspectionResult && body.inspectionResult.indexStatusResult) || {};
    return {
      url, verdict: s.verdict || '', coverage: s.coverageState || '', fetch: s.pageFetchState || '',
      crawl: s.lastCrawlTime || '', googleCanonical: s.googleCanonical || '', userCanonical: s.userCanonical || '',
    };
  }
  return { url, error: 'не відповів після чотирьох спроб' };
}

async function sitemapsState(auth) {
  const res = await fetch(`https://www.googleapis.com/webmasters/v3/sites/${encodeURIComponent(SITE)}/sitemaps`,
    { headers: { Authorization: `Bearer ${await auth.get()}` } });
  const body = await res.json();
  if (!res.ok) throw new Error((body.error && body.error.message) || `HTTP ${res.status}`);
  for (const s of body.sitemap || []) {
    const n = (s.contents || []).map(c => `${c.type}: ${c.submitted}`).join(', ');
    console.log(`${s.path}\n  lastSubmitted ${s.lastSubmitted}  lastDownloaded ${s.lastDownloaded}` +
      `\n  errors ${s.errors}  warnings ${s.warnings}  ${n}  (submitted відстає годинами — дивитись на lastDownloaded)`);
  }
}

async function main() {
  const keyFile = arg('--key', process.env.GSC_KEY_FILE || path.join(os.homedir(), 'secrets', 'gsc.json'));
  const auth = tokenSource(keyFile);   // об'єкт з get(), не функція
  if (process.argv.includes('--sitemaps')) return sitemapsState(auth);

  const inMapSet = new Set(await sitemapUrls());
  const urls = new Set(inMapSet);
  const inMap = urls.size;
  for (const u of pagesFromDb()) urls.add(u.replace(/#.*$/, ''));
  let list = [...urls];
  const only = arg('--only', '');
  if (only) list = list.filter(u => only.split(',').some(p => u.includes(p)));
  console.error(`адрес: ${list.length} (карта ${inMap}, з бази ще ${urls.size - inMap})`);

  const conc = Math.max(1, parseInt(arg('--conc', '6'), 10) || 6);
  const out = [];
  let next = 0;
  await Promise.all(Array.from({ length: conc }, async () => {
    while (next < list.length) out.push(await inspect(auth, list[next++]));
  }));

  const groups = {};
  for (const r of out) (groups[r.error ? 'ПОМИЛКА: ' + r.error : r.coverage || 'unknown'] ||= []).push(r);
  const ok = 'Submitted and indexed';
  console.log(`\nУ індексі (${ok}): ${(groups[ok] || []).length} з ${out.length}`);
  for (const [k, rows] of Object.entries(groups).sort((a, b) => b[1].length - a[1].length)) {
    if (k === ok) continue;
    console.log(`\n${k} — ${rows.length}`);
    for (const r of rows.sort((a, b) => (b.crawl || '').localeCompare(a.crawl || '')))
      console.log(`  ${r.crawl ? r.crawl.slice(0, 10) : 'не обходив'}  ${r.url}${inMapSet.has(r.url) ? '' : '  (не в карті)'}`);
  }
  const foreign = out.filter(r => r.googleCanonical && r.userCanonical && r.googleCanonical !== r.userCanonical);
  if (foreign.length) {
    console.log(`\nGoogle обрав інший canonical — ${foreign.length}:`);
    for (const r of foreign) console.log(`  ${r.url}\n    → ${r.googleCanonical}`);
  }
  const push = out.filter(r => !r.error && r.coverage !== ok && inMapSet.has(r.url)).slice(0, 10);
  if (push.length) {
    console.log('\nПідштовхнути вручну («Запросити індексування», ≈10 на день):');
    for (const r of push)
      console.log(`  https://search.google.com/search-console/inspect?resource_id=${encodeURIComponent(SITE)}&id=${encodeURIComponent(r.url)}`);
  }
  const json = arg('--json', '');
  if (json) { fs.writeFileSync(json, JSON.stringify(out, null, 1)); console.error(`JSON → ${json}`); }
}

main().catch(err => { console.error(err.message); process.exit(1); });
