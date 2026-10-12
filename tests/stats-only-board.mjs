// Stats-only board (2026-10-10): tiles heat vs usual, clips last on the page, back under the video with the stream.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
for(const [w,h] of [[1440,1000],[390,844]]){const mob=w<700;const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:mob,hasTouch:mob});const p=await ctx.newPage();
const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
await p.addInitScript(()=>{try{localStorage.setItem('ct-show',JSON.stringify({k:location.pathname.split('/').slice(0,3).join('/'),at:Date.now(),video:false}))}catch(e){}});
await p.goto(process.argv[2],{waitUntil:'load'});await p.waitForTimeout(2500);
const t=await p.evaluate(()=>[...document.querySelectorAll('.sb-tile')].map(x=>x.querySelector('span').textContent+':'+(x.className.match(/h-\w+/)||['-'])[0]+(x.querySelector('.sb-usual')?'('+x.querySelector('.sb-usual').textContent+')':'')).join(' '));
ok(/h-(ex|good|avg|below|poor)/.test(t),`${w}: tiles tinted vs usual`,t);
const order=()=>p.evaluate(()=>{const top=s=>{const e=document.querySelector(s);if(!e||!e.getClientRects().length)return null;let y=0;for(let x=e;x;x=x.offsetParent)y+=x.offsetTop;return y};return {clips:top('.liveclips'),log:top('#latest'),medals:top('.brk'),board:top('#statsboard')}});
let o=await order();ok(o.clips>Math.max(o.log||0,o.medals||0),`${w}: clips are last in Stats only`,JSON.stringify(o));
await p.screenshot({path:S+`sb-${w}.png`,fullPage:!mob});
await p.locator('[data-statsonly]:visible').first().click();await p.waitForTimeout(1500);
o=await order();const vs=await p.evaluate(()=>{const v=document.getElementById('livevs'),r=document.querySelector('.liveclips');return v&&r&&v.nextElementSibling===r});
ok(vs,`${w}: back under the video with the stream`,JSON.stringify(o));
ok(!errs.length,`${w}: no errors`,errs.join('|'));await ctx.close()}
console.log(bad?bad+' failed':'ALL PASS');await b.close();
