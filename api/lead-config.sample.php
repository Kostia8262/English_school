<?php
/**
 * Зразок конфіга приймача заявок. Сам конфіг у репозиторії не лежить і лежати
 * не повинен — у ньому адмін-токен CRM.
 *
 * Куди класти на хостингу (на рівень вище за public_html, щоб rsync деплою
 * його не зносив і щоб він не віддавався по HTTP):
 *
 *   /home/u260300169/domains/fluent-fox.site/lead-config.php
 *
 * Токен CRM — той самий MAIN_ADMIN_TOKEN, яким користуються сайти мережі:
 *
 *   ssh root@62.72.21.71 "grep '^MAIN_ADMIN_TOKEN' /var/www/mycomputer-new/sites/python/.env"
 *
 * sheet_url можна прибрати, коли CRM відпрацює місяць без збоїв — тоді дубль
 * у Google-таблицю просто перестане робитись.
 */

return [
    'crm_token' => 'ТУТ_MAIN_ADMIN_TOKEN',
    'crm_url'   => 'https://mycomputer.education/api/leads/admin',
    'sheet_url' => 'https://script.google.com/macros/s/AKfycbxAA1T6SIdTeldgSFmT-3HUEfRBUIq7-v79uGBe3UbVnTQBlespZMrsgNQMqmZKCzEGqA/exec',

    // Той самий CANARY_TOKEN, що й у сайтів мережі — інакше сторож
    // доставки не зможе перевірити цей сайт, а не завести сміттєвий лід.
    // Немає — перевірка просто вимкнена, заявки це ніяк не чіпає.
    'canary_token' => '',
];
