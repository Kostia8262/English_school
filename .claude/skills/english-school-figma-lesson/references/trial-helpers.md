# Helper-код пробного заняття (use_figma)

Узято дослівно з третьої збірки (секція `342:2`, 19.10.2026) — вона найповніша. Звичайний JS для `use_figma`:
top-level `await`, у кінці `return`, без IIFE, `console.log`, `figma.notify`. Ліміт коду — 50 000 символів
(13 слайдів займали 14–15 тис.), ліміт відповіді — 20 480 байт.

## 1. Read-only: секція-взірець і сусіди

```js
const n = await figma.getNodeByIdAsync('328:3');            // node-id з посилання власника, «-» → «:»
let page = n; while (page.type !== 'PAGE') page = page.parent;
await figma.setCurrentPageAsync(page);
const top = page.children.filter(c=>c.type!=='VECTOR').map(c => `${c.type} "${c.name}" ${c.id} ${Math.round(c.x)},${Math.round(c.y)} ${Math.round(c.width)}x${Math.round(c.height)} k${'children' in c ? c.children.length : 0}`);
const kids = 'children' in n ? n.children.map(c => `${c.type} "${c.name}" ${c.id} ${Math.round(c.x)},${Math.round(c.y)} ${Math.round(c.width)}x${Math.round(c.height)}`) : [];
return {node:`${n.type} "${n.name}" ${Math.round(n.x)},${Math.round(n.y)} ${Math.round(n.width)}x${Math.round(n.height)}`, page:page.name, kids, top};
```

## 2. Read-only: модулі програми віку

```js
const p = await figma.getNodeByIdAsync('16:314');           // 16:210 — програма 10–12, 16:314 — 12–14
await figma.setCurrentPageAsync(p);
const texts = p.findAllWithCriteria({types:['TEXT']}).map(t=>t.characters.replace(/\s+/g,' ')).filter(s=>s.length>3);
const i = texts.findIndex(s=>/МОДУЛЬ 1/.test(s));
return texts.slice(Math.max(0,i-4), i+75).map(s=>s.slice(0,220)).join(' | ').slice(0,8000);
```

## 3. Збірка секції: шапка і хелпери

Після хелперів іде по блоку на слайд (`let B = slide(...)`, далі `numRow` / `chips` / `box` / `two` /
`choiceRows`), у кінці — підрахунок `fit`.

```js
const ref = await figma.getNodeByIdAsync('328:3');          // секція-взірець (з неї y і заливка)
const prev = await figma.getNodeByIdAsync('342:2');         // крайня права секція — нова стане правіше
const page = ref.parent; await figma.setCurrentPageAsync(page);
for (const s of ['Black','ExtraBold','Bold']) await figma.loadFontAsync({family:'Nunito',style:s});
const C = {blue:[47,116,189], green:[78,154,66], orange:[224,154,30], red:[226,89,63], purple:[124,91,196], ink:[28,58,94], sub:[74,107,136], bg:[255,247,233], white:[255,255,255], grey:[120,135,150]};
const TINT = {blue:[228,239,250], green:[233,246,226], orange:[252,243,224], red:[253,235,230], purple:[240,234,250]};
const solid = a => [{type:'SOLID', color:{r:a[0]/255,g:a[1]/255,b:a[2]/255}}];
const ROT = ['blue','green','orange','red','purple'];
function txt(s, style, size, color, lh=130, align){ const t=figma.createText(); t.fontName={family:'Nunito',style}; t.characters=s; t.fontSize=size; t.fills=solid(color); t.lineHeight={unit:'PERCENT',value:lh}; if(align) t.textAlignHorizontal=align; return t; }
function al(dir, props={}){ const f=figma.createAutoLayout(dir); f.fills=[]; f.set(props); return f; }
function fillText(parent,t){ parent.appendChild(t); t.layoutSizingHorizontal='FILL'; t.textAutoResize='HEIGHT'; return t; }
function paint(t, sub, style, color){ let i=t.characters.indexOf(sub); while(i>=0){ if(style) t.setRangeFontName(i,i+sub.length,{family:'Nunito',style}); if(color) t.setRangeFills(i,i+sub.length,solid(color)); i=t.characters.indexOf(sub,i+sub.length);} }
function brackets(t){ const re=/\([^)]+\)/g; let m; while((m=re.exec(t.characters))){ t.setRangeFontName(m.index,m.index+m[0].length,{family:'Nunito',style:'ExtraBold'}); t.setRangeFills(m.index,m.index+m[0].length,solid(C.red)); } }
const N = 13;                                               // кількість слайдів
const sec = figma.createSection(); sec.name = '13 · пробне + speaking';
sec.x = prev.x + prev.width + 1280; sec.y = ref.y; sec.resizeWithoutConstraints(2744, 729 + N*864 + 600);
try { sec.fills = JSON.parse(JSON.stringify(ref.fills)); } catch(e) {}
const created=[]; let idx=0;
// слайд 1280×720: плашка-заголовок (колір із 5), опційний бейдж (SPEAKING, A2, B1), підзаголовок-інструкція, тіло
function slide(name,title,color,sub,badge){
  const s=al('VERTICAL',{itemSpacing:20,paddingTop:34,paddingBottom:36,paddingLeft:56,paddingRight:56,cornerRadius:16}); s.fills=solid(C.bg); s.name=name;
  s.resize(1280,720); s.primaryAxisSizingMode='FIXED'; s.counterAxisSizingMode='FIXED'; s.clipsContent=true;
  sec.appendChild(s); s.x=732; s.y=729+idx*864; idx++;
  const head=al('VERTICAL',{itemSpacing:7,counterAxisAlignItems:'CENTER'}); s.appendChild(head); head.layoutSizingHorizontal='FILL';
  const row=al('HORIZONTAL',{itemSpacing:12,counterAxisAlignItems:'CENTER'}); head.appendChild(row);
  const pill=al('HORIZONTAL',{paddingTop:11,paddingBottom:15,paddingLeft:40,paddingRight:40,cornerRadius:14}); pill.fills=solid(C[color]); row.appendChild(pill); pill.appendChild(txt(title,'Black',46,C.white));
  if(badge){ const b=al('HORIZONTAL',{paddingTop:8,paddingBottom:11,paddingLeft:16,paddingRight:16,cornerRadius:12}); b.fills=solid(C.white); b.strokes=solid(C[color]); b.strokeWeight=3; b.appendChild(txt(badge,'Black',26,C[color])); row.appendChild(b); }
  fillText(head, txt(sub,'Bold',23,C.sub,130,'CENTER'));
  const body=al('VERTICAL',{itemSpacing:14}); s.appendChild(body); body.layoutSizingHorizontal='FILL'; body.layoutSizingVertical='FILL';
  created.push(s.id); return body;
}
// рядок із номером-чипом
function numRow(parent,n,text,color,size=28,pad=12){
  const r=al('HORIZONTAL',{itemSpacing:18,paddingTop:pad,paddingBottom:pad,paddingLeft:22,paddingRight:22,cornerRadius:16,counterAxisAlignItems:'CENTER'}); r.fills=solid(C.white); r.strokes=solid(C[color]); r.strokeWeight=3; parent.appendChild(r); r.layoutSizingHorizontal='FILL';
  const chip=al('VERTICAL',{cornerRadius:10,primaryAxisAlignItems:'CENTER',counterAxisAlignItems:'CENTER'}); chip.fills=solid(C[color]); chip.appendChild(txt(String(n),'Black',22,C.white)); r.appendChild(chip); chip.resize(42,42);
  const t=fillText(r, txt(text,'ExtraBold',size,C.ink)); return {r,t};
}
// ряд слів-карток, кольори по колу
function chips(parent, words, size=28, pad=12){
  const row=al('HORIZONTAL',{itemSpacing:12}); parent.appendChild(row); row.layoutSizingHorizontal='FILL';
  words.forEach((w,j)=>{ const col=ROT[j%5]; const c=al('VERTICAL',{paddingTop:pad,paddingBottom:pad+2,paddingLeft:8,paddingRight:8,cornerRadius:14,counterAxisAlignItems:'CENTER',primaryAxisAlignItems:'CENTER'}); c.fills=solid(C.white); c.strokes=solid(C[col]); c.strokeWeight=3; row.appendChild(c); c.layoutSizingHorizontal='FILL'; c.layoutSizingVertical='FILL'; fillText(c, txt(w,'Black',size,C[col],125,'CENTER')); });
  return row;
}
// картка з тонованою заливкою: заголовок + текст
function box(parent,color,title,body,size=27,lh=155){
  const b=al('VERTICAL',{itemSpacing:8,paddingTop:20,paddingBottom:22,paddingLeft:28,paddingRight:28,cornerRadius:18}); b.fills=solid(TINT[color]); b.strokes=solid(C[color]); b.strokeWeight=3; parent.appendChild(b); b.layoutSizingHorizontal='FILL';
  if(title) fillText(b, txt(title,'Black',28,C[color]));
  const t=fillText(b, txt(body,'Bold',size,C.ink,lh)); return {b,t};
}
function two(parent){ const r=al('HORIZONTAL',{itemSpacing:16}); parent.appendChild(r); r.layoutSizingHorizontal='FILL'; return r; }
// «обери варіант»: варіант між двома пробілами з кожного боку фарбується
function choiceRows(B, items, size=25, pad=8){ items.forEach((q,i)=>{ const {t}=numRow(B,i+1,q,ROT[i%5],size,pad); const m=q.match(/ {2}(.+?)(?= {2}|[.?!]$)/); if(m) paint(t,m[1],'Black',C[ROT[i%5]]); }); }

// приклад слайда
let B=slide('13+ · Слайд 1 · ЗАВДАННЯ 1 · INTERVIEW','INTERVIEW','blue','Знайомимось. Відповідай не одним словом — додай ще одне речення');
['Where are you from, and what do you like about your town?','What are you into these days — games, music, sport?'].forEach((q,i)=>numRow(B,i+1,q,ROT[i],27,14));

// висота вмісту тіла кожного слайда: 507 = до краю, < ~400 = порожньо
const fit=[]; for (const id of created){ const s=await figma.getNodeByIdAsync(id); const b=s.children[1]; const h=b.children.reduce((a,c)=>a+c.height,0)+(b.children.length-1)*b.itemSpacing; fit.push(Math.round(h)); }
return {section:sec.id, created, fit};
```

## 4. Скріни — не більше 5 за виклик

```js
const p = await figma.getNodeByIdAsync('113:2'); await figma.setCurrentPageAsync(p);
for (const id of ["342:3","342:30","342:61","342:88","342:98"]) { const n = await figma.getNodeByIdAsync(id); await n.screenshot({scale:0.5}); }
return 'ok';
```

## 5. Перевірка, чи щось вилазить після правок

```js
const body = async id => (await figma.getNodeByIdAsync(id)).children[1];
const fit=[]; for (const id of ['342:88','342:129']){ const b=await body(id); let over=false;
  for (const c of b.children) if (c.y+c.height > b.height+1) over=true;
  for (const c of b.findAll(n=>n.type==='TEXT')) { const par=c.parent; if (c.absoluteBoundingBox.y+c.height > par.absoluteBoundingBox.y+par.height+1) over=true; }
  fit.push([id,over]); }
return fit;
```

Типові правки порожнього слайда: `body.itemSpacing` 18–20, `paddingTop/Bottom` карток 24–28, кегль тексту
28–31, `lineHeight` 180–185 %. Чипси, що перенеслись: кегль 26, `paddingLeft/Right` 4; висота тексту 33 — один рядок.
