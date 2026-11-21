<?php
// php tools/tests/meta-capi.test.php — збірка тіла Conversions API для
// api/lead.php без жодного запиту в Meta. Лежить у tools/, бо tools/ деплой
// на хостинг не везе (у public_html тест був би доступний по HTTP).
declare(strict_types=1);

require __DIR__ . '/../../api/meta-capi.php';

$fails = 0;
function check(string $name, bool $ok): void
{
    global $fails;
    echo ($ok ? 'ok   ' : 'FAIL ') . $name . "\n";
    if (!$ok) {
        $fails++;
    }
}

check('0671234567 → 380671234567', meta_phone_digits('0671234567') === '380671234567');
check('+380671234567 → 380671234567', meta_phone_digits('+380671234567') === '380671234567');
check('80671234567 → 380671234567', meta_phone_digits('80671234567') === '380671234567');
check('671234567 → 380671234567', meta_phone_digits('671234567') === '380671234567');

$meta = meta_parse(json_encode([
    'event_id' => 'e-1', 'consent' => 'all', 'fbp' => 'fb.1.1.2',
    'fbc' => 'fb.1.1700000000000.abc', 'url' => 'https://fluent-fox.site/lp/probnyi-urok/', 'evil' => 'x',
]));
check('parseMeta відкидає зайве', !isset($meta['evil']) && $meta['event_id'] === 'e-1');
check('parseMeta: битий JSON → []', meta_parse('{oops') === []);

$b = meta_build_body($meta, [
    'phone' => '+380671234567', 'email' => ' Mail@Example.COM ', 'content_name' => 'trial_lesson',
    'ip' => '1.2.3.4', 'ua' => 'UA', 'time' => 1763700000,
]);
$ev = $b['data'][0] ?? [];
check('event_name/time/id/source', ($ev['event_name'] ?? '') === 'Lead' && $ev['event_time'] === 1763700000
      && $ev['event_id'] === 'e-1' && $ev['action_source'] === 'website');
check('event_source_url', $ev['event_source_url'] === 'https://fluent-fox.site/lp/probnyi-urok/');
check('ph = sha256(380…)', $ev['user_data']['ph'] === [hash('sha256', '380671234567')]);
check('em = sha256(lower(trim))', $ev['user_data']['em'] === [hash('sha256', 'mail@example.com')]);
check('ip/ua/fbp/fbc', $ev['user_data']['client_ip_address'] === '1.2.3.4' && $ev['user_data']['client_user_agent'] === 'UA'
      && $ev['user_data']['fbp'] === 'fb.1.1.2' && $ev['user_data']['fbc'] === 'fb.1.1700000000000.abc');
check('custom_data.content_name', $ev['custom_data'] === ['content_name' => 'trial_lesson']);
check('без test_event_code, якщо не задано', !isset($b['test_event_code']));

$b2 = meta_build_body(['event_id' => 'e-2', 'consent' => 'all'], ['phone' => '0671234567'], 'TEST1');
check('порожні поля не передаються', array_keys($b2['data'][0]['user_data']) === ['ph']
      && !isset($b2['data'][0]['event_source_url']) && !isset($b2['data'][0]['custom_data']));
check('test_event_code додається', $b2['test_event_code'] === 'TEST1');

check('без згоди — null', meta_build_body(['event_id' => 'e', 'consent' => 'necessary'], ['phone' => '0671234567']) === null);
check('порожня згода — null', meta_build_body(['event_id' => 'e'], ['phone' => '0671234567']) === null);
check('без event_id — null', meta_build_body(['consent' => 'all'], ['phone' => '0671234567']) === null);

check('без токена — вимкнено', meta_enabled(['meta_pixel_id' => '931791603129774', 'meta_capi_token' => '']) === false);
check('без пікселя — вимкнено', meta_enabled(['meta_pixel_id' => '', 'meta_capi_token' => 't']) === false);
check('з токеном і пікселем — увімкнено', meta_enabled(['meta_pixel_id' => '931791603129774', 'meta_capi_token' => 't']) === true);

echo $fails ? "\n$fails FAIL\n" : "\nвсі перевірки пройшли\n";
exit($fails ? 1 : 0);
