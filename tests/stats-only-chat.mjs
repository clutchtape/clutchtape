// Stats only + Keep chat (2026-10-10): no video, chat beside the stats on desktop, Chat pill + sheet on phones.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
for(const [w,h] of [[1440,1000],[390,844]]){const mob=w<700;const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:mob,hasTouch:mob});const p=await ctx.newPage();
const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
await p.goto(process.argv[2],{waitUntil:'load'});await p.waitForTimeout(2500);
const tap=async l=>{mob?await l.tap():await l.click();await p.waitForTimeout(400)};
await tap(p.locator('.laybtn'));await p.locator('.laycard input[name=sochat]').check();await p.waitForTimeout(300);await tap(p.locator('[data-layclose]'));
await tap(p.locator('[data-statsonly]:visible').first());await p.waitForTimeout(1500);
const st=await p.evaluate(()=>{const c=document.getElementById('twchat'),pl=document.getElementById('player'),t=document.querySelector('.chattab');const R=e=>e&&e.getClientRects().length?(r=>Math.round(r.left)+','+Math.round(r.top)+' '+Math.round(r.width)+'x'+Math.round(r.height))(e.getBoundingClientRect()):'hidden';
 return {statsonly:document.documentElement.classList.contains('statsonly'),player:R(pl),chat:R(c),chatVisible:!!c&&getComputedStyle(c).display!=='none',pill:t?R(t):'none',board:R(document.getElementById('statsboard'))}});
if(!mob)ok(st.statsonly&&st.player==='hidden'&&st.chatVisible&&st.chat!=='hidden',`${w}: no video, chat beside the stats`,JSON.stringify(st));
else{ok(st.statsonly&&st.player==='hidden'&&st.pill!=='hidden'&&st.pill!=='none',`${w}: no video, Chat pill showing`,JSON.stringify(st));
 await tap(p.locator('.chattab'));await p.waitForTimeout(1500);const c=await p.evaluate(()=>{const r=document.getElementById('twchat').getBoundingClientRect();return {open:document.documentElement.classList.contains('chat-open'),top:Math.round(r.top),h:Math.round(r.height),src:!!document.querySelector('.twchat-frame').getAttribute('src')}});
 ok(c.open&&c.top>100&&c.h>300&&c.src,`${w}: chat sheet opens`,JSON.stringify(c));}
await p.screenshot({path:S+`sochat-${w}.png`});
ok(!errs.length,`${w}: no errors`,errs.join('|'));await ctx.close()}
console.log(bad?bad+' failed':'ALL PASS');await b.close();
