<?php
/**
 * Створення рахунку на оплату: WayForPay і MonoPay.
 *
 * Навіщо цей файл, якщо в мережі вже є робоча інтеграція. Вона є — у
 * `my_computer_new/sites/*/server/wayforpay.js` і `server/mono-pay.js`, — але
 * перенести її сюди як є не можна: там Node за LiteSpeed-проксі, а FluentFox
 * це статика на Hostinger, де з динаміки живе лише PHP. Тому тут той самий
 * протокол, переписаний на PHP, а не інший спосіб оплати.
 *
 * Чому взагалі потрібен сервер, а не кнопка прямо на сторінці. Обидва шлюзи
 * вимагають секрет: WayForPay підписує запит HMAC-MD5 на merchantSecretKey,
 * MonoPay ходить з `X-Token` мерчанта. Покласти будь-що з цього в браузер
 * означає віддати можливість створювати рахунки від імені школи кожному, хто
 * відкриє «Переглянути код».
 *
 * Що робить: приймає суму й призначення, створює рахунок на боці шлюзу й
 * повертає адресу його сторінки оплати. Далі браузер просто переходить туди —
 * ні iframe, ні віджета, тому CSP у .htaccess правити не довелось: перехід за
 * адресою політика не обмежує, а `fetch` іде на свій же домен.
 *
 * Секрети в репозиторій не потрапляють. Вони лежать у pay-config.php на рівень
 * вище за public_html — rsync деплою чистить тільки public_html, тож файл
 * переживає викатки. Зразок для ручної установки — api/pay-config.sample.php.
 * Немає конфіга — ендпоінт відповідає 503 і нічого не створює.
 */

declare(strict_types=1);

header('Cache-Control: no-store');
header('Content-Type: application/json; charset=utf-8');

const LOG_NAME    = 'pay-errors.log';
const RATE_MAX    = 15;           // рахунків з однієї адреси
const RATE_WINDOW = 15 * 60;      // за 15 хвилин
const TIMEOUT     = 10;           // секунд на шлюз
const AMOUNT_MIN  = 1.0;
const AMOUNT_MAX  = 100000.0;     // та сама межа, що в мережі
const SITE_URL    = 'https://fluent-fox.site';

/** Каталог поруч із pay-config.php: на рівень вище за public_html. */
function private_dir(): string
{
    return dirname(__DIR__, 2);
}

function log_problem(string $line): void
{
    @file_put_contents(private_dir() . '/' . LOG_NAME,
                       date('c') . ' ' . $line . "\n", FILE_APPEND | LOCK_EX);
}

function respond(int $code, array $payload): void
{
    http_response_code($code);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE);
    exit;
}

/**
 * Повідомлення для людини й рядок для лога — різні речі. Відвідувачу нема
 * чого знати, що саме відповів шлюз; у лог навпаки треба все.
 */
function fail(int $code, string $human, string $detail = ''): void
{
    if ($detail !== '') {
        log_problem($detail);
    }
    respond($code, ['error' => $human]);
}

/**
 * Ліміт на адресу — той самий підхід, що в lead.php: файл на IP з часами
 * спроб. Захист не від зловмисника, а від подвійного кліку й бота, який
 * ганяє форму по колу, залишаючи за собою хвіст непотрібних рахунків.
 */
function rate_limited(string $ip): bool
{
    $dir = private_dir() . '/pay-rate';
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

function clean(string $s, int $max): string
{
    $s = preg_replace('/[\x00-\x1F\x7F]/u', ' ', $s) ?? '';
    $s = trim(preg_replace('/\s+/u', ' ', $s) ?? '');
    return function_exists('mb_substr') ? mb_substr($s, 0, $max) : substr($s, 0, $max);
}

/** POST з тілом і заголовками. Редиректи не слідуємо: шлюзи їх не шлють. */
function post_json(string $url, string $body, array $headers): array
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $body,
        CURLOPT_HTTPHEADER     => $headers,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => TIMEOUT,
        CURLOPT_CONNECTTIMEOUT => 5,
    ]);
    $out  = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_error($ch);
    curl_close($ch);
    if ($out === false) {
        return [0, '', $err !== '' ? $err : 'network error'];
    }
    return [$code, (string) $out, ''];
}

/**
 * Підпис WayForPay: HMAC-MD5 на merchantSecretKey по полях, з'єднаних «;».
 * Порядок полів і їхній склад — з документації шлюзу; він же відтворений у
 * `sign()` в my_computer_new/sites/*/server/wayforpay.js, і зійтися вони
 * зобов'язані символ у символ: акаунт мерчанта той самий.
 */
function wfp_sign(string $secret, array $fields): string
{
    return hash_hmac('md5', implode(';', $fields), $secret);
}

/**
 * Рахунок WayForPay. `merchantDomainName` — домен, з якого йде оплата; він
 * має бути заведений у кабінеті мерчанта, інакше шлюз відкине підпис як
 * чужий, хоч ключ і правильний.
 */
function wfp_invoice(array $cfg, float $amount, string $description, string $order_ref): array
{
    $merchant = (string) ($cfg['wfp_merchant'] ?? '');
    $secret   = (string) ($cfg['wfp_secret'] ?? '');
    if ($merchant === '' || $secret === '') {
        return [null, 'wfp_merchant або wfp_secret не задані в pay-config.php'];
    }

    $domain = (string) parse_url(SITE_URL, PHP_URL_HOST);
    $date   = time();
    $sum    = number_format($amount, 2, '.', '');

    $params = [
        'transactionType'    => 'CREATE_INVOICE',
        'merchantAccount'    => $merchant,
        'merchantDomainName' => $domain,
        'merchantSignature'  => wfp_sign($secret, [
            $merchant, $domain, $order_ref, (string) $date, $sum, 'UAH',
            $description, '1', $sum,
        ]),
        'apiVersion'         => '1',
        'language'           => 'UA',
        'returnUrl'          => SITE_URL . '/oplata-uspih.html',
        // serviceUrl немає навмисно. Вебхук потрібен тому, хто записує платіж
        // у себе — у мережі це робить база на сервері. Тут писати нікуди:
        // сайт статичний. А вебхук, який відповідає не так, як чекає шлюз,
        // змушує його повторювати виклик годинами, тож краще без нього:
        // платіж видно в кабінеті мерчанта, і він приходить листом.
        'orderReference'     => $order_ref,
        'orderDate'          => $date,
        'amount'             => $sum,
        'currency'           => 'UAH',
        'productName'        => [$description],
        'productCount'       => ['1'],
        'productPrice'       => [$sum],
    ];

    [$code, $body, $err] = post_json(
        'https://api.wayforpay.com/api',
        (string) json_encode($params, JSON_UNESCAPED_UNICODE),
        ['Content-Type: application/json']
    );
    if ($err !== '') {
        return [null, 'WayForPay: ' . $err];
    }
    $json = json_decode($body, true);
    if (is_array($json) && !empty($json['invoiceUrl'])) {
        return [(string) $json['invoiceUrl'], ''];
    }
    $reason = is_array($json)
        ? (string) ($json['reason'] ?? $json['reasonCode'] ?? 'без причини')
        : 'відповідь не розібралась';
    return [null, sprintf('WayForPay %d: %s', $code, $reason)];
}

/**
 * Рахунок MonoPay. Підпису тут немає — автентифікує заголовок `X-Token`,
 * тому й тримати цей токен треба так само суворо, як ключ WayForPay.
 * Сума в копійках, ccy 980 — гривня.
 */
function mono_invoice(array $cfg, float $amount, string $description): array
{
    $token = (string) ($cfg['mono_token'] ?? '');
    if ($token === '') {
        return [null, 'mono_token не заданий у pay-config.php'];
    }

    $payload = [
        'amount'           => (int) round($amount * 100),
        'ccy'              => 980,
        'merchantPaymInfo' => ['destination' => $description, 'comment' => $description],
        'redirectUrl'      => SITE_URL . '/oplata-uspih.html',
        // webHookUrl — з тієї ж причини, що й serviceUrl вище.
        'validity'         => 3600,
    ];

    [$code, $body, $err] = post_json(
        'https://api.monobank.ua/api/merchant/invoice/create',
        (string) json_encode($payload, JSON_UNESCAPED_UNICODE),
        ['Content-Type: application/json', 'X-Token: ' . $token]
    );
    if ($err !== '') {
        return [null, 'MonoPay: ' . $err];
    }
    $json = json_decode($body, true);
    if (is_array($json) && !empty($json['pageUrl'])) {
        return [(string) $json['pageUrl'], ''];
    }
    $reason = is_array($json) ? (string) ($json['errText'] ?? 'без причини') : 'відповідь не розібралась';
    return [null, sprintf('MonoPay %d: %s', $code, $reason)];
}


// ── обробка запиту ───────────────────────────────────────────────────────────

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    respond(405, ['error' => 'Метод не підтримується']);
}

$raw   = (string) file_get_contents('php://input');
$input = json_decode($raw, true);
if (!is_array($input)) {
    $input = $_POST;                       // форма без JS постить сюди ж
}

$provider = (string) ($input['provider'] ?? '');
if ($provider !== 'wfp' && $provider !== 'mono') {
    respond(400, ['error' => 'Невідомий спосіб оплати']);
}

$amount = (float) str_replace([' ', ','], ['', '.'], (string) ($input['amount'] ?? ''));
if ($amount < AMOUNT_MIN || $amount > AMOUNT_MAX) {
    respond(400, ['error' => 'Введіть суму від 1 до 100 000 грн']);
}

$description = clean((string) ($input['description'] ?? ''), 120);
if ($description === '') {
    $description = 'Оплата навчання FluentFox';
}

$ip = (string) ($_SERVER['REMOTE_ADDR'] ?? '0.0.0.0');
if (rate_limited($ip)) {
    respond(429, ['error' => 'Забагато спроб. Спробуйте за кілька хвилин.']);
}

$config_path = private_dir() . '/pay-config.php';
if (!is_readable($config_path)) {
    fail(503, 'Оплата на сайті тимчасово недоступна. Напишіть нам — надішлемо рахунок.',
         'немає pay-config.php: ' . $config_path);
}
$cfg = require $config_path;
if (!is_array($cfg)) {
    fail(503, 'Оплата на сайті тимчасово недоступна. Напишіть нам — надішлемо рахунок.',
         'pay-config.php не повернув масив');
}

// Номер замовлення має бути унікальним у межах мерчанта: якщо школа коли-небудь
// ділитиме акаунт із сусіднім сайтом, префікс `ff-` не дасть їм зіткнутися.
$order_ref = 'ff-' . date('Ymd-His') . '-' . bin2hex(random_bytes(3));

[$url, $error] = $provider === 'wfp'
    ? wfp_invoice($cfg, $amount, $description, $order_ref)
    : mono_invoice($cfg, $amount, $description);

if ($url === null) {
    fail(502, 'Не вдалося створити рахунок. Спробуйте ще раз або напишіть нам.', $error);
}

respond(200, ['pageUrl' => $url, 'orderReference' => $order_ref]);
