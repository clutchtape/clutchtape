// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
const ctx=await b.newContext({viewport:{width:1440,height:900}});const p=await ctx.newPage();
await p.addInitScript(()=>{if(!sessionStorage.t){sessionStorage.t=1;localStorage.setItem('clutchtape.saved.v1',JSON.stringify([{label:'CyKul',url:'/p/cykul'},{label:'TriPPPeY',url:'/p/tripppey'}]))}});
await p.goto('https://clutchtape.com/',{waitUntil:'load'});await p.waitForTimeout(5000);
let n=await p.locator('#home-cards .personal-chip').count();await p.click('#home-edit');await p.locator('.personal-x').last().click();await p.waitForTimeout(4000);
const m=await p.locator('#home-cards .personal-chip').count();ok(m===n-1&&await p.evaluate(()=>JSON.parse(localStorage.getItem('clutchtape.saved.v1')).length)===1,'Edit → ✕ removes a saved chip',`${n} -> ${m}`);
for(const [u,kind] of [['/p/cykul','player'],['/sq/d7c3bb','squad']]){await p.goto('https://clutchtape.com'+u,{waitUntil:'load'});await p.waitForTimeout(1500);
 const t=await p.evaluate(()=>{const e=document.querySelector('.firsttip');return e&&!e.hidden?{kind:e.dataset.tip,text:e.textContent.replace(/\s+/g,' ').trim().slice(0,90),live:[...e.querySelectorAll('[data-tipfor]')].length}:null});
 ok(t&&t.kind===kind,`${kind}: first-visit tips show`,JSON.stringify(t));
 await p.click('[data-tipclose]');await p.reload({waitUntil:'load'});await p.waitForTimeout(800);
 ok(await p.evaluate(()=>document.querySelector('.firsttip')?.hidden!==false),`${kind}: dismissed tips stay hidden after reload`);}
const ph=await (await b.newContext({viewport:{width:390,height:844},isMobile:true})).newPage();await ph.goto('https://clutchtape.com/p/cykul',{waitUntil:'load'});await ph.waitForTimeout(1200);
ok(await ph.evaluate(()=>{const e=document.querySelector('.firsttip');return e&&!e.hidden&&document.documentElement.scrollWidth<=innerWidth}),'phone: tips fit, no overflow');
console.log(bad?bad+' failed':'ALL PASS');await b.close();
