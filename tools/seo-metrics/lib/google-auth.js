'use strict';

/* Доступ к Google API по сервисному аккаунту — без единой зависимости.
 *
 * Библиотека googleapis тянет за собой полсотни пакетов ради одной подписи, а
 * скрипт запускают руками раз в неделю: чем меньше у него движущихся частей,
 * тем меньше поводов однажды не запуститься. Здесь весь обмен — это
 * подписанный JWT в обмен на часовой токен, тридцать строк на crypto из
 * стандартной поставки.
 *
 * Ключ в репозиторий не кладётся никогда: путь к файлу приходит снаружи.
 */

const crypto = require('crypto');
const fs = require('fs');

const TOKEN_URL = 'https://oauth2.googleapis.com/token';
// Только чтение. Сборщику нечего писать ни в Search Console, ни в Analytics,
// и права, которых у него нет, невозможно потратить по ошибке.
const SCOPE = 'https://www.googleapis.com/auth/webmasters.readonly';
const SCOPE_ANALYTICS = 'https://www.googleapis.com/auth/analytics.readonly';

const b64url = buf => Buffer.from(buf).toString('base64')
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

function readKey(file) {
  let raw;
  try {
    raw = fs.readFileSync(file, 'utf8');
  } catch (err) {
    throw new Error(`ключ не прочитан (${file}): ${err.message}`);
  }
  let key;
  try {
    key = JSON.parse(raw);
  } catch {
    throw new Error(`ключ не разобран как JSON: ${file}`);
  }
  // Скачать можно и OAuth-клиент вместо сервисного аккаунта — файлы похожи,
  // а ошибка вылезла бы только на подписи и звучала бы невнятно.
  if (key.type !== 'service_account' || !key.client_email || !key.private_key) {
    throw new Error(`это не ключ сервисного аккаунта: ${file}`);
  }
  return key;
}

/** Токен на час. Тот же ключ повторно не подписываем, пока прежний жив.
 *  Область прав — параметром: ключ один на оба сборщика, а токен под каждую
 *  область свой, и общий кэш выдал бы Analytics токен от Search Console. */
function tokenSource(keyFile, scope = SCOPE) {
  const key = readKey(keyFile);
  let cached = null;

  async function fetchToken() {
    const now = Math.floor(Date.now() / 1000);
    const header = b64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
    const claim = b64url(JSON.stringify({
      iss: key.client_email,
      scope,
      aud: TOKEN_URL,
      iat: now,
      exp: now + 3600,
    }));
    const signature = b64url(
      crypto.createSign('RSA-SHA256').update(`${header}.${claim}`).sign(key.private_key)
    );

    const res = await fetch(TOKEN_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        assertion: `${header}.${claim}.${signature}`,
      }),
    });
    const body = await res.text();
    if (!res.ok) {
      // Ответ Google здесь содержательный («invalid_grant», «Not authorized»),
      // и без него разбираться пришлось бы вслепую.
      throw new Error(`токен не выдан (HTTP ${res.status}): ${body.slice(0, 300)}`);
    }
    const data = JSON.parse(body);
    cached = { token: data.access_token, expires: now + (data.expires_in || 3600) - 60 };
    return cached.token;
  }

  return {
    email: key.client_email,
    async get() {
      const now = Math.floor(Date.now() / 1000);
      if (cached && cached.expires > now) return cached.token;
      return fetchToken();
    },
  };
}

module.exports = { tokenSource, readKey, SCOPE, SCOPE_ANALYTICS };
