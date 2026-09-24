// og-картки під кожну сторінку.
//
// Навіщо. og:image на всіх 86 сторінках був один — og-image.jpg. Посилання
// на ціни, на блог і на пробний урок виглядали в месенджері однаково, і
// подивитися на прев'ю, куди саме тебе кличуть, було неможливо.
//
// Текст береться з <h1> уже зібраної сторінки, українська з `slug.html`,
// російська з `slug.ru.html`. Другої копії заголовків тут немає навмисно:
// на цьому сайті вже двічі розходилися тексти, які лежали у двох місцях.
//
// Рендерить справжній браузер (системний Chrome через playwright-core), бо
// шрифт сайту — варіативний Nunito у woff2, розбитий на кириличний і
// латинський сабсети. PIL woff2 не читає, а fontTools відмовляється зливати
// варіативні сабсети в один ttf. Браузер бере той самий css/fonts.css, що й
// сторінки, тож набір у картці той самий, що бачить відвідувач.
//
//   node tools/og/build.js            усі сторінки
//   node tools/og/build.js tsiny      одна
//
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const OUT = path.join(ROOT, 'og');

// slug -> іконка з /icons і підпис у підвалі картки.
// Іконка та сама, що вже стоїть на самій сторінці, — картка не вигадує
// собі окремої мови знаків.
const PAGES = {
  'index':                           ['cap',        'Онлайн по всій Україні',      'Онлайн по всей Украине'],
  'tsiny':                           ['money',      'Ціни та знижки',              'Цены и скидки'],
  'probnyi-urok':                    ['gift',       'Перший урок — безкоштовно',   'Первый урок — бесплатно'],
  'kursy-anhliyskoyi-dlya-ditey':    ['books',      '6–18 років · групи до 5',     '6–18 лет · группы до 5'],
  'anhliyska-6-8-rokiv':             ['chick',      'A0 → A1 · ігрова форма',      'A0 → A1 · игровая форма'],
  'anhliyska-9-12-rokiv':            ['rocket',     'A1 → B1 · розмовні клуби',    'A1 → B1 · разговорные клубы'],
  'anhliyska-13-18-rokiv':           ['target',     'B1 → B2 · НМТ і Cambridge',   'B1 → B2 · НМТ и Cambridge'],
  'anhliyska-onlayn-dlya-ditey':     ['laptop',     'Zoom · Google Meet',          'Zoom · Google Meet'],
  'anhliyska-z-nulya-dlya-ditey':    ['form',       'З нуля · без домашки на ніч', 'С нуля · без домашки на ночь'],
  'anhliyska-dlya-ditey-za-kordonom':['earth',      'Для дітей за кордоном',       'Для детей за границей'],
  'anhliyska-dlya-ditey-u-polshchi': ['earth',      'Для родин у Польщі',          'Для семей в Польше'],
  'anhliyska-dlya-ditey-u-nimechchyni': ['earth',    'Для родин у Німеччині',       'Для семей в Германии'],
  'anhliyska-dlya-ditey-u-chekhiyi': ['earth',      'Для родин у Чехії',           'Для семей в Чехии'],
  'anhliyska-dlya-ditey-v-italiyi':  ['earth',      'Для родин в Італії',          'Для семей в Италии'],
  'anhliyska-dlya-ditey-u-rumuniyi': ['earth',      'Час той самий, що в Києві',   'Время то же, что в Киеве'],
  'anhliyska-dlya-ditey-u-frantsiyi': ['earth',     'Для родин у Франції',         'Для семей во Франции'],
  'anhliyska-dlya-ditey-v-ispaniyi': ['earth',      'Для родин в Іспанії',         'Для семей в Испании'],
  'anhliyska-dlya-ditey-u-velykobrytaniyi': ['earth', 'Для родин у Британії', 'Для семей в Британии'],
  'anhliyska-dlya-ditey-v-irlandiyi': ['earth', 'Для родин в Ірландії', 'Для семей в Ирландии'],
  'anhliyska-dlya-ditey-u-niderlandakh': ['earth', 'Для родин у Нідерландах', 'Для семей в Нидерландах'],
  'anhliyska-dlya-ditey-v-avstriyi': ['earth', 'Для родин в Австрії', 'Для семей в Австрии'],
  'anhliyska-dlya-ditey-u-slovachchyni': ['earth', 'Для родин у Словаччині', 'Для семей в Словакии'],
  'anhliyska-dlya-ditey-u-bolhariyi': ['earth', 'Час той самий, що в Києві', 'Время то же, что в Киеве'],
  'anhliyska-dlya-ditey-u-portuhaliyi': ['earth', 'Для родин у Португалії', 'Для семей в Португалии'],
  'anhliyska-dlya-ditey-u-shveytsariyi': ['earth', 'Для родин у Швейцарії', 'Для семей в Швейцарии'],
  'anhliyska-dlya-ditey-u-moldovi': ['earth', 'Час той самий, що в Києві', 'Время то же, что в Киеве'],
  'anhliyska-dlya-ditey-v-uhorshchyni': ['earth', 'Для родин в Угорщині', 'Для семей в Венгрии'],
  'anhliyska-dlya-ditey-u-hruziyi': ['earth', 'Для родин у Грузії', 'Для семей в Грузии'],
  'anhliyska-dlya-ditey-u-kazakhstani': ['earth', 'Для родин у Казахстані', 'Для семей в Казахстане'],
  'anhliyska-dlya-ditey-u-virmeniyi': ['earth', 'Для родин у Вірменії', 'Для семей в Армении'],
  'anhliyska-dlya-ditey-u-kyrhyzstani': ['earth', 'Для родин у Киргизстані', 'Для семей в Кыргызстане'],
  'rozmovna-anhliyska-dlya-ditey':   ['speak',      'Говорить учень, а не вчитель','Говорит ученик, а не учитель'],
  'repetytor-z-anhliyskoyi':         ['cap',        'Один на один із вчителем',    'Один на один с учителем'],
  'pidhotovka-do-nmt':               ['clipboard',  'НМТ з англійської',           'НМТ по английскому'],
  'cambridge':                       ['medal',      'YLE · KET · PET · FCE',       'YLE · KET · PET · FCE'],
  'dnipro':                          ['pin',        'Онлайн і два класи в Дніпрі', 'Онлайн и два класса в Днепре'],
  'pro-shkolu':                      ['school',     'Про школу FluentFox',         'О школе FluentFox'],
  'vidhuky':                         ['chat',       'Відгуки батьків',             'Отзывы родителей'],
  'oplata':                          ['card',       'Оплата навчання',             'Оплата обучения'],
  'blog/index':                      ['quill',      'Статті наших вчителів',       'Статьи наших преподавателей'],
};

// Статті блога виходять щотижня, тому перелічувати їх тут не можна — забудеться
// рівно на тій, яку додасть чужа вкладка. Беремо з blog/articles.json, іконку —
// за рубрикою.
const BLOG_ICON = {
  'Методи навчання':  'books',
  'Формат занять':    'laptop',
  'Вік і розвиток':   'chick',
  'Вибір школи':      'search',
  'Мотивація':        'rocket',
  'НМТ та іспити':    'clipboard',
};

function addArticles() {
  const file = path.join(ROOT, 'blog', 'articles.json');
  if (!fs.existsSync(file)) return;
  const { articles } = JSON.parse(fs.readFileSync(file, 'utf8'));
  for (const a of articles) {
    const icon = BLOG_ICON[a.category] || 'quill';
    PAGES['blog/' + a.slug] = [icon, a.category, a.category];
  }
}

function headline(file) {
  const html = fs.readFileSync(path.join(ROOT, file), 'utf8');
  const m = html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/);
  if (!m) throw new Error(`немає <h1> у ${file}`);
  return m[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
}

// Останні два слова заголовка фарбуються у fox-500 — картка без акценту
// читається як суцільна чорна плита.
function accented(text) {
  const w = text.split(' ');
  if (w.length < 4) return esc(text);
  const tail = w.splice(-2).join(' ');
  return `${esc(w.join(' '))} <em>${esc(tail)}</em>`;
}
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

(async () => {
  const only = process.argv[2];
  addArticles();
  fs.mkdirSync(OUT, { recursive: true });

  const browser = await chromium.launch({ channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
  await page.goto('file:///' + path.join(__dirname, 'card.html').replace(/\\/g, '/'));
  await page.evaluate(() => document.fonts.ready);

  let made = 0;
  for (const [slug, [icon, noteUk, noteRu]] of Object.entries(PAGES)) {
    if (only && slug !== only) continue;

    for (const lang of ['uk', 'ru']) {
      const src = lang === 'uk' ? `${slug}.html` : `${slug}.ru.html`;
      if (!fs.existsSync(path.join(ROOT, src))) { console.log(`  пропуск ${src}`); continue; }

      const title = headline(src);
      await page.evaluate(({ title, icon, note, lang }) => {
        const h = document.getElementById('title');
        h.innerHTML = title;
        h.className = title.length > 58 ? 'xlong' : title.length > 38 ? 'long' : '';
        document.getElementById('icon').src = `../../icons/${icon}.webp`;
        document.getElementById('note').textContent = note;
        document.getElementById('tagline').textContent =
          lang === 'ru' ? 'Школа английского' : 'English School';
        document.documentElement.lang = lang;
      }, { title: accented(title), icon, note: lang === 'uk' ? noteUk : noteRu, lang });

      await page.evaluate(() => document.fonts.ready);
      const name = slug.replace('/', '-') + (lang === 'ru' ? '.ru' : '') + '.jpg';
      await page.screenshot({ path: path.join(OUT, name), type: 'jpeg', quality: 78 });
      made++;
    }
  }
  await browser.close();

  const total = fs.readdirSync(OUT).reduce((n, f) => n + fs.statSync(path.join(OUT, f)).size, 0);
  console.log(`og: ${made} карток, ${(total / 1024).toFixed(0)} КБ разом`);
})();
