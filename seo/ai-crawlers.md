# ІІ-пошук: що заміряно, де блокується і як це зняти

Заміри 25.09.2026 з домашньої адреси, пауза 19–20 секунд між запитами (швидша
черга сама дає 429 через per-IP лімит — див. `prod_html_cache` у пам'яті).

## Головне: GPTBot отримує 429, і відповідь народжує сам хостинг

| User-Agent | Відповідь |
|---|---|
| `Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)` | **429** (5 з 5) |
| `Mozilla/5.0 (compatible; GPTBot/1.2)` — без адреси | **429** |
| `Mozilla/5.0 (compatible; Bot/1.2; +https://openai.com/gptbot)` | 200 |
| `OAI-SearchBot/1.0` — агент пошуку ChatGPT | 200 |
| `ClaudeBot`, `Claude-SearchBot`, `PerplexityBot` | 200 |
| `bingbot`, `Googlebot` | 200 |
| `ChatGPT-User/1.0` — коли людина просить ChatGPT відкрити посилання | 200 |

Блокується саме підпис `GPTBot/<версія>`, не швидкість і не адреса в UA.

**429 приходить з нашими ж заголовками.** У відповіді стоять `Content-Security-Policy`,
`X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` і
`Cache-Control: public, max-age=0, must-revalidate` — усе це ставить наш
`.htaccess` через `mod_headers`. Отже запит **дійшов до сервера**, і 429
народив хостинг (LiteSpeed), а не край CDN. Попередній розбір 21.09.2026
вважав навпаки — виправлено цим заміром.

Що це означає: `.htaccess` тут не помічник (правило вище за наш рівень), але й
«вимкнути CDN» проблему не зніме. Потрібне зняття обмеження на боці хостингу.

**Під 429 потрапляє все, що доходить до сервера:** сторінки, `robots.txt`,
`llms.txt`, навіть статика (`css/style.css`, `og/*.jpg`, `*-hero.webp`).
Єдине, що пройшло, — `sitemap.xml` зі статусом `x-hcdn-cache-status: HIT`,
тобто копія з краю, яку віддали без походу на сервер.

## Що зробити власнику — три кроки

**1. Панель Hostinger: перевірити доступ ІІ-краулерів.**
`hPanel → Websites → Dashboard → Performance → CDN`. Якщо там є керування
доступом ботів або ІІ-краулерів (у Hostinger це подавали як «AI Audit» —
перелік відомих ІІ-ботів із вибором Allow/Block), виставити GPTBot у **Allow**.
Офіційна стаття про 429 цього пункту не описує, тому може виявитись, що в
нашому тарифі його немає, — тоді крок 2.

**2. Той самий екран: вимкнути CDN на кілька хвилин** (`Disable`) і повторити
перевірку з кроку «як перевірити» нижче. Ми вже знаємо, що 429 з нашими
заголовками, тобто з сервера, — але підтримка запитає, чи перевіряли CDN.
Після перевірки CDN увімкнути назад.

**3. Звернення в підтримку** — текст нижче.

## Панель Hostinger каже, що GPTBot дозволений

`hPanel → Сайти → fluent-fox.site → Продуктивність → CDN → вкладка
«Перевірка ШІ»` — це і є керування доступом ІІ-краулерів. Перевірено
25.09.2026:

* «Заблоковані запити: 0», «Заблоковані сканери: 0» за 24 години;
* у переліку ботів перемикач «Блок» вимкнено в усіх, включно з GPTBot;
* лічильники за добу: ClaudeBot 16, OAI-SearchBot 6, ChatGPT-User 2,
  PerplexityBot 2, **GPTBot 1** — при тому що тільки наших тестових запитів
  GPTBot було близько десяти.

Одразу після цього повторна перевірка: GPTBot → **429** (двічі), ClaudeBot →
200. Отже цей механізм ні до чого: обмеження живе на іншому шарі, а до
лічильника «Перевірки ШІ» заблоковані запити навіть не доходять.

## Текст для підтримки Hostinger

> Вітаю. На сайті fluent-fox.site будь-який запит із User-Agent краулера
> OpenAI GPTBot отримує **429 Too Many Requests**, незалежно від частоти.
>
> Перевірено 25.09.2026 з однієї адреси, пауза 20 секунд між запитами:
>
> * `curl -A "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)" https://fluent-fox.site/robots.txt` → 429
> * той самий запит із User-Agent `ClaudeBot`, `PerplexityBot`, `bingbot`,
>   `OAI-SearchBot` → 200
> * той самий запит із User-Agent `Mozilla/5.0 (compatible; Bot/1.2; +https://openai.com/gptbot)` → 200
>
> Тобто обмеження спрацьовує саме на підпис `GPTBot/1.2`, а не на кількість
> запитів. 429 приходить і на `/robots.txt`, і на `/llms.txt`, і на статичні
> файли (`/css/style.css`, `/og/*.jpg`).
>
> Відповідь 429 містить заголовки, які ставить наш `.htaccess`
> (`Content-Security-Policy`, `X-Frame-Options`,
> `Cache-Control: public, max-age=0, must-revalidate`), тобто запит доходить до
> веб-сервера й 429 віддає LiteSpeed, а не край CDN. У `.htaccess` у нас немає
> жодного правила за User-Agent — перевірено.
>
> У `robots.txt` GPTBot дозволений явно, ми **хочемо** цього обходу. Прошу
> зняти обмеження за User-Agent для GPTBot на нашому сайті або сказати, де це
> вимкнути самостійно.
>
> Додатково: у панелі `Продуктивність → CDN → Перевірка ШІ` GPTBot **не**
> заблокований (перемикач «Блок» вимкнено, «Заблоковані запити: 0»), тобто це
> обмеження приходить не з цього механізму.
>
> `x-hcdn-request-id` прикладів: `b591df09989e0c1b8a2c9ab65aa15d8d-fra-edge3`,
> `3cca4ab7e77cc6668c2ba86e765006ec-fra-edge1`,
> `95167b70348501dde91acc56d30b9ad5-fra-edge5`.

## Як перевірити, що виправили

    curl -s -o /dev/null -w "%{http_code}\n" \
      -A "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)" \
      https://fluent-fox.site/robots.txt

Має бути `200`. Пауза між спробами ≥16 секунд, інакше 429 прийде законно.

## Що вже перевірено й до нас не стосується

* `robots.txt` дозволяє всіх ІІ-агентів явно: `GPTBot`, `OAI-SearchBot`,
  `ChatGPT-User`, `ClaudeBot`, `Claude-SearchBot`, `PerplexityBot`,
  `Google-Extended`, `Applebot-Extended`;
* сторінки читаються без JS — текст, таблиці, FAQ і JSON-LD у розмітці;
* `llms.txt` віддається всім, крім GPTBot;
* розмітка `EducationalOrganization` має `sameAs` на Instagram, Facebook і
  Telegram та `aggregateRating`;
* у `.htaccess` немає жодного правила за User-Agent.

## Ще один аргумент для підтримки

Власна документація Hostinger про 429 каже дві речі, які прямо суперечать
тому, що ми заміряли: «A 429 Too Many Requests response on a website behind
Hostinger CDN almost always comes from the hosting server or a plugin, not
from the CDN» і «search engine and AI crawlers are subject to the same DDoS
protection as other visitors and are never limited at normal crawl rates».
Перше підтверджує наш висновок (429 з сервера), друге — привід зняти
обмеження: один запит на двадцять секунд це і є normal crawl rate.

## Що з цього справді зміниться

`OAI-SearchBot` і `ChatGPT-User` проходять уже зараз — тобто ChatGPT може і
процитувати нас у відповіді з посиланням, і відкрити сторінку на прохання
людини. `GPTBot`, яким OpenAI
збирає корпус, не проходить зовсім, і поки так — сайт не потрапляє в знання
моделі. Це варто зняти, але сам факт цитування ІІ тримається не на цьому, а на
сторонніх згадках: агрегатори й списки шкіл. Технічна частина дає можливість,
а не сам факт.
