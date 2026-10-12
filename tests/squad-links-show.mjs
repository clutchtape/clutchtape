// Squad row click + squad share link + per-page Show (2026-10-12).
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
// (c) Show switch choices stick to that page only
import {chromium} from 'playwright';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let fails=0;const ok=(c,m,d)=>{console.log((c?'PASS ':'FAIL ')+m,d!==undefined?JSON.stringify(d):'');if(!c)fails++};
const ctx=await b.newContext({viewport:{width:1440,height:900}});await ctx.grantPermissions(['clipboard-read','clipboard-write'],{origin:'https://clutchtape.com'});
const p=await ctx.newPage();
await p.goto('https://clutchtape.com/sq/657683#w='+(process.env.CT_W||'chan1..chan3.chan4')+'',{waitUntil:'load'});await p.waitForTimeout(5000);
ok(/#w=.+$/.test(p.url()),'(b) squad address carries the channels',p.url());
await p.locator('[data-share]').first().click();await p.waitForTimeout(500);
const clip=await p.evaluate(()=>navigator.clipboard.readText().catch(()=>null));ok(clip&&/#w=/.test(clip),'(b) Share copies the link with channels',clip);
const row=p.locator('table.night tr[data-mid="547a4f94"]');await row.scrollIntoViewIfNeeded();await row.locator('td').first().click();await p.waitForTimeout(6000);
ok(/\/sq\/657683\/g\/547a4f94/.test(p.url())&&await p.evaluate(()=>!document.getElementById('multi').hidden),'(a) clicking the game row opens every angle',p.url());
// (c) per page: set stats hidden on cykul, then visit another player
const q=await ctx.newPage();
await q.goto('https://clutchtape.com/p/cykul',{waitUntil:'load'});await q.evaluate(()=>window.ctShow.set({stats:false,video:false}));await q.reload({waitUntil:'load'});await q.waitForTimeout(800);
const a=await q.evaluate(()=>[document.documentElement.classList.contains('lay-stats-hidden'),document.documentElement.classList.contains('statsonly')]);
await q.goto('https://clutchtape.com/p/itzthelastshot',{waitUntil:'load'});await q.waitForTimeout(800);
const bb=await q.evaluate(()=>[document.documentElement.classList.contains('lay-stats-hidden'),document.documentElement.classList.contains('statsonly')]);
await q.goto('https://clutchtape.com/p/cykul',{waitUntil:'load'});await q.waitForTimeout(800);
const c=await q.evaluate(()=>[document.documentElement.classList.contains('lay-stats-hidden'),document.documentElement.classList.contains('statsonly')]);
await q.evaluate(()=>{const s=JSON.parse(localStorage.getItem('ct-show'));s.at=Date.now()-13*3600e3;localStorage.setItem('ct-show',JSON.stringify(s))});await q.reload({waitUntil:'load'});await q.waitForTimeout(800);
const d=await q.evaluate(()=>[document.documentElement.classList.contains('lay-stats-hidden'),document.documentElement.classList.contains('statsonly')]);
ok(a[0]&&a[1]&&!bb[0]&&!bb[1]&&c[0]&&c[1]&&!d[0]&&!d[1],'(c) hidden on cykul only; another player shows all; back on cykul still hidden; after 12 h shows all',{cykul:a,other:bb,back:c,after13h:d});
await b.close();console.log(fails?fails+' FAILED':'ALL PASS');
