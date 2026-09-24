// logo.svg -> logo.png (1024). Знак живе у векторі; растр — похідна від нього,
// бо PIL не вміє SVG, а іконки збираються саме з растру.
const { Resvg } = require('@resvg/resvg-js');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..', '..');
const svg = fs.readFileSync(path.join(root, 'logo.svg'));
const png = new Resvg(svg, {
  fitTo: { mode: 'width', value: 1024 },
  background: 'rgba(0,0,0,0)',
}).render().asPng();

fs.writeFileSync(path.join(root, 'logo.png'), png);
console.log(`logo.png  ${png.length.toLocaleString()} B  1024x1024`);
