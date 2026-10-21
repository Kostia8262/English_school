/* Піксель Meta — базовий код і PageView.

   Чому окремий файл, а не вставка в <head> кожного шаблону, як радить
   майстер у Events Manager. Сторінки народжуються в трьох генераторах, і
   один з них — tools/landing/build.py — складає <head> через f-рядок. Код
   пікселя рясніє фігурними дужками (`{if(f.fbq)return;...}`), а в f-рядку
   кожну з них довелося б подвоювати. Одна пропущена — і збірка падає або,
   гірше, мовчки псує розмітку. Файл збоку не має цієї проблеми взагалі:
   у шаблонах лишається один тег <script src>, де дужок немає.

   Друга причина — політика CSP. 'self' для script-src уже дозволений, тож
   сам файл проходить без правок; домен connect.facebook.net потрібен лише
   тому, що fbevents.js підвантажується звідти (див. .htaccess).

   Подію Lead цей файл не шле: вона живе в js/lead.js, у тій самій точці, де
   стоїть generate_lead — ПІСЛЯ підтвердження від сервера. Стріляти Lead по
   кліку означало б учити оптимізацію Meta на заявках, яких не було. */
(function () {
  'use strict';

  /* eslint-disable */
  !function(f,b,e,v,n,t,s)
  {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
  n.callMethod.apply(n,arguments):n.queue.push(arguments)};
  if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
  n.queue=[];t=b.createElement(e);t.async=!0;
  t.src=v;s=b.getElementsByTagName(e)[0];
  s.parentNode.insertBefore(t,s)}(window, document,'script',
  'https://connect.facebook.net/en_US/fbevents.js');
  /* eslint-enable */

  fbq('init', '931791603129774');
  fbq('track', 'PageView');
})();
