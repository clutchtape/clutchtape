// Customize the live view (2026-10-10): chat beside/below/hidden/right, table off, pinned stats, reload, reset, phone sheet.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';const url=process.argv[2];
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
const ctx=await b.newContext({viewport:{width:1440,height:1000}});const p=await ctx.newPage();const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
const geo=()=>p.evaluate(()=>{const R=s=>{const e=document.querySelector(s);if(!e||!e.offsetHeight)return null;const r=e.getBoundingClientRect();return {x:Math.round(r.left),y:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height)}};
 return {video:R('#player .embed'),vs:R('#livevs'),onair:R('#onair'),chat:R('#twchat'),side2:!!document.querySelector('.colside.side2'),nums:[...document.querySelectorAll('#onair .oa-card:first-child .oa-nums>[data-k]')].map(e=>e.dataset.k)}});
await p.goto(url,{waitUntil:'load'});await p.waitForTimeout(3000);const g0=await geo();console.log('default',JSON.stringify(g0));
const open=async()=>{if(!await p.locator('.laycard').isVisible())await p.locator('.laybtn').click();await p.waitForTimeout(200)};
const pick=async(sel)=>{await open();await p.locator(sel).check();await p.waitForTimeout(900)};
await open();await p.screenshot({path:S+'cust-open.png'});
await pick('input[name=chat][value=beside]');let g=await geo();ok(g.side2&&g.chat&&g.chat.x<g.onair.x,'chat beside, on the left',JSON.stringify({v:g.video,chat:g.chat,onair:g.onair}));
await pick('input[name=side][value=right]');g=await geo();ok(g.side2&&g.chat.x>g.onair.x,'chat on the right');
await p.locator('[data-layclose]').click();await p.waitForTimeout(5000);await p.screenshot({path:S+'cust-beside-right.png'});
{const fr=p.frames().find(f=>/player\.twitch/.test(f.url()));const v=fr?await fr.evaluate(()=>{const v=document.querySelector('video');return v&&!v.paused}).catch(()=>false):false;ok(v,'stream playing again after closing Customize');}
await pick('input[name=chat][value=below]');g=await geo();ok(!g.side2&&g.chat&&g.chat.y>g.onair.y,'chat below stats');
await pick('input[name=chat][value=hidden]');g=await geo();ok(!g.chat&&g.onair&&g.onair.h>500,'chat hidden, stats fill the side',JSON.stringify(g.onair));
const vh=g.video.h;await open();await p.locator('input[name=vs]').uncheck();await p.waitForTimeout(900);g=await geo();ok(!g.vs&&g.video.h>=vh,'table hidden (video keeps or gains height; at 1440x1000 it is width-limited)',vh+' -> '+g.video.h);
await p.evaluate(()=>{const c=document.querySelector('#onair .oa-card');if(c.querySelector(':scope>.oa-nums [data-k]'))return;c.classList.remove('none');c.insertAdjacentHTML('beforeend','<div class="oa-nums" data-test><span class="lv" data-k="kda"><b>3.1</b>KDA</span><span class="lv" data-k="dmg_pm"><b>480</b>Dmg/min</span><span class="lv" data-k="sc_pct"><b>27%</b>Score %</span></div><div class="oa-more"><div class="oa-grp"><span class="lab">Slaying</span><span class="lv" data-k="kd"><b>1.4</b>K/D</span></div><div class="oa-grp"><span class="lab">Team</span><span class="lv" data-k="win_pct"><b>60%</b>Win</span><span class="lv" data-k="acc"><b>51%</b>Acc</span></div></div>')});
await pick('input[name=pin][value=kd]');await pick('input[name=pin][value=acc]');await pick('input[name=pin][value=win_pct]');g=await geo();
g.nums=await p.evaluate(()=>[...document.querySelectorAll('#onair .oa-card:first-child>.oa-nums>[data-k]')].map(e=>e.dataset.k));const un=await p.evaluate(()=>[...document.querySelectorAll('#onair .oa-card:first-child .oa-unpinned [data-k]')].map(e=>e.dataset.k));
ok(JSON.stringify(g.nums)===JSON.stringify(['kd','acc','win_pct'])&&['kda','dmg_pm','sc_pct'].every(k=>un.includes(k)),'pinned stats lead the live box (sample card), the rest move to "Also"',JSON.stringify(g.nums)+' also '+JSON.stringify(un));
await p.reload({waitUntil:'load'});await p.waitForTimeout(3000);g=await geo();ok(!g.chat&&!g.vs,'settings survive reload');
ok(await p.evaluate(()=>['kd','acc','win_pct'].every(k=>JSON.parse(localStorage.getItem('ct-layout')).pins.includes(k))),'pins saved');
await open();await p.locator('[data-layreset]').click();await p.waitForTimeout(900);g=await geo();ok(g.chat&&g.vs,'Reset restores the default layout');
ok(!errs.length,'no page errors',errs.join('|'));
// phone: menu fits on screen
const m=await b.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const q=await m.newPage();await q.goto(url,{waitUntil:'load'});await q.waitForTimeout(2000);
await q.locator('.laybtn').tap();await q.waitForTimeout(400);const r=await q.evaluate(()=>{const c=document.querySelector('.laycard').getBoundingClientRect();return {l:Math.round(c.left),r:Math.round(c.right),t:Math.round(c.top),b:Math.round(c.bottom),ovf:document.documentElement.scrollWidth-innerWidth}});
ok(r.l>=0&&r.r<=390&&r.b<=844&&r.ovf===0,'phone: Customize sheet on screen',JSON.stringify(r));await q.screenshot({path:S+'cust-phone.png'});
console.log(bad?bad+' failed':'ALL PASS');await b.close();
