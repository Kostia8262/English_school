/**
 * Переподати sitemap.xml у Google Search Console.
 *
 *   node tools/seo-metrics/submit-sitemap.js            # ключ із ~/secrets/gsc.json
 *   node tools/seo-metrics/submit-sitemap.js --dry      # тільки показати, що зробить
 *   node tools/seo-metrics/submit-sitemap.js --key шлях.json
 *
 * Навіщо окремий скрипт. Google прибрав ping-адресу для карт сайту в 2023-му,
 * і єдиний спосіб сказати «перечитай мапу» — Search Console: руками в
 * інтерфейсі або цим викликом API. Після додавання сторінок (країни, нові
 * посадкові) переподання не обов'язкове — Google перечитує мапу сам, — але
 * воно прискорює перший обхід, і це рівно те, чого від нього хочуть.
 *
 * Права. Читання метрик (collect-gsc.js) працює зі scope `webmasters.readonly`,
 * а надсилання карти вимагає `webmasters` і рівня доступу вище за
 * «Обмежений» у самій Search Console. Якщо сервісний акаунт доданий лише
 * читачем, API відповість 403 — скрипт скаже про це прямо, а не «щось пішло
 * не так».
 *
 * Bing і Яндекс тут не потрібні: у них працює IndexNow, і виказка вже подає
 * змінені сторінки через tools/indexnow/submit.py.
 */
'use strict';

const os = require('os');
const path = require('path');
const { tokenSource } = require('./lib/google-auth');
const { listSites } = require('./lib/gsc-api');

const SCOPE = 'https://www.googleapis.com/auth/webmasters';
const SITEMAP = 'https://fluent-fox.site/sitemap.xml';
const OURS = /(^sc-domain:(www\.)?fluent-fox\.site$)|(^https?:\/\/(www\.)?fluent-fox\.site\/?$)/i;

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

async function main() {
  const dry = process.argv.includes('--dry');
  const keyFile = arg('--key', process.env.GSC_KEY_FILE ||
                      path.join(os.homedir(), 'secrets', 'gsc.json'));
  const auth = tokenSource(keyFile, SCOPE);
  const token = await auth.get();
  console.log(`Сервісний акаунт: ${auth.email}`);

  const sites = (await listSites(token)).filter(s => OURS.test(s.url));
  if (!sites.length) {
    console.error('У цього акаунта немає ресурсу fluent-fox.site.');
    console.error('Додайте його користувачем у Search Console з правом «Повний».');
    process.exit(1);
  }

  for (const site of sites) {
    const url = `https://www.googleapis.com/webmasters/v3/sites/` +
                `${encodeURIComponent(site.url)}/sitemaps/${encodeURIComponent(SITEMAP)}`;
    console.log(`${site.url}  (доступ: ${site.level})`);
    if (dry) { console.log('  --dry: запит не надсилався'); continue; }

    const res = await fetch(url, {
      method: 'PUT',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 200 || res.status === 204) {
      console.log('  карта подана');
    } else if (res.status === 403) {
      const body = await res.text();
      console.error('  403: замало прав. Потрібен рівень «Повний» для ' +
                    `${auth.email} у Search Console.`);
      console.error(`  ${body.slice(0, 300)}`);
      process.exitCode = 1;
    } else {
      console.error(`  ${res.status}: ${(await res.text()).slice(0, 300)}`);
      process.exitCode = 1;
    }
  }
}

main().catch(err => { console.error(err.message); process.exit(1); });
