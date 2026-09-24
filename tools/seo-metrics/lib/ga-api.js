'use strict';

/* Запросы к Google Analytics Data API (GA4). Без зависимостей — по тем же
 * причинам, что и соседний gsc-api.js: скрипт живёт на VPS и стартует из cron.
 *
 * Отличия от Search Console, из-за которых это отдельный файл, а не ветка в
 * общем: здесь один ресурс отвечает за всю сеть сразу (разбивка — по хосту в
 * измерении hostName), постраничная выборка считается через offset, а не через
 * startRow, и предел строк задаётся явно.
 */

const API = 'https://analyticsdata.googleapis.com/v1beta';
// Предел ответа у API — 250 000 строк, но забирать столько одним куском незачем:
// памяти это стоит как весь остальной сбор, а разрезы у нас узкие.
const PAGE_LIMIT = 10000;

function ymd(d) {
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
}

/** Дата за N дней до указанной. Считаем в UTC: у GA свой часовой пояс ресурса,
 *  и смешивать его с временем сервера — верный способ потерять сутки. */
function daysBefore(date, n) {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - n);
  return ymd(d);
}

function today() {
  return ymd(new Date());
}

/* GA дозаполняет сутки задним числом: сегодняшнее число сессий за вчера завтра
   будет другим. Для «последнего дня с данными» берём вчера, а хвост сборщик
   перезабирает целиком — по ключу записи заменяются. */
function lastSettledDate() {
  return daysBefore(today(), 1);
}

async function runReport(token, property, body) {
  const res = await fetch(`${API}/properties/${property}:runReport`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) {
    // Ответ GA содержательный: «PERMISSION_DENIED», «property not found».
    // Без него разбираться пришлось бы вслепую.
    let msg = text.slice(0, 300);
    try { msg = JSON.parse(text).error.message; } catch { /* оставляем как есть */ }
    throw new Error(`HTTP ${res.status}: ${msg}`);
  }
  return JSON.parse(text);
}

/** Отчёт целиком, страница за страницей. Строки приводим к плоскому виду:
 *  { keys: [...измерения], values: [...числа] }. */
async function reportAll(token, property, { dateRanges, dimensions, metrics, orderBys }) {
  const out = [];
  let offset = 0;

  for (;;) {
    const data = await runReport(token, property, {
      dateRanges,
      dimensions: dimensions.map(name => ({ name })),
      metrics: metrics.map(name => ({ name })),
      ...(orderBys ? { orderBys } : {}),
      limit: PAGE_LIMIT,
      offset,
      // Служебные строки итогов нам не нужны: панель складывает сама.
      keepEmptyRows: false,
    });

    const rows = data.rows || [];
    for (const r of rows) {
      out.push({
        keys: (r.dimensionValues || []).map(v => v.value),
        values: (r.metricValues || []).map(v => Number(v.value) || 0),
      });
    }

    offset += rows.length;
    // rowCount — сколько строк есть всего, а не сколько пришло. Без него
    // последняя неполная страница выглядела бы как «данные кончились» ровно
    // тогда, когда их ровно PAGE_LIMIT.
    if (!rows.length || offset >= (data.rowCount || 0)) break;
  }
  return out;
}

/** Проверка доступа: лёгкий запрос за неделю. Если ресурс виден, но данные не
 *  отдаёт, узнать это надо на первой секунде, а не после всего сбора. */
async function probe(token, property) {
  const end = lastSettledDate();
  const data = await runReport(token, property, {
    dateRanges: [{ startDate: daysBefore(end, 6), endDate: end }],
    metrics: [{ name: 'sessions' }, { name: 'totalUsers' }],
  });
  const row = (data.rows || [])[0];
  return {
    sessions: row ? Number(row.metricValues[0].value) || 0 : 0,
    users: row ? Number(row.metricValues[1].value) || 0 : 0,
    timeZone: (data.metadata && data.metadata.timeZone) || '?',
  };
}

module.exports = { reportAll, runReport, probe, daysBefore, lastSettledDate, today };
