// Site motion (2026-10-10): page transitions + slide direction, count-up, Raw crossfade, sort slide, game -> match morph.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const base=process.argv[2];
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
for(const [w,h] of [[1440,1000],[390,844]]){const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:w<700,hasTouch:w<700});const p=await ctx.newPage();
const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});p.on('console',m=>{if(m.type()==='error'&&/Content Security|speculation|Refused/i.test(m.text()))errs.push(m.text().slice(0,160))});
await p.addInitScript(()=>{window.__vt=null;addEventListener('pagereveal',e=>{if(e.viewTransition){const t=[];try{e.viewTransition.types.forEach(x=>t.push(x))}catch(x){}setTimeout(()=>{try{e.viewTransition.types.forEach(x=>t.includes(x)||t.push(x))}catch(x){}window.__vt={types:t,hero:!!document.querySelector('.vt-hero')}},0)}})});
const serverHtml=await (await ctx.request.get(base)).text();
await p.goto(base,{waitUntil:'domcontentloaded'});await p.waitForTimeout(150);
const mid=await p.evaluate(()=>[...document.querySelectorAll('.hubkpi b')].map(e=>e.textContent));
await p.waitForTimeout(1200);
const fin=await p.evaluate(()=>[...document.querySelectorAll('.hubkpi b')].map(e=>e.textContent));
const srv=[...serverHtml.matchAll(/<div class="hubkpi[^"]*"[^>]*><b>([^<]*)<\/b>/g)].map(m=>m[1]);
ok(JSON.stringify(fin)===JSON.stringify(srv),`${w}: KPI numbers end exactly as served`,JSON.stringify(fin));
ok(JSON.stringify(mid)!==JSON.stringify(fin),`${w}: KPI numbers were counting up`,JSON.stringify(mid));
// tab change -> page transition, slide forward
await p.locator('.hub-tabs a',{hasText:'Sessions'}).click();await p.waitForLoadState('load');await p.waitForTimeout(600);
let vt=await p.evaluate(()=>window.__vt);ok(vt&&vt.types.includes('page')&&vt.types.includes('fwd'),`${w}: Latest -> Sessions transitions (fwd)`,JSON.stringify(vt));
await p.locator('.hub-tabs a').first().click();await p.waitForLoadState('load');await p.waitForTimeout(600);
vt=await p.evaluate(()=>window.__vt);ok(vt&&vt.types.includes('back'),`${w}: Sessions -> Latest slides back`,JSON.stringify(vt));
// previous session arrow
const prev=p.locator('.sessbtn[rel=prev]').first();if(await prev.count()){await prev.click();await p.waitForLoadState('load');await p.waitForTimeout(600);vt=await p.evaluate(()=>window.__vt);ok(vt&&vt.types.includes('back'),`${w}: ‹ Previous session slides back`,JSON.stringify(vt));}
// game -> match
const ml=p.locator('.gamelog a[href^="/match/"]:visible').first();
if(await ml.count()){await ml.click();await p.waitForURL(/\/match\//);await p.waitForTimeout(700);vt=await p.evaluate(()=>window.__vt);ok(vt&&vt.hero,`${w}: game row morphs into the match header`,JSON.stringify(vt));
 await p.goBack();await p.waitForLoadState('load');await p.waitForTimeout(700);vt=await p.evaluate(()=>window.__vt);ok(vt&&vt.types.includes('page'),`${w}: back from match transitions`,JSON.stringify(vt));}
else ok(false,`${w}: no game link found`);
// raw <-> summary
const raw=p.locator('[data-view=raw]:visible').first();
if(await raw.count()){await raw.click();await p.waitForTimeout(900);ok(await p.evaluate(()=>document.documentElement.classList.contains('rawview')&&!!document.querySelector('#raw table')?.offsetHeight),`${w}: Raw view shows`);
 await p.locator('[data-view=summary]:visible').first().click();await p.waitForTimeout(900);ok(await p.evaluate(()=>!document.documentElement.classList.contains('rawview')),`${w}: back to Summary`);}
// sort slide
const th=p.locator('.gamelog table thead th:visible').nth(3);
if(await th.count()){const before=await p.evaluate(()=>[...document.querySelector('.gamelog table tbody').rows].map(r=>r.textContent.slice(0,20)).join('|'));await th.click();await p.waitForTimeout(500);
 const after=await p.evaluate(()=>[...document.querySelector('.gamelog table tbody').rows].map(r=>r.textContent.slice(0,20)).join('|'));ok(true,`${w}: sort click ok`,before===after?'(order unchanged)':'(reordered)');}
ok(!errs.length,`${w}: no page/CSP errors`,errs.slice(0,3).join(' | '));
await ctx.close()}
console.log(bad?bad+' failed':'ALL PASS');await b.close();
