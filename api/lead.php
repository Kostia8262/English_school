<?php
/**
 * Приймач заявок FluentFox.
 *
 * Навіщо він узагалі є. Сайт — статика на Hostinger, свого сервера немає, і
 * заявка досі йшла з браузера прямо в Google Apps Script. Через це:
 *   • заявка жила тільки рядком у таблиці — ні статусу, ні «передзвонили»,
 *     ні нагадування, що лід висить необробленим третю годину;
 *   • сторож доставки сусідньої мережі (tools/watchdogs/check-lead-delivery.js)
 *     окремо позначав FluentFox як сайт, доставку якого перевірити нічим:
 *     канарейку слати нікуди, бо свого приймача немає.
 *
 * Тепер форма постить сюди, на свій же домен, а цей файл розкладає заявку в
 * два місця: у CRM «Мій комп'ютер» (там воронка, статуси й нагадування) і в
 * стару Google-таблицю. Таблиця лишається навмисно: поки не набереться місяць
 * спокійної роботи, дублікат коштує нічого, а втрачена заявка коштує клієнта.
 *
 * Токен CRM у репозиторій не потрапляє. Він лежить у lead-config.php на рівень
 * вище за public_html — rsync деплою чистить тільки public_html, тож файл
 * переживає викатки. Кладе його деплой із секрету CRM_ADMIN_TOKEN; зразок для
 * ручної установки — api/lead-config.sample.php.
 */

declare(strict_types=1);

header('Cache-Control: no-store');

// Версія ассетів — руками, як на юридичних сторінках і на 404: цей файл не
// складається генератором. Розходження ловить python tools/audit/assets.py,
// який заради цього рядка й почав дивитись у .php.
const ASSET_VERSION = '20260924c';

const LOG_NAME       = 'lead-errors.log';
const RATE_MAX       = 10;          // заявок з однієї адреси
const RATE_WINDOW    = 15 * 60;     // за 15 хвилин — та сама норма, що в CRM
const TIMEOUT        = 8;           // секунд на кожного отримувача
const CANARY_HEADER  = 'HTTP_X_CANARY';
const CANARY_MIN_LEN = 16;

/** Каталог поруч із lead-config.php: на рівень вище за public_html. */
function private_dir(): string
{
    return dirname(__DIR__, 2);
}

/**
 * Чи це звичайна відправка форми, а не `fetch` зі сторінки.
 *
 * Навіщо розрізняти. У форми є `action` і `method`, тож без JS вона постить
 * сюди сама — і людина побачить те, що ми відповімо. JSON у вікні браузера
 * був би не кращим за колишню тиху втрату заявки.
 *
 * `Sec-Fetch-Dest` ставить браузер, а не сторінка, тому заголовок є й тоді,
 * коли скрипти вимкнено — рівно той випадок, заради якого ця гілка й існує.
 * Для браузера без `Sec-Fetch-*` лишається `Accept`: навігація просить html,
 * `fetch` із js/home.js — ні.
 */
function is_navigation(): bool
{
    $dest = strtolower((string) ($_SERVER['HTTP_SEC_FETCH_DEST'] ?? ''));
    if ($dest !== '') {
        return $dest === 'document';
    }
    return str_contains(strtolower((string) ($_SERVER['HTTP_ACCEPT'] ?? '')), 'text/html');
}

function respond(int $code, array $payload): void
{
    http_response_code($code);
    if (($_SERVER['REQUEST_METHOD'] ?? '') === 'POST' && is_navigation()) {
        header('Content-Type: text/html; charset=utf-8');
        echo result_page(($payload['result'] ?? '') === 'success',
                         (string) ($payload['message'] ?? ''));
        exit;
    }
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($payload, JSON_UNESCAPED_UNICODE);
    exit;
}

/**
 * Сторінка відповіді для того, хто надіслав форму без JS.
 *
 * Своїх стилів не тримає: підключає той самий style.css, що й решта сайту, і
 * користується тими ж класами. Робити тут окремий вигляд означало б завести
 * другу дизайн-систему заради сторінки, яку бачить меншість.
 */
function result_page(bool $ok, string $message): string
{
    $ru = ((string) ($_POST['lang'] ?? 'uk')) === 'ru';
    $v  = ASSET_VERSION;

    $title = $ok
        ? ($ru ? 'Заявка принята' : 'Заявку прийнято')
        : ($ru ? 'Заявка не отправилась' : 'Заявка не надіслалась');
    $lead = $ok
        ? ($ru ? 'Мы перезвоним в течение 30 минут и договоримся о времени пробного урока.'
               : 'Ми передзвонимо протягом 30 хвилин і домовимось про час пробного уроку.')
        : ($message !== '' ? $message
                           : ($ru ? 'Попробуйте ещё раз или позвоните нам.'
                                  : 'Спробуйте ще раз або зателефонуйте нам.'));
    $back = $ru ? 'Вернуться на сайт' : 'Повернутись на сайт';
    $call = $ru ? 'Позвонить' : 'Зателефонувати';
    $home = $ru ? '/?lang=ru' : '/';
    $h    = static fn(string $s): string
        => htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');

    return '<!DOCTYPE html><html lang="' . ($ru ? 'ru' : 'uk') . '"><head>'
         . '<meta charset="UTF-8">'
         . '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
         . '<meta name="robots" content="noindex">'
         . '<title>' . $h($title) . ' — FluentFox</title>'
         . '<link rel="stylesheet" href="/css/style.css?v=' . $v . '">'
         . '</head><body class="font-sans antialiased text-gray-800 bg-cream">'
         . '<main class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">'
         . '<div class="inline-flex items-center justify-center w-16 h-16 rounded-full '
         . ($ok ? 'bg-fox-50 text-fox-600' : 'bg-gray-100 text-gray-500')
         . ' text-3xl mb-6">' . ($ok ? '🦊' : '📞') . '</div>'
         . '<h1 class="text-3xl md:text-4xl font-black text-gray-900 mb-3 leading-tight">'
         . $h($title) . '</h1>'
         . '<p class="text-gray-500 text-lg leading-relaxed mb-8">' . $h($lead) . '</p>'
         . '<div class="flex flex-wrap items-center justify-center gap-3">'
         . '<a href="' . $home . '" class="px-7 py-3.5 rounded-full font-black text-base '
         . 'bg-fox-500 hover:bg-fox-600 text-white shadow-fox hover:shadow-fox-lg '
         . 'hover:-translate-y-1 transition-all duration-200">' . $h($back) . '</a>'
         . '<a href="tel:+380954624672" class="px-7 py-3.5 rounded-full font-black text-base '
         . 'bg-white hover:bg-gray-50 text-gray-800 border border-gray-200 shadow-sm '
         . 'hover:shadow-md hover:-translate-y-1 transition-all duration-200">'
         . $h($call) . ' +38 (095) 462-46-72</a>'
         . '</div></main></body></html>';
}

function fail(int $code, string $message, array $extra = []): void
{
    respond($code, ['result' => 'error', 'message' => $message] + $extra);
}

/**
 * Пишемо тільки те, що зламалось. Успішні заявки не пишемо навмисно:
 * персональні дані на диску хостингу — це те, чого краще не мати.
 */
function log_problem(string $line): void
{
    @file_put_contents(private_dir() . '/' . LOG_NAME,
                       date('c') . ' ' . $line . "\n", FILE_APPEND | LOCK_EX);
}

/**
 * Ліміт на адресу. Файл на кожен IP, у ньому — часи останніх спроб.
 * Захист не від зловмисника (обійти тривіально), а від подвійного кліку й
 * від бота, що ганяє форму по колу.
 */
function rate_limited(string $ip): bool
{
    $dir = private_dir() . '/lead-rate';
    if (!is_dir($dir) && !@mkdir($dir, 0700, true) && !is_dir($dir)) {
        return false;
    }
    $file = $dir . '/' . sha1($ip) . '.txt';
    $now  = time();
    $hits = [];
    if (is_readable($file)) {
        foreach (explode("\n", (string) @file_get_contents($file)) as $t) {
            $t = (int) trim($t);
            if ($t > 0 && $now - $t < RATE_WINDOW) {
                $hits[] = $t;
            }
        }
    }
    if (count($hits) >= RATE_MAX) {
        return true;
    }
    $hits[] = $now;
    @file_put_contents($file, implode("\n", $hits), LOCK_EX);
    return false;
}

/** 0671234567, 380671234567, +38 (067) 123-45-67 → +380671234567. */
function normalize_phone(string $raw): ?string
{
    $d = preg_replace('/\D+/', '', $raw) ?? '';
    if (strlen($d) === 12 && str_starts_with($d, '380')) {
        $d = substr($d, 3);
    } elseif (strlen($d) === 11 && str_starts_with($d, '80')) {
        $d = substr($d, 2);
    } elseif (strlen($d) === 10 && $d[0] === '0') {
        $d = substr($d, 1);
    }
    return strlen($d) === 9 ? '+380' . $d : null;
}

function clean(string $s, int $max): string
{
    // Невалідний UTF-8 раніше з'їдав значення цілком: preg_replace з /u повертає
    // null на битих байтах, і ім'я ставало порожнім — людина бачила «Вкажіть
    // імʼя», хоча вписала його. З браузера таке тіло не прийде, але тиха втрата
    // заявки через технічну дрібницю — рівно те, заради чого цей файл і заведений.
    if (!mb_check_encoding($s, 'UTF-8')) {
        $s = mb_convert_encoding($s, 'UTF-8', 'UTF-8');
    }
    $stripped = preg_replace('/[[:cntrl:]]+/u', ' ', $s);
    if ($stripped === null) {
        $stripped = preg_replace('/[[:cntrl:]]+/', ' ', $s) ?? $s;
    }
    return mb_substr(trim($stripped), 0, $max);
}

/**
 * Один POST. Повертає [ok, http-код, тіло-або-помилка].
 * Помилка мережі й відмова сервера розрізняються навмисно: у логу
 * «не достукались» і «відмовили 401» ведуть до різних дій.
 */
function post_to(string $url, string $body, array $headers): array
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $body,
        CURLOPT_HTTPHEADER     => $headers,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,   // Apps Script відповідає редиректом
        CURLOPT_TIMEOUT        => TIMEOUT,
        CURLOPT_CONNECTTIMEOUT => 5,
    ]);
    $out  = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_error($ch);
    curl_close($ch);
    if ($out === false) {
        return [false, 0, $err !== '' ? $err : 'network error'];
    }
    return [$code >= 200 && $code < 300, $code, (string) $out];
}

/**
 * Лист із заявкою на випадок, коли CRM її не взяла.
 *
 * Спершу лист слали звідси завжди — і він не доходив жодного разу. Причина
 * не в коді: Hostinger віддає лист релею, той мовчки викидає листи з
 * неіснуючої скриньки домену, а `mail()` при цьому повертає true. Тобто
 * найгірший різновид відмови — той, що виглядає як успіх, рівно як колись
 * непрозора відповідь Apps Script.
 *
 * Тому звичайний лист тепер шле CRM (прапорець `notify` у форварді): там уже
 * працює SMTP, яким ходять листи сторожа, тобто доставка, перевірена щодня.
 * За цією функцією лишився єдиний випадок, якого CRM закрити не може, — коли
 * вона сама заявку й не прийняла. Тоді лист найкраще, що є, хоч і без
 * гарантій.
 *
 * Результат нічого не вирішує в будь-якому разі: відповідь сторінці дають
 * тільки ті отримувачі, які підтвердження справді повертають.
 *
 * Вигляд листа — той самий, що в мережі (sites/main/server/mailer.js): картка
 * з кольоровою шапкою і таблицею полів, поруч текстова частина для тих, хто
 * HTML не показує. Відмінності дві — колір шапки свій і рядок унизу про те,
 * куди заявка лягла.
 *
 * From мусить бути на своєму домені: SPF домену — include:_spf.mail.hostinger.com,
 * тож лист із чужої адреси не пройде вирівнювання. `-f` ставить ту саму адресу
 * конвертом; там, де хостинг його не дозволяє, `mail()` просто відмовить —
 * тому друга спроба без нього, інакше втратили б лист на рівному місці.
 */
function mail_lead(string $to, array $lead, array $stored): array
{
    // Час явно київський. Сервер Hostinger живе в UTC, і лист із часом на три
    // години назад читається як позавчорашній. У мережі так само — там
    // toLocaleString('uk-UA', { timeZone: 'Europe/Kiev' }).
    $time = (new DateTime('now', new DateTimeZone('Europe/Kyiv')))
            ->format('d.m.Y, H:i:s');

    $name  = $lead['name'];
    $phone = $lead['phone'];
    $age   = $lead['age'] > 0 ? $lead['age'] . ' років' : '—';
    $langs = $lead['lang'] === 'ru' ? 'російська' : 'українська';
    $note  = $stored
        ? 'Записано: ' . implode(', ', $stored)
        : 'УВАГА: заявку не прийняв жоден отримувач — ні CRM, ні таблиця.'
          . ' У панелі її немає, цей лист — єдиний її слід.';

    $text = "Нова заявка — FluentFox\n"
          . "Дитина: {$name}, {$age}\n"
          . "Курс: Англійська мова\n"
          . "Телефон: {$phone}\n"
          . "Мова сторінки: {$langs}\n"
          . "Джерело: fluent-fox.site\n"
          . "Час: {$time}\n"
          . "\n{$note}\n";

    // Ім'я приходить від відвідувача, тож у HTML воно йде тільки екранованим.
    $h = static fn(string $s): string
        => htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
    $row = static fn(string $k, string $v): string
        => '<tr><td style="padding:8px 0;color:#888;width:140px">' . $k
           . '</td><td style="padding:8px 0">' . $v . '</td></tr>';

    $html = '<!DOCTYPE html><html lang="uk"><head><meta charset="UTF-8"/></head>'
          . '<body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">'
          . '<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:10px;'
          . 'overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)">'
          . '<div style="background:#FF6B35;padding:20px 28px">'
          . '<h2 style="color:#fff;margin:0;font-size:18px">🦊 Нова заявка — FluentFox</h2>'
          . '</div><div style="padding:24px 28px"><table style="width:100%;border-collapse:collapse">'
          . $row('Ім\'я дитини', '<strong>' . $h($name) . '</strong>')
          . $row('Вік', $h($age))
          . $row('Курс', 'Англійська мова')
          . $row('Телефон', '<strong><a href="tel:' . $h($phone)
                 . '" style="color:#FF6B35;text-decoration:none">' . $h($phone) . '</a></strong>')
          . $row('Мова сторінки', $langs)
          . $row('Джерело', 'fluent-fox.site')
          . $row('Час', $time)
          . '</table></div>'
          . '<div style="background:' . ($stored ? '#fff7f3' : '#fff0f0')
          . ';padding:16px 28px;border-top:1px solid #eee">'
          . '<p style="margin:0 0 6px;color:#888;font-size:13px">Передзвоніть протягом 30 хвилин 📞</p>'
          . '<p style="margin:0;color:' . ($stored ? '#888' : '#c0392b')
          . ';font-size:13px">' . $h($note) . '</p>'
          . '</div></div></body></html>';

    // Тема з кирилицею мусить бути закодована, інакше поштовик покаже або
    // питальники, або сам заголовок як текст. Вигляд теми — як у мережі:
    // «📩 [джерело] Нова заявка: ім'я — курс».
    $subject = '=?UTF-8?B?' . base64_encode(
        '📩 [fluent-fox.site] Нова заявка: ' . $name . ' — Англійська мова'
    ) . '?=';

    $bound   = 'ff-' . bin2hex(random_bytes(8));
    $headers = implode("\r\n", [
        'From: FluentFox <zayavky@fluent-fox.site>',
        'MIME-Version: 1.0',
        'Content-Type: multipart/alternative; boundary="' . $bound . '"',
    ]);
    $body = "--{$bound}\r\n"
          . "Content-Type: text/plain; charset=utf-8\r\n"
          . "Content-Transfer-Encoding: 8bit\r\n\r\n"
          . str_replace("\n", "\r\n", $text) . "\r\n"
          . "--{$bound}\r\n"
          . "Content-Type: text/html; charset=utf-8\r\n"
          . "Content-Transfer-Encoding: 8bit\r\n\r\n"
          . $html . "\r\n"
          . "--{$bound}--\r\n";

    $ok = @mail($to, $subject, $body, $headers, '-fzayavky@fluent-fox.site');
    if (!$ok) {
        $ok = @mail($to, $subject, $body, $headers);
    }
    // Причина відмови — єдине, що тут узагалі можна дізнатись: `mail()` сам
    // повертає лише true/false, а текст лишається в останній помилці PHP.
    // Без нього «лист не дійшов» нерозрізненне: чи то PHP відмовив, чи то
    // лист прийняли й викинули далі — а це різні поломки й різні починки.
    $err = $ok ? null : (error_get_last()['message'] ?? 'mail() повернув false без помилки');
    return [$ok, $err];
}

// ── Проба канарейки ─────────────────────────────────────────────────────────
// GET сюди шле сторож доставки — питає, чи знає цей сайт про канарейку.
// Питання не формальне: якщо деплой не доїхав і код тут старий, заголовок
// x-canary буде проігноровано, і нічна перевірка заведе в CRM сміттєвий лід.
// Тому сторож спершу питає, і лише отримавши відповідь, шле заявку.
// Секрету проба не потребує й нічого про нього не повідомляє.

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'GET') {
    respond(200, ['canary' => true, 'probe' => true]);
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    fail(405, 'Method not allowed');
}

// ── Конфіг ──────────────────────────────────────────────────────────────────

$config_path = private_dir() . '/lead-config.php';
if (!is_readable($config_path)) {
    // Виразна відмова, а не тиша: інакше сторінка показала б людині помилку,
    // а причину довелося б шукати вручну.
    log_problem('CONFIG MISSING ' . $config_path);
    fail(503, 'Приймач заявок не налаштований. Зателефонуйте нам, будь ласка.',
         ['reason' => 'config_missing']);
}
$config = require $config_path;

// ── Заявка сторожа ──────────────────────────────────────────────────────────
// Правило дослівно те саме, що в server/canary.js мережі: запит із заголовком
// x-canary НЕ створює заявку НІКОЛИ. Не збігся секрет або його не задано —
// 503 і вихід. Інакше сторож, що потрапив на сайт із ненастроєним секретом,
// щоночі мовчки складав би в базу сміттєвий лід.

$is_canary = isset($_SERVER[CANARY_HEADER]);
if ($is_canary) {
    $secret = (string) ($config['canary_token'] ?? '');
    if (strlen($secret) < CANARY_MIN_LEN
        || !hash_equals($secret, (string) $_SERVER[CANARY_HEADER])) {
        respond(503, [
            'canary' => false,
            'error'  => 'canary_token не заданий на сайті або не збігся',
        ]);
    }
}

// Ліміт канарейки не стосується: вона ходить раз на добу й не повинна
// з'їдати квоту живих відвідувачів, а живий відвідувач — її.
$ip = (string) ($_SERVER['HTTP_CF_CONNECTING_IP'] ?? $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0');
if (!$is_canary && rate_limited($ip)) {
    fail(429, 'Забагато спроб. Спробуйте за 15 хвилин або зателефонуйте нам.');
}

// ── Розбір заявки ───────────────────────────────────────────────────────────

$name  = clean((string) ($_POST['name'] ?? ''), 120);
$phone = normalize_phone((string) ($_POST['phone'] ?? ''));
$age   = (int) ($_POST['childAge'] ?? 0);
$lang  = ((string) ($_POST['lang'] ?? 'uk')) === 'ru' ? 'ru' : 'uk';
// Без запасного 'group'. Поля формату на сторінці немає жодного, тож запасне
// значення означало не «обрали групу», а «ніхто нічого не обирав» — і саме
// воно роками лягало в нотатки кожної заявки рядком «формат: group», ніби це
// вибір батьків. Порожній рядок нижче просто випадає з нотаток.
$fmt   = clean((string) ($_POST['format'] ?? ''), 40);

if (mb_strlen($name) < 2) {
    fail(400, 'Вкажіть імʼя (мінімум 2 символи).');
}
if ($phone === null) {
    fail(400, 'Невірний формат телефону.');
}
if ($age < 3 || $age > 99) {
    $age = 0;
}

// ── Отримувач 1: CRM ────────────────────────────────────────────────────────
// Контракт той самий, яким користуються всі шістнадцять сайтів мережі:
// POST /api/leads/admin з адмін-токеном у заголовку. Поле source лишає слід
// походження — у панелі заявка позначена як FluentFox, а не як заявка хаба.

$crm_url = (string) ($config['crm_url'] ?? 'https://mycomputer.education/api/leads/admin');
$crm     = ['configured' => !empty($config['crm_token']), 'reached' => false, 'accepted' => false];
$crm_ok  = false;

if ($crm['configured']) {
    $payload = [
        'child_name' => $name,
        'phone'      => $phone,
        'course'     => 'Англійська мова (FluentFox)',
        'source'     => 'fluent-fox.site',
        // Хай CRM сама надішле лист про заявку. Своєї відправки в цього сайту
        // немає: Hostinger віддає лист релею й той тихо викидає його, бо
        // скриньки на домені немає, — а `mail()` при цьому повертає true, тож
        // зі свого боку все виглядає успішним. У CRM для цього вже працює той
        // самий SMTP, яким ходять листи сторожа.
        //
        // Прапорець, а не типова поведінка маршруту: сайти мережі шлють листи
        // самі, і ввімкнути його для всіх означало б задвоїти їм пошту.
        'notify'     => true,
        'notes'      => 'Заявка з fluent-fox.site · пробний урок'
                        . ($fmt !== '' ? ' · формат: ' . $fmt : '')
                        . ' · мова сторінки: ' . $lang,
    ];
    if ($age > 0) {
        $payload['age'] = $age;
    }

    $headers = ['Content-Type: application/json', 'x-admin-token: ' . $config['crm_token']];
    if ($is_canary) {
        // Той самий заголовок передається далі: CRM його впізнає й теж нічого
        // не запише. Форвард при цьому справжній — перевіряється саме він.
        $headers[] = 'x-canary: ' . $_SERVER[CANARY_HEADER];
    }

    $started = microtime(true);
    [$crm_ok, $code, $body] = post_to(
        $crm_url,
        json_encode($payload, JSON_UNESCAPED_UNICODE) ?: '{}',
        $headers
    );
    $crm['reached'] = $code > 0;
    $crm['status']  = $code;
    $crm['ms']      = (int) round((microtime(true) - $started) * 1000);

    if ($is_canary) {
        // Прийнято — лише за явним підтвердженням CRM. Двохсотка від чужої
        // заглушки чи сторінки-редиректа не має читатись як «доставка жива».
        $json = json_decode($body, true);
        $crm['accepted'] = is_array($json)
                           && ($json['canary'] ?? null) === true
                           && ($json['accepted'] ?? null) === true;
        if (!$crm['accepted']) {
            $crm['error'] = mb_substr(is_array($json) && isset($json['error'])
                                      ? (string) $json['error'] : $body, 0, 200);
        }
    } else {
        $crm['accepted'] = $crm_ok;
        if (!$crm_ok) {
            $crm['error'] = mb_substr($body, 0, 200);
            log_problem(sprintf('CRM FAIL http=%d %s | %s', $code, substr($body, 0, 300), $phone));
        }
    }
} else {
    $crm['error'] = 'crm_token не заданий у lead-config.php';
    if (!$is_canary) {
        log_problem('CRM SKIP: ' . $crm['error']);
    }
}

// Далі — запис. Канарейці сюди не можна: усе, що вона мала перевірити (шлях
// живий, токен приймають, CRM відповідає), уже позаду.
if ($is_canary) {
    respond(200, ['canary' => true, 'written' => false, 'crm' => $crm]);
}

// ── Отримувач 2: Google-таблиця ─────────────────────────────────────────────
// Дубль на час переходу. Коли CRM відпрацює місяць без збоїв — цей блок і
// адресу в конфізі можна прибрати одним рухом.

$sheet_ok = false;
if (!empty($config['sheet_url'])) {
    [$ok, $code, $body] = post_to((string) $config['sheet_url'], http_build_query([
        'name'      => $name,
        'phone'     => $phone,
        'childAge'  => $age > 0 ? (string) $age : '',
        'format'    => $fmt,
        'lang'      => $lang,
        'timestamp' => date('d.m.Y, H:i:s'),
    ]), ['Content-Type: application/x-www-form-urlencoded']);

    // Apps Script уміє відповісти 200 і власною сторінкою помилки, тому
    // самого коду замало — дивимось у тіло.
    $sheet_ok = $ok && str_contains($body, 'success');
    if (!$sheet_ok) {
        log_problem(sprintf('SHEET FAIL http=%d %s | %s', $code, substr($body, 0, 300), $phone));
    }
}

// ── Останній слід: лист звідси, коли CRM заявку не взяла ────────────────────
// Звичайний лист про заявку шле сама CRM — прапорець `notify` вище. Тут
// лишився один-єдиний випадок, якого CRM закрити не може: вона ж заявку й не
// прийняла. Тоді лист — єдине, де заявка взагалі існує, і рядок «УВАГА» в
// тілі каже про це прямо. Рівно так було 14.09.2026: CRM тричі відповіла 401,
// таблиця заявку взяла, відвідувач побачив «прийнято», а дізнатись про
// розбіжність не було звідки.
//
// Надія на цей лист слабка: Hostinger віддає його релею, той тихо викидає
// листи з неіснуючої скриньки домену, а `mail()` усе одно повертає true.
// Але коштує він нічого, а поруч у лог лягає рядок MAIL FAIL — і це вже
// не мовчання.

$notify = trim((string) ($config['notify_email'] ?? ''));
if ($notify !== '' && !$crm_ok) {
    // Перелік того, куди заявка таки лягла, — тут це щонайбільше таблиця:
    // CRM сюди не потрапляє за визначенням, бо блок працює лише тоді, коли
    // вона заявку й не взяла.
    [$sent, $mail_err] = mail_lead($notify, [
        'name'  => $name,
        'phone' => $phone,
        'age'   => $age,
        'lang'  => $lang,
    ], $sheet_ok ? ['Google-таблиця'] : []);
    if (!$sent) {
        log_problem('MAIL FAIL ' . $notify . ' | ' . $phone . ' | ' . $mail_err);
    }
}

// ── Відповідь ───────────────────────────────────────────────────────────────
// Успіх — якщо заявку прийняв хоч один отримувач: вона не втрачена, і просити
// людину надіслати ще раз означало б завести дублікат. Якщо не прийняв ніхто,
// відповідаємо помилкою чесно — форма покаже червоний блок і телефон.

if ($crm_ok || $sheet_ok) {
    respond(200, [
        'result' => 'success',
        'stored' => array_values(array_filter([
            $crm_ok ? 'crm' : null,
            $sheet_ok ? 'sheet' : null,
        ])),
    ]);
}

log_problem('LOST ' . $name . ' ' . $phone . ' — не прийняв ніхто');
fail(502, 'Не вдалося передати заявку. Зателефонуйте нам, будь ласка.');
