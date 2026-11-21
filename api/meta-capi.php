<?php
/**
 * Серверна подія Lead у Meta (Conversions API) — для api/lead.php.
 *
 * Контракт мережі від 21.11.2026: піксель у браузері + Lead із сервера з тим
 * самим event_id, щоб Meta склеїла дві події в одну. Сервер бачить заявку
 * навіть тоді, коли браузерну подію з'їв блокувальник реклами чи iOS.
 *
 * Правила:
 *   • тільки за згодою: meta.consent === 'all', інакше в Meta нічого;
 *   • немає токена чи id пікселя в lead-config.php — модуль вимкнений;
 *   • заявка ніколи не падає через Meta: відправка йде ПІСЛЯ відповіді
 *     відвідувачу (lead.php реєструє її shutdown-функцією), таймаут 5 с,
 *     помилка — рядок у lead-errors.log;
 *   • телефон і пошта — лише SHA-256 від нормалізованого значення.
 *
 * Файл лежить у public_html/api, тож його можна запросити по HTTP: тоді він
 * лише оголошує функції й нічого не виводить. Тест — tools/tests/meta-capi.test.php.
 */

declare(strict_types=1);

const META_GRAPH_VERSION = 'v23.0';
const META_TIMEOUT       = 5;

/** Цифри номера в E.164 без «+»: 0671234567 / +380671234567 → 380671234567. */
function meta_phone_digits(string $raw): string
{
    $d = preg_replace('/\D+/', '', $raw) ?? '';
    if (strlen($d) === 10 && $d[0] === '0') {
        return '38' . $d;
    }
    if (strlen($d) === 9) {
        return '380' . $d;
    }
    if (strlen($d) === 11 && str_starts_with($d, '80')) {
        return '3' . $d;
    }
    return $d;
}

/** Розбір поля `meta` з тіла заявки (JSON-рядок). Зайве відкидається. */
function meta_parse(string $raw): array
{
    if ($raw === '' || strlen($raw) > 4000) {
        return [];
    }
    $j = json_decode($raw, true);
    if (!is_array($j)) {
        return [];
    }
    $out = [];
    foreach (['event_id' => 100, 'fbp' => 300, 'fbc' => 600, 'fbclid' => 500,
              'consent' => 20, 'url' => 1000] as $k => $max) {
        if (isset($j[$k]) && is_string($j[$k])) {
            $v = trim(preg_replace('/[[:cntrl:]]+/', '', $j[$k]) ?? '');
            if ($v !== '' && strlen($v) <= $max) {
                $out[$k] = $v;
            }
        }
    }
    return $out;
}

/**
 * Тіло запиту в Graph API або null, якщо слати не можна (немає згоди,
 * немає event_id). Поля без значення не передаються.
 *
 * $lead: phone, email?, content_name, ip, ua, time?
 */
function meta_build_body(array $meta, array $lead, string $test_code = ''): ?array
{
    if (($meta['consent'] ?? '') !== 'all' || empty($meta['event_id'])) {
        return null;
    }
    $user = [];
    $ph = meta_phone_digits((string) ($lead['phone'] ?? ''));
    if ($ph !== '') {
        $user['ph'] = [hash('sha256', $ph)];
    }
    $em = strtolower(trim((string) ($lead['email'] ?? '')));
    if ($em !== '') {
        $user['em'] = [hash('sha256', $em)];
    }
    foreach (['client_ip_address' => $lead['ip'] ?? '', 'client_user_agent' => $lead['ua'] ?? '',
              'fbp' => $meta['fbp'] ?? '', 'fbc' => $meta['fbc'] ?? ''] as $k => $v) {
        if ((string) $v !== '') {
            $user[$k] = (string) $v;
        }
    }
    $event = [
        'event_name'    => 'Lead',
        'event_time'    => (int) ($lead['time'] ?? time()),
        'event_id'      => $meta['event_id'],
        'action_source' => 'website',
    ];
    if (!empty($meta['url'])) {
        $event['event_source_url'] = $meta['url'];
    }
    $event['user_data'] = $user;
    if (!empty($lead['content_name'])) {
        $event['custom_data'] = ['content_name' => (string) $lead['content_name']];
    }
    $body = ['data' => [$event]];
    if ($test_code !== '') {
        $body['test_event_code'] = $test_code;
    }
    return $body;
}

/** Чи ввімкнений модуль за конфігом. */
function meta_enabled(array $config): bool
{
    return trim((string) ($config['meta_capi_token'] ?? '')) !== ''
        && preg_match('/^\d{5,20}$/', trim((string) ($config['meta_pixel_id'] ?? ''))) === 1;
}

/** Один POST у Graph API. Повертає [ok, http-код, тіло-або-помилка]. */
function meta_send(array $config, array $body): array
{
    $url = sprintf('https://graph.facebook.com/%s/%s/events?access_token=%s',
                   META_GRAPH_VERSION, trim((string) $config['meta_pixel_id']),
                   rawurlencode(trim((string) $config['meta_capi_token'])));
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?: '{}',
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => META_TIMEOUT,
        CURLOPT_CONNECTTIMEOUT => META_TIMEOUT,
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
 * Відпустити відвідувача й лише потім іти в Meta. На LiteSpeed (Hostinger)
 * це litespeed_finish_request(), на php-fpm — fastcgi_finish_request().
 * Якщо немає жодної — відповідь уже виведена, а запит у Meta обмежений 5 с.
 */
function meta_finish_response(): void
{
    if (function_exists('litespeed_finish_request')) {
        litespeed_finish_request();
    } elseif (function_exists('fastcgi_finish_request')) {
        fastcgi_finish_request();
    } else {
        @ob_flush();
        @flush();
    }
}
