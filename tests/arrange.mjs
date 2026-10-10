// Arrange the Latest tab (2026-10-10): reorder, hide, reload, reset, phone sheet.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';const url=process.argv[2];
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
for(const [w,h] of [[1440,1000],[390,844]]){const mob=w<700;const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:mob,hasTouch:mob});const p=await ctx.newPage();
const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
const order=()=>p.evaluate(()=>[['media','#mediasec'],['tiles','.hubkpis'],['log','#latest'],['modes','.brk']].map(([k,s])=>{const e=document.querySelector(s);if(!e||!e.offsetHeight)return null;let t=0;for(let x=e;x;x=x.offsetParent)t+=x.offsetTop;return [k,t]}).filter(Boolean).sort((a,b)=>a[1]-b[1]).map(x=>x[0]).join(','));
await p.goto(url,{waitUntil:'load'});await p.waitForTimeout(1500);const o0=await order();console.log(w,'default order',o0);
const tap=async s=>{const l=p.locator(s).first();mob?await l.tap():await l.click();await p.waitForTimeout(250)};
await tap('.arrbtn');ok(await p.locator('.arrcard').isVisible(),`${w}: Arrange opens`);
const box=await p.evaluate(()=>{const r=document.querySelector('.arrcard').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight});ok(box,`${w}: Arrange card on screen`);
await p.screenshot({path:S+`arr-${w}.png`});
await tap('.arrlist li[data-k=log] [data-mv="-1"]');await tap('.arrlist li[data-k=log] [data-mv="-1"]');
await p.waitForTimeout(400);let o=await order();ok(o.startsWith('log'),`${w}: Game log moved to the top`,o);
await p.locator('.arrlist li[data-k=tiles] input').uncheck();await p.waitForTimeout(500);o=await order();ok(!o.includes('tiles'),`${w}: tiles hidden`,o);
await p.reload({waitUntil:'load'});await p.waitForTimeout(1200);o=await order();ok(o.startsWith('log')&&!o.includes('tiles'),`${w}: kept after reload`,o);
await tap('.arrbtn');await tap('[data-arrreset]');o=await order();ok(o===o0,`${w}: Reset restores the page's own order`,o);
ok(!errs.length,`${w}: no errors`,errs.join('|'));await ctx.close()}
console.log(bad?bad+' failed':'ALL PASS');await b.close();
