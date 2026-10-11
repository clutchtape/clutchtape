// Session clips (2026-10-11): Latest shows only the session's clips (+ All clips →); the Clips tab shows all.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
const p=await b.newPage({viewport:{width:1440,height:1000}});const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
const info=()=>p.evaluate(()=>{const sec=document.querySelector('.clipsec');const dates=[...document.querySelectorAll('.clipsec .mo small')].map(s=>(s.textContent.match(/(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d+/)||[''])[0]);
 const sess=(document.querySelector('.gamelog .ph .muted')?.textContent.match(/(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d+/)||[''])[0];
 return {title:sec?.querySelector('h2')?.textContent,n:dates.length,dates:[...new Set(dates)],sess,all:!!document.querySelector('.clipsec .allclips'),tw:document.querySelector('.twclips h2')?.textContent||'-'}});
for(const base of ['https://clutchtape.com/p/cykul','https://clutchtape.com/sq/d7c3bb']){
await p.goto(base,{waitUntil:'load'});await p.waitForTimeout(800);let r=await info();
ok(!r.title||r.title==='Clips from this session',`${base}: Latest titled "Clips from this session"`,JSON.stringify(r));
ok(r.dates.every(d=>!d||d===r.sess),`${base}: Latest clips are all from the session shown (${r.sess})`,JSON.stringify(r.dates));
const prev=p.locator('.sessbtn[rel=prev]').first();if(await prev.count()){await prev.click();await p.waitForLoadState('load');await p.waitForTimeout(800);r=await info();
 ok(r.dates.every(d=>!d||d===r.sess),`${base}: an older session shows only its own clips (${r.sess})`,JSON.stringify(r));}
await p.goto(base+(base.includes('?')?'&':'?')+'tab=clips',{waitUntil:'load'});await p.waitForTimeout(800);r=await info();
ok(r.title==='Auto clips'&&r.n>=r.dates.length,`${base}: Clips tab has all clips (${r.n} from ${r.dates.length} days)`,JSON.stringify(r.dates.slice(0,6)));}
ok(!errs.length,'no errors',errs.join('|'));console.log(bad?bad+' failed':'ALL PASS');await b.close();
