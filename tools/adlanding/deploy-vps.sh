#!/bin/bash
# Викатка рекламного лендінга lp.fluent-fox.site на VPS мережі.
#
# Навіщо окремий скрипт. Лендінг живе не на Hostinger (там CDN 22.10.2026
# увімкнув «Checking your browser»), а на VPS: pm2 `ff-landing`,
# /var/www/ff-landing, порт 3030. deploy.yml його не чіпає. До 20.11.2026
# файли туди носили руками, і копія відстала від репозиторію на місяць:
# стара знижка «15% на другу дитину», старий підвал, без блоку «Дякуємо!» і
# без css/fonts.css, на який посилаються юридичні сторінки.
#
# Що робить:
#   1. збирає лендінг (python3 tools/adlanding/build.py) і зупиняється, якщо
#      після збірки lp/probnyi-urok/index.html відрізняється від закоміченого —
#      викочувати треба те, що лежить у git;
#   2. бере index.html лендінга + offer/privacy/terms.html і ВСІ локальні
#      файли, на які вони посилаються (src/href="/..."), без ?v=;
#   3. rsync у public/ (без --delete: .well-known для certbot живе там же),
#      server.js поруч, `node --check`, перезапуск pm2 ff-landing;
#   4. перевіряє, що GET /api/lead.php відповідає canary:true.
#
# Запуск з кореня репозиторію:  bash tools/adlanding/deploy-vps.sh
set -eu

HOST=root@62.72.21.71
DIR=/var/www/ff-landing
cd "$(git rev-parse --show-toplevel)"

python3 tools/adlanding/build.py >/dev/null
if ! git diff --quiet -- lp/probnyi-urok/index.html; then
  echo "lp/probnyi-urok/index.html після збірки відрізняється від git — спершу закомітьте збірку" >&2
  exit 1
fi

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/public"
cp lp/probnyi-urok/index.html "$STAGE/public/index.html"
PAGES="lp/probnyi-urok/index.html offer.html privacy.html terms.html"
for p in offer.html privacy.html terms.html; do cp "$p" "$STAGE/public/$p"; done

# Локальні посилання сторінок: /css/…, /js/…, /icons/…, /fonts/…, /logo.svg.
# Шрифти тягне ще й css (url(/fonts/…)), тож дивимось і в css-файли.
refs=$(grep -ohE '(src|href)="/[^"/][^"]*"' $PAGES | sed -E 's/^(src|href)="\///; s/[?#].*//; s/"$//' | sort -u)
css=$(echo "$refs" | grep -E '\.css$' || true)
refs="$refs
$(for c in $css; do [ -f "$c" ] && grep -ohE 'url\(/?[^)]+\)' "$c" | sed -E 's/^url\(\/?//; s/\)$//; s/["'\'']//g; s/[?#].*//'; done)
favicon.ico"
for f in $(echo "$refs" | sort -u); do
  [ -f "$f" ] || continue                     # сторінки сайту (/tsiny…) — не файли лендінга
  mkdir -p "$STAGE/public/$(dirname "$f")"
  cp "$f" "$STAGE/public/$f"
done
cp tools/adlanding/server/server.js "$STAGE/server.js"
cp tools/adlanding/server/setup-vhost.sh "$STAGE/setup-vhost.sh"

echo "файли лендінга:"; (cd "$STAGE" && find . -type f | sort | sed 's/^/  /')

rsync -rlptz --chmod=F644,D755 "$STAGE/public/" "$HOST:$DIR/public/"
rsync -rlptz --chmod=F644 "$STAGE/server.js" "$STAGE/setup-vhost.sh" "$HOST:$DIR/"
ssh $HOST "node --check $DIR/server.js && pm2 restart ff-landing --update-env >/dev/null && sleep 1 && curl -s http://127.0.0.1:3030/api/lead.php"
echo
probe=$(curl -s https://lp.fluent-fox.site/api/lead.php)
echo "проба: $probe"
echo "$probe" | grep -q '"canary":true' || { echo "лендінг не відповідає canary:true — сторож його не перевірить" >&2; exit 1; }
