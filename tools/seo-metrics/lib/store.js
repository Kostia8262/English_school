'use strict';

/* Хранилище показателей FluentFox.
 *
 * Зачем своё хранилище, а не запрос в Google по клику: окно Search Console
 * скользящее, и то, что видно сегодня, через три месяца недоступно. Не сложив
 * срез к себе сегодня, сравнивать декабрь будет не с чем. GA глубже, но и он
 * знает только то, что было после установки счётчика.
 *
 * Отличие от сетевой версии в `my_computer_new/tools/seo-metrics`, откуда это
 * перенесено: там четырнадцать сайтов, и у каждой таблицы есть колонка `site`
 * плюс карта «хост → слаг». Здесь сайт один, колонки нет — вместо неё фильтр
 * по хосту на входе, потому что сервисный аккаунт видит и ресурсы соседней
 * сети, и без фильтра они утекли бы в этот файл.
 *
 * База лежит вне git: репозиторий публичный, а цифры посещаемости в нём никому
 * не нужны. Путь переопределяется через SEO_DB_FILE.
 */

const fs = require('fs');
const path = require('path');
const { DatabaseSync } = require('node:sqlite');

const DEFAULT_DB = path.join(__dirname, '..', 'data', 'seo.db');
const DB_FILE = process.env.SEO_DB_FILE || DEFAULT_DB;

/* Хосты, которые считаются нашими. Сервисный аккаунт добавлен пользователем и
   в ресурсы соседней сети — её строки сюда попадать не должны. */
const OUR_HOST = /(^|\.)fluent-fox\.site$/i;
/* Стенд и локальный запуск шлют события в тот же счётчик GA. Отсеиваем на
   входе, а не в отчёте: цифру, которую надо мысленно уменьшать, однажды
   перенесут в отчёт как есть. */
const NOT_A_SITE = /^(localhost|127\.0\.0\.1|dev\.|test\.|staging\.)/i;

fs.mkdirSync(path.dirname(DB_FILE), { recursive: true });
const db = new DatabaseSync(DB_FILE);

db.exec('PRAGMA journal_mode = WAL');
db.exec('PRAGMA synchronous = NORMAL');

db.exec(`
CREATE TABLE IF NOT EXISTS gsc_page_daily (
  date        TEXT    NOT NULL,
  page        TEXT    NOT NULL,
  clicks      INTEGER NOT NULL,
  impressions INTEGER NOT NULL,
  position    REAL    NOT NULL,
  PRIMARY KEY (date, page)
);
CREATE INDEX IF NOT EXISTS idx_gsc_page_date ON gsc_page_daily(date);

-- Запросы приходят без разбивки по дням намеренно: с измерением «дата» строк
-- становится столько, что предел в 25 000 срезает хвост, и пропадают как раз
-- редкие запросы, ради которых всё и затевалось. Берём окном.
CREATE TABLE IF NOT EXISTS gsc_query_window (
  window_end  TEXT    NOT NULL,
  window_days INTEGER NOT NULL,
  query       TEXT    NOT NULL,
  clicks      INTEGER NOT NULL,
  impressions INTEGER NOT NULL,
  position    REAL    NOT NULL,
  PRIMARY KEY (window_end, window_days, query)
);

CREATE TABLE IF NOT EXISTS ga_site_daily (
  date     TEXT    NOT NULL,
  property TEXT    NOT NULL,
  sessions INTEGER NOT NULL,
  users    INTEGER NOT NULL,
  views    INTEGER NOT NULL,
  engaged  INTEGER NOT NULL,
  avg_sec  REAL    NOT NULL,
  PRIMARY KEY (date, property)
);

-- channel — группировка самого Google («Organic Search», «AI Assistant»),
-- source — домен. Держим оба: группа переживает переименование домена, домен
-- отвечает на вопрос «а это чей трафик».
CREATE TABLE IF NOT EXISTS ga_source_daily (
  date     TEXT    NOT NULL,
  property TEXT    NOT NULL,
  channel  TEXT    NOT NULL,
  source   TEXT    NOT NULL,
  sessions INTEGER NOT NULL,
  users    INTEGER NOT NULL,
  PRIMARY KEY (date, property, channel, source)
);

CREATE TABLE IF NOT EXISTS ga_page_window (
  window_end  TEXT    NOT NULL,
  window_days INTEGER NOT NULL,
  property    TEXT    NOT NULL,
  path        TEXT    NOT NULL,
  views       INTEGER NOT NULL,
  users       INTEGER NOT NULL,
  avg_sec     REAL    NOT NULL,
  PRIMARY KEY (window_end, window_days, property, path)
);

-- Чтобы «данных нет» можно было отличить от «сборщик не отработал».
CREATE TABLE IF NOT EXISTS collector_runs (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT    NOT NULL,
  ran_at TEXT    NOT NULL,
  ok     INTEGER NOT NULL,
  rows   INTEGER,
  note   TEXT
);
`);

/* У node:sqlite нет `.transaction()` из better-sqlite3, а сбор пишет десятки
   тысяч строк: без общей транзакции каждая строка — отдельная запись на диск,
   и разница выходит в минуты против секунд. */
function inTransaction(fn) {
  db.exec('BEGIN');
  try {
    const out = fn();
    db.exec('COMMIT');
    return out;
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  }
}

function hostOf(pageUrl) {
  try { return new URL(pageUrl).hostname.toLowerCase(); } catch { return ''; }
}

const upsertPage = db.prepare(`
  INSERT INTO gsc_page_daily (date, page, clicks, impressions, position)
  VALUES (?, ?, ?, ?, ?)
  ON CONFLICT(date, page) DO UPDATE SET
    clicks = excluded.clicks, impressions = excluded.impressions, position = excluded.position
`);

const upsertQuery = db.prepare(`
  INSERT INTO gsc_query_window (window_end, window_days, query, clicks, impressions, position)
  VALUES (?, ?, ?, ?, ?, ?)
  ON CONFLICT(window_end, window_days, query) DO UPDATE SET
    clicks = excluded.clicks, impressions = excluded.impressions, position = excluded.position
`);

const upsertGaSite = db.prepare(`
  INSERT INTO ga_site_daily (date, property, sessions, users, views, engaged, avg_sec)
  VALUES (?, ?, ?, ?, ?, ?, ?)
  ON CONFLICT(date, property) DO UPDATE SET
    sessions = excluded.sessions, users = excluded.users, views = excluded.views,
    engaged = excluded.engaged, avg_sec = excluded.avg_sec
`);

const upsertGaSource = db.prepare(`
  INSERT INTO ga_source_daily (date, property, channel, source, sessions, users)
  VALUES (?, ?, ?, ?, ?, ?)
  ON CONFLICT(date, property, channel, source) DO UPDATE SET
    sessions = excluded.sessions, users = excluded.users
`);

const upsertGaPage = db.prepare(`
  INSERT INTO ga_page_window (window_end, window_days, property, path, views, users, avg_sec)
  VALUES (?, ?, ?, ?, ?, ?, ?)
  ON CONFLICT(window_end, window_days, property, path) DO UPDATE SET
    views = excluded.views, users = excluded.users, avg_sec = excluded.avg_sec
`);

const insRun = db.prepare(
  'INSERT INTO collector_runs (source, ran_at, ok, rows, note) VALUES (?, ?, ?, ?, ?)'
);

/* Взвешенное среднее позиции. Позиция в ответе Google уже усреднена внутри
   своей строки, поэтому при объединении строк её нельзя ни складывать, ни
   усреднять поровну: строка с одним показом весила бы столько же, сколько
   строка с тысячей. Вес — показы. */
function weightedPosition(rows) {
  let imps = 0, sum = 0;
  for (const r of rows) {
    const i = r.impressions | 0;
    imps += i;
    sum += (r.position || 0) * i;
  }
  return imps ? sum / imps : 0;
}

module.exports = {
  db,
  DB_FILE,
  OUR_HOST,
  NOT_A_SITE,
  weightedPosition,

  /** Строки «дата + страница» из Search Console. Чужие хосты отбрасываем:
   *  сервисный аккаунт видит и ресурсы соседней сети. */
  savePageRows(rows) {
    let saved = 0, foreign = 0;
    inTransaction(() => {
      for (const r of rows) {
        const [date, page] = r.keys;
        if (!OUR_HOST.test(hostOf(page))) { foreign++; continue; }
        upsertPage.run(date, page, r.clicks | 0, r.impressions | 0, r.position || 0);
        saved++;
      }
    });
    return { saved, foreign };
  },

  /** Запрос×страница схлопывается в запрос: страниц под один запрос бывает
   *  несколько, их показы надо сложить, а позиции — взвесить. */
  saveQueryRows(rows, windowEnd, windowDays) {
    const byQuery = new Map();
    for (const r of rows) {
      const [query, page] = r.keys;
      if (!OUR_HOST.test(hostOf(page))) continue;
      if (!byQuery.has(query)) byQuery.set(query, []);
      byQuery.get(query).push({
        clicks: r.clicks | 0, impressions: r.impressions | 0, position: r.position || 0,
      });
    }
    inTransaction(() => {
      for (const [query, group] of byQuery) {
        const clicks = group.reduce((s, g) => s + g.clicks, 0);
        const imps = group.reduce((s, g) => s + g.impressions, 0);
        upsertQuery.run(windowEnd, windowDays, query, clicks, imps, weightedPosition(group));
      }
    });
    return byQuery.size;
  },

  saveGaSiteRows(rows, property) {
    inTransaction(() => {
      for (const r of rows) {
        upsertGaSite.run(r.date, String(property), r.sessions, r.users, r.views, r.engaged, r.avgSec);
      }
    });
    return rows.length;
  },

  saveGaSourceRows(rows, property) {
    inTransaction(() => {
      for (const r of rows) {
        upsertGaSource.run(r.date, String(property), r.channel, r.source, r.sessions, r.users);
      }
    });
    return rows.length;
  },

  saveGaPageRows(rows, windowEnd, windowDays, property) {
    inTransaction(() => {
      for (const r of rows) {
        upsertGaPage.run(windowEnd, windowDays, String(property), r.path, r.views, r.users, r.avgSec);
      }
    });
    return rows.length;
  },

  logRun(source, ok, rows, note) {
    insRun.run(source, new Date().toISOString(), ok ? 1 : 0, rows == null ? null : rows, note || null);
  },
};
