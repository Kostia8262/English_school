'use strict';

/* Запросы в Search Console.
 *
 * Главное, что нужно помнить про эти данные:
 *
 * 1. Позиция в ответе — уже усреднённая по показам внутри строки. Складывать
 *    позиции нельзя ни при каком объединении строк: среднее от средних врёт.
 *    Объединять только взвешенно по показам — см. store.js.
 * 2. Ответ отдаётся страницами по 25 000 строк. Пока пришло ровно столько,
 *    сколько просили, — данные не кончились, и надо запрашивать дальше.
 * 3. Данные отстают на два-три дня и ещё несколько дней дозаполняются задним
 *    числом. Поэтому сборщик каждый раз перезабирает хвост, а не только вчера.
 * 4. Набор измерений задаёт дробность: чем их больше, тем быстрее упрёшься в
 *    предел строк и тем больше строк с одним показом. Поэтому запросы узкие и
 *    разные, а не один общий.
 */

const API = 'https://searchconsole.googleapis.com/webmasters/v3';
const PAGE = 25000;

/** Сколько дней назад Search Console ещё не знает. */
const LAG_DAYS = 3;

function ymd(d) { return d.toISOString().slice(0, 10); }

/** Последняя дата, за которую данные уже есть (с запасом на отставание). */
function lastSettledDate(today = new Date()) {
  const d = new Date(today);
  d.setUTCDate(d.getUTCDate() - LAG_DAYS);
  return ymd(d);
}

function daysBefore(dateStr, days) {
  const d = new Date(dateStr + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() - days);
  return ymd(d);
}

/* Ресурсы Search Console спрашиваем у самого API, а не держим списком.
 *
 * Список в коде пришлось бы угадывать: у одного и того же домена ресурс бывает
 * доменным (`sc-domain:...`) и адресным (`https://.../`), это разные периметры
 * с разными данными — сравнивать их между собой нельзя. Плюс список в коде
 * молча устаревает, когда ресурс добавили или переделали.
 *
 * Ответ заодно отвечает на главный вопрос: куда сервисный аккаунт вообще пущен.
 */
async function listSites(token) {
  const res = await fetch(`${API}/sites`, { headers: { Authorization: `Bearer ${token}` } });
  const text = await res.text();
  if (!res.ok) throw new Error(`список ресурсов не получен (HTTP ${res.status}): ${text.slice(0, 300)}`);
  const entries = JSON.parse(text).siteEntry || [];
  // siteUnverifiedUser — ресурс виден, но данные по нему не отдаются.
  return entries
    .filter(e => e.permissionLevel && e.permissionLevel !== 'siteUnverifiedUser')
    .map(e => ({ url: e.siteUrl, level: e.permissionLevel }));
}

async function queryAll(token, property, body, { onPage } = {}) {
  const url = `${API}/sites/${encodeURIComponent(property)}/searchAnalytics/query`;
  const rows = [];
  let startRow = 0;

  for (;;) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, rowLimit: PAGE, startRow }),
    });
    const text = await res.text();
    if (!res.ok) {
      // 403 здесь почти всегда значит одно: сервисный аккаунт не добавлен
      // пользователем в этот ресурс. Говорим об этом прямо, а не «HTTP 403».
      if (res.status === 403) {
        throw new Error(`нет доступа к ${property} — добавлен ли сервисный аккаунт `
          + `пользователем в Search Console? Ответ: ${text.slice(0, 200)}`);
      }
      throw new Error(`${property}: HTTP ${res.status} ${text.slice(0, 300)}`);
    }
    const data = JSON.parse(text);
    const batch = data.rows || [];
    rows.push(...batch);
    if (onPage) onPage(rows.length);
    if (batch.length < PAGE) break;
    startRow += PAGE;
  }
  return rows;
}

module.exports = { API, PAGE, LAG_DAYS, listSites, queryAll, ymd, lastSettledDate, daysBefore };
