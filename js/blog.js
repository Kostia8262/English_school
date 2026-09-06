/* Вкладки категорій у лістингу блогу.

   Доти лістинг був застосунком на Alpine: картки малював цикл `x-for` по
   масиву в кінці файлу, а підписи стояли у виразах `x-text`. У самій сторінці
   тексту не було зовсім — 165 знаків на 58 КБ файлу, тобто для читача без JS
   лістинг був порожній обома мовами.

   Тепер картки лежать у розмітці готовими, а від скрипта лишилася одна
   робота: сховати ті, що не належать вибраній категорії. Якщо він не
   виконається, сторінка просто покаже всі статті — це робочий стан, а не
   поламаний. */
(function () {
  'use strict';

  var ON = ['bg-fox-500', 'text-white'];
  var OFF = ['bg-white/5', 'text-gray-400', 'hover:bg-white/10', 'hover:text-gray-200'];

  function init() {
    var tabs = [].slice.call(document.querySelectorAll('[data-cat]'));
    var cards = [].slice.call(document.querySelectorAll('[data-card-cat]'));
    var empty = document.getElementById('cardsEmpty');
    if (!tabs.length || !cards.length) return;

    function select(key) {
      var shown = 0;
      cards.forEach(function (card) {
        var on = key === 'all' || card.dataset.cardCat === key;
        card.hidden = !on;
        if (on) shown++;
      });
      if (empty) empty.hidden = shown > 0;

      tabs.forEach(function (tab) {
        var on = tab.dataset.cat === key;
        ON.forEach(function (c) { tab.classList.toggle(c, on); });
        OFF.forEach(function (c) { tab.classList.toggle(c, !on); });
        tab.setAttribute('aria-pressed', String(on));
      });
    }

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () { select(tab.dataset.cat); });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
