#!/bin/bash
# Підключення lp.fluent-fox.site до OpenLiteSpeed.
#
# Чому окремим скриптом, а не руками: правимо httpd_config.conf — спільний
# файл, від якого залежать усі 16 сайтів мережі. Тому тут бекап із міткою
# часу, перевірка «чи вже додано» (скрипт можна запускати двічі) і зупинка
# на першій же помилці. Нічого не видаляється — тільки дописується.
#
# Запуск:  bash /var/www/ff-landing/setup-vhost.sh
set -euo pipefail

HOST=lp.fluent-fox.site
CONF=/usr/local/lsws/conf/httpd_config.conf
VHDIR=/usr/local/lsws/conf/vhosts/$HOST
ROOT=/var/www/ff-landing

echo "== 1/6. Конфіг віртуального хоста =="
mkdir -p "$VHDIR" "$ROOT/public/.well-known"
cat > "$VHDIR/vhconf.conf" <<'VHEOF'
docRoot                   /var/www/ff-landing/public/

accesslog $SERVER_ROOT/logs/access.log {
  useServer               1
}

index  {
  useServer               0
  indexFiles              index.html
}

extprocessor nodejs-ff-landing {
  type                    proxy
  address                 http://127.0.0.1:3030
  maxConns                100
  pcKeepAliveTimeout      60
  initTimeout             60
  retryTimeout            0
  respBuffer              0
}

context /.well-known/ {
  location                /var/www/ff-landing/public/.well-known/
  allowBrowse             1
  addDefaultCharset       off
}

context / {
  type                    proxy
  handler                 nodejs-ff-landing
  addDefaultCharset       off
}
VHEOF
echo "   готово: $VHDIR/vhconf.conf"

echo "== 2/6. Додаємо хост у спільний конфіг (з бекапом) =="
python3 - "$CONF" "$HOST" <<'PYEOF'
import io, shutil, sys, time
conf, host = sys.argv[1], sys.argv[2]
s = io.open(conf, encoding='utf-8').read()
if host in s:
    print('   вже додано — пропускаємо')
    raise SystemExit(0)
backup = conf + '.bak-' + time.strftime('%Y%m%d-%H%M%S')
shutil.copy2(conf, backup)
print('   бекап: ' + backup)
block = ("\nvirtualhost %s {\n  vhRoot                  %s/\n"
         "  configFile              conf/vhosts/%s/vhconf.conf\n"
         "  allowSymbolLink         1\n  enableScript            1\n"
         "  restrained              0\n}\n") % (host, host, host)
i = s.index('\nlistener ')
s = s[:i] + block + s[i:]
mapline = '\n  map                     %s %s' % (host, host)
out, pos, n = [], 0, 0
while True:
    j = s.find('\nlistener ', pos)
    if j < 0:
        out.append(s[pos:]); break
    end = s.index('\n}', j)
    out.append(s[pos:end]); out.append(mapline); n += 1
    pos = end
io.open(conf, 'w', encoding='utf-8', newline='').write(''.join(out))
print('   додано у %d listener(ів)' % n)
PYEOF

echo "== 3/6. Перезапуск OpenLiteSpeed =="
/usr/local/lsws/bin/lswsctrl restart >/dev/null
sleep 3
code=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $HOST" http://127.0.0.1/ || true)
echo "   відповідь по HTTP: $code"
if [ "$code" != "200" ]; then
  echo "   !! Хост не віддає 200. Сайти мережі перевір окремо; бекап конфіга лежить поряд."
  exit 1
fi

echo "== 4/6. Сертифікат =="
if [ -d "/etc/letsencrypt/live/$HOST" ]; then
  echo "   сертифікат уже є"
else
  certbot certonly --webroot -w "$ROOT/public" -d "$HOST" --non-interactive --agree-tos --register-unsafely-without-email --quiet
  echo "   випущено"
fi

echo "== 5/6. Вмикаємо HTTPS для хоста =="
if ! grep -q 'vhssl' "$VHDIR/vhconf.conf"; then
  cat >> "$VHDIR/vhconf.conf" <<SSLEOF

vhssl  {
  keyFile                 /etc/letsencrypt/live/$HOST/privkey.pem
  certFile                /etc/letsencrypt/live/$HOST/fullchain.pem
  certChain               1
}
SSLEOF
  /usr/local/lsws/bin/lswsctrl restart >/dev/null
  sleep 3
fi

echo "== 6/6. Перевірка =="
echo -n "   https://$HOST/ -> "
curl -s -o /dev/null -w '%{http_code}\n' "https://$HOST/" || true
echo -n "   приймання заявок -> "
curl -s "https://$HOST/api/lead.php" || true
echo
echo "Готово."
