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
 * переживає викатки. Зразок конфіга див. у api/lead-config.sample.php.
 */

declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

const LOG_NAME    = 'lead-errors.log';
const RATE_MAX    = 10;          // заявок з однієї адреси
const RATE_WINDOW = 15 * 60;     // за 15 хвилин — та сама норма, що в CRM
const TIMEOUT     = 8;           // секунд на кожного отримувача

/** Каталог поруч із lead-config.php: на рівень вище за public_html. */
function private_dir(): string
{
    return dirname(__DIR__, 2);
}

function fail(int $code, string $message, array $extra = []): void
{
    http_response_code($code);
    echo json_encode(['result' => 'error', 'message' => $message] + $extra,
                     JSON_UNESCAPED_UNICODE);
    exit;
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
    $s = trim(preg_replace('/[\x00-\x1F\x7F]+/u', ' ', $s) ?? '');
    return mb_substr($s, 0, $max);
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

// ── Перевірки запиту ────────────────────────────────────────────────────────

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    fail(405, 'Method not allowed');
}

$config_path = private_dir() . '/lead-config.php';
if (!is_readable($config_path)) {
    // Виразна відмова, а не тиша: інакше сторінка показала б людині помилку,
    // а причину довелося б шукати вручну.
    log_problem('CONFIG MISSING ' . $config_path);
    fail(503, 'Приймач заявок не налаштований. Зателефонуйте нам, будь ласка.',
         ['reason' => 'config_missing']);
}
$config = require $config_path;

$ip = (string) ($_SERVER['HTTP_CF_CONNECTING_IP'] ?? $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0');
if (rate_limited($ip)) {
    fail(429, 'Забагато спроб. Спробуйте за 15 хвилин або зателефонуйте нам.');
}

$name  = clean((string) ($_POST['name'] ?? ''), 120);
$phone = normalize_phone((string) ($_POST['phone'] ?? ''));
$age   = (int) ($_POST['childAge'] ?? 0);
$lang  = ((string) ($_POST['lang'] ?? 'uk')) === 'ru' ? 'ru' : 'uk';
$fmt   = clean((string) ($_POST['format'] ?? 'group'), 40);

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
$crm_ok  = false;

if (!empty($config['crm_token'])) {
    $payload = [
        'child_name' => $name,
        'phone'      => $phone,
        'course'     => 'Англійська мова (FluentFox)',
        'source'     => 'fluent-fox.site',
        'notes'      => 'Заявка з fluent-fox.site · пробний урок'
                        . ($fmt !== '' ? ' · формат: ' . $fmt : '')
                        . ' · мова сторінки: ' . $lang,
    ];
    if ($age > 0) {
        $payload['age'] = $age;
    }

    [$crm_ok, $code, $body] = post_to(
        $crm_url,
        json_encode($payload, JSON_UNESCAPED_UNICODE) ?: '{}',
        ['Content-Type: application/json', 'x-admin-token: ' . $config['crm_token']]
    );

    if (!$crm_ok) {
        log_problem(sprintf('CRM FAIL http=%d %s | %s', $code, substr($body, 0, 300), $phone));
    }
} else {
    log_problem('CRM SKIP: crm_token не заданий у lead-config.php');
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

// ── Відповідь ───────────────────────────────────────────────────────────────
// Успіх — якщо заявку прийняв хоч один отримувач: вона не втрачена, і просити
// людину надіслати ще раз означало б завести дублікат. Якщо не прийняв ніхто,
// відповідаємо помилкою чесно — форма покаже червоний блок і телефон.

if ($crm_ok || $sheet_ok) {
    echo json_encode([
        'result' => 'success',
        'stored' => array_values(array_filter([
            $crm_ok ? 'crm' : null,
            $sheet_ok ? 'sheet' : null,
        ])),
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

log_problem('LOST ' . $name . ' ' . $phone . ' — не прийняв ніхто');
fail(502, 'Не вдалося передати заявку. Зателефонуйте нам, будь ласка.');
