/**
 * Скільки людей прийшло з ІІ-помічників — ChatGPT, Perplexity, Copilot, Gemini.
 *
 *   node tools/seo-metrics/ai-referrals.js            # за 90 днів
 *   node tools/seo-metrics/ai-referrals.js --days 30
 *   node tools/seo-metrics/ai-referrals.js --all      # заразом усі джерела
 *
 * Навіщо окремий скрипт. Питання власника звучить просто: «я побачу в
 * аналітиці, що люди приходять від ІІ?» — і відповідь на нього має бути
 * числом, а не міркуванням. GA4 показує такі переходи як звичайні реферали з
 * chatgpt.com, perplexity.ai і подібних; тут вони зібрані в один перелік, щоб
 * не шукати їх серед решти джерел щоразу.
 *
 * Базовий замір 25.09.2026: за 90 днів **нуль** сесій із будь-якого ІІ.
 * 151 прямий захід, 22 з Google, 5 із соцмереж. Тобто будь-яка одиниця в цьому
 * звіті — уже подія.
 *
 * Ключ і ресурс ті самі, що в collect-ga.js: сервісний акаунт із
 * ~/secrets/gsc.json, ресурс 545484974.
 *
 * Важливо, що цей звіт НЕ показує: чи читають нас краулери. Перехід людини й
 * обхід ботом — різні речі. Обхід дивляться в логах і в seo/ai-crawlers.md,
 * а тут — тільки живі люди, які клікнули посилання у відповіді помічника.
 */
'use strict';

const os = require('os');
const path = require('path');
const { tokenSource, SCOPE_ANALYTICS } = require('./lib/google-auth');

const PROPERTY = '545484974';

// Хост -> як називати в звіті. Перелік свідомо широкий: помічники міняють
// домени, з яких віддають посилання (chat.openai.com -> chatgpt.com), і
// пропустити перехід через застарілий перелік прикро.
const AI = [
  [/(^|\.)chatgpt\.com$/i, 'ChatGPT'],
  [/(^|\.)chat\.openai\.com$/i, 'ChatGPT'],
  [/(^|\.)openai\.com$/i, 'OpenAI'],
  [/(^|\.)perplexity\.ai$/i, 'Perplexity'],
  [/(^|\.)copilot\.microsoft\.com$/i, 'Copilot'],
  [/(^|\.)bing\.com$/i, 'Bing (у т.ч. Copilot)'],
  [/(^|\.)gemini\.google\.com$/i, 'Gemini'],
  [/(^|\.)bard\.google\.com$/i, 'Gemini'],
  [/(^|\.)claude\.ai$/i, 'Claude'],
  [/(^|\.)you\.com$/i, 'You.com'],
  [/(^|\.)poe\.com$/i, 'Poe'],
  [/(^|\.)phind\.com$/i, 'Phind'],
  [/(^|\.)deepseek\.com$/i, 'DeepSeek'],
  [/(^|\.)grok\.com$/i, 'Grok'],
  [/(^|\.)x\.ai$/i, 'Grok'],
];

function label(source) {
  for (const [re, name] of AI) if (re.test(source)) return name;
  return null;
}

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

async function main() {
  const days = Number(arg('--days', '90'));
  const all = process.argv.includes('--all');
  const keyFile = process.env.GSC_KEY_FILE ||
                  path.join(os.homedir(), 'secrets', 'gsc.json');
  const auth = tokenSource(keyFile, SCOPE_ANALYTICS);
  const token = await auth.get();

  const body = {
    dateRanges: [{ startDate: `${days}daysAgo`, endDate: 'today' }],
    dimensions: [{ name: 'sessionSource' }],
    metrics: [{ name: 'sessions' }, { name: 'activeUsers' }],
    orderBys: [{ metric: { metricName: 'sessions' }, desc: true }],
    limit: 200,
  };
  const res = await fetch(
    `https://analyticsdata.googleapis.com/v1beta/properties/${PROPERTY}:runReport`,
    { method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body) });
  if (!res.ok) {
    console.error(`GA відповів ${res.status}: ${(await res.text()).slice(0, 300)}`);
    process.exit(1);
  }
  const rows = (await res.json()).rows || [];

  const ai = [];
  let aiSessions = 0, total = 0;
  for (const r of rows) {
    const src = r.dimensionValues[0].value;
    const sessions = Number(r.metricValues[0].value);
    const users = Number(r.metricValues[1].value);
    total += sessions;
    const name = label(src);
    if (name) { ai.push({ name, src, sessions, users }); aiSessions += sessions; }
  }

  console.log(`За ${days} днів: ${total} сесій усього.`);
  console.log('');
  if (!ai.length) {
    console.log('З ІІ-помічників — жодного переходу.');
    console.log('');
    console.log('Це очікувано, поки нас нема в сторонніх переліках: помічник');
    console.log('спершу вирішує, кого згадати, і бере це з агрегаторів і оглядів,');
    console.log('а вже потім читає сам сайт. Див. seo/ai-crawlers.md.');
  } else {
    console.log('Переходи з ІІ-помічників:');
    for (const a of ai) {
      console.log(`  ${a.name.padEnd(22)} ${String(a.sessions).padStart(4)} сесій, ` +
                  `${a.users} людей   (${a.src})`);
    }
    const share = total ? (aiSessions / total * 100).toFixed(1) : '0';
    console.log('');
    console.log(`Разом: ${aiSessions} сесій — ${share}% усього трафіку.`);
  }

  if (all) {
    console.log('');
    console.log('Усі джерела:');
    for (const r of rows) {
      console.log(`  ${r.dimensionValues[0].value.padEnd(28)} ` +
                  `${String(r.metricValues[0].value).padStart(4)}`);
    }
  }
}

main().catch(err => { console.error(err.message); process.exit(1); });
