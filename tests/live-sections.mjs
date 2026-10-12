// Live refresh (2026-10-11): sections missing before come back in place, extra ones are removed, the video is never touched.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const [U]=process.argv.slice(2);
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let fails=0;const ok=(c,m,d)=>{console.log((c?'PASS ':'FAIL ')+m,d!==undefined?JSON.stringify(d):'');if(!c)fails++};
for(const [w,h] of [[1440,900],[390,844]]){const p=await b.newPage({viewport:{width:w,height:h},isMobile:w<700});const errs=[];p.on('pageerror',e=>errs.push(e.message));
await p.goto(U,{waitUntil:'load'});await p.waitForTimeout(2500);
const order=()=>p.evaluate(()=>[...document.querySelectorAll('.hubkpis,#latest,.brk,#raw,.clipsec,#teamwork,#vodvs,#watchguide,#sqtable,#livevs')].map(e=>e.id||e.className.split(' ')[0]));
const o0=await order();
await p.evaluate(()=>{document.querySelector('.hubkpis')?.remove();document.getElementById('latest')?.remove();const f=document.createElement('section');f.id=document.getElementById('teamwork')?'vodvs':'teamwork';f.textContent='stale';document.querySelector('main').appendChild(f)});
const o1=await order();
const vid0=await p.evaluate(()=>{const f=document.querySelector('#player iframe');return f?f.src:null});
await p.evaluate(()=>window.ctLiveRefresh());await p.waitForTimeout(3000);
const o2=await order();const vid1=await p.evaluate(()=>{const f=document.querySelector('#player iframe');return f?f.src:null});
ok(JSON.stringify(o2)===JSON.stringify(o0),w+' missing sections come back in place, stale one removed',{before:o0,broken:o1,after:o2});
ok(vid0===vid1,w+' video untouched');ok(!errs.length,w+' no errors',errs.slice(0,2));await p.close()}
await b.close();console.log(fails?fails+' FAILED':'ALL PASS');
