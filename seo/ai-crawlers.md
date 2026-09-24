# ІІ-пошук: що заміряно й що заблоковано

Заміри 25.09.2026, з домашньої адреси, із паузою 16–20 секунд між запитами
(швидша черга сама дає 429 — див. `prod_html_cache` у пам'яті проєкту).

## Головна знахідка: GPTBot отримує 429 від edge Hostinger

| User-Agent | Відповідь |
|---|---|
| `Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)` | **429** (5 спроб із 5) |
| `Mozilla/5.0 (compatible; GPTBot/1.2)` | **429** |
| `Mozilla/5.0 (compatible; Bot/1.2; +https://openai.com/gptbot)` | 200 |
| `Mozilla/5.0 (compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)` | 200 |
| `Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)` | 200 |
| `Mozilla/5.0 (compatible; PerplexityBot/1.0; …)` | 200 |
| `Mozilla/5.0 (compatible; bingbot/2.0; …)` | 200 |

Отже ріже саме підпис `GPTBot/<версія>`, а не швидкість і не адреса в UA.
Під 429 потрапляють і `robots.txt`, і `llms.txt` — тобто краулер OpenAI не
може прочитати навіть дозвіл на обхід. `sitemap.xml` при цьому віддається 200.

Наш `robots.txt` усіх ІІ-краулерів дозволяє явно (`GPTBot`, `OAI-SearchBot`,
`ChatGPT-User`, `ClaudeBot`, `Claude-SearchBot`, `PerplexityBot`,
`Google-Extended`, `Applebot-Extended`), тобто причина не в нас. Відповідь
народжується на краю Hostinger (`Server: hcdn`, у відповіді є
`x-hcdn-request-id`, Apache запиту не бачить), тому `.htaccess` тут
безсилий — потрібна підтримка хостингу.

Що це означає на практиці: `OAI-SearchBot` — агент, яким ChatGPT дістає
сторінки для відповідей із посиланнями, — проходить, і цитувати нас технічно
може. `GPTBot` — агент, яким OpenAI збирає корпус, — не проходить зовсім.

## Текст для підтримки Hostinger

> Вітаю. На сайті fluent-fox.site ваш CDN (`Server: hcdn`) відповідає
> **429 Too Many Requests** на будь-який запит із User-Agent краулера OpenAI
> GPTBot, незалежно від частоти запитів.
>
> Перевірено 25.09.2026 з однієї адреси з паузою 20 секунд між запитами:
>
> * `curl -A "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)" https://fluent-fox.site/robots.txt` → 429
> * той самий запит із User-Agent `ClaudeBot`, `PerplexityBot`, `bingbot` → 200
> * той самий запит із User-Agent `Mozilla/5.0 (compatible; Bot/1.2; +https://openai.com/gptbot)` → 200
>
> Тобто блокується саме підпис `GPTBot/1.2`, а не кількість запитів. 429
> віддається навіть на `/robots.txt` і `/llms.txt`.
>
> Ми хочемо, щоб GPTBot мав доступ: у `robots.txt` він дозволений явно.
> Прошу зняти обмеження для цього User-Agent на нашому сайті або підказати,
> де в hPanel це налаштування, якщо воно на нашому боці.
>
> `x-hcdn-request-id` прикладів: `3cca4ab7e77cc6668c2ba86e765006ec-fra-edge1`,
> `12216dddd40846484b01b88e6d7ba204-fra-edge2`,
> `95167b70348501dde91acc56d30b9ad5-fra-edge5`.

## Як перевірити, що виправили

    curl -s -o /dev/null -w "%{http_code}\n" \
      -A "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)" \
      https://fluent-fox.site/robots.txt

Має бути `200`. Між спробами тримати паузу ≥16 секунд, інакше 429 прийде
законно — через per-IP лімит.

## Що заміряно й до нас не стосується

* `robots.txt` — усі ІІ-агенти дозволені, перевірено вище;
* сторінки читаються без JS — текст, таблиці, FAQ і JSON-LD у розмітці;
* `llms.txt` віддається 200 усім, крім GPTBot;
* розмітка `EducationalOrganization` має `sameAs` на Instagram, Facebook і
  Telegram та `aggregateRating`.

Головний нетехнічний важіль лишається тим самим, що й у розборі 21.09.2026:
сторонніх згадок нема, а ІІ в цій ніші цитує агрегатори й списки. Технічна
частина без цього дає лише можливість бути процитованим, а не сам факт.
