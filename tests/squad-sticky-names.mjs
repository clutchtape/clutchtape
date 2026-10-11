// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
for(const [w,h] of [[1440,900],[1366,768]]){const p=await b.newPage({viewport:{width:w,height:h}});await p.goto(process.argv[2],{waitUntil:'load'});await p.waitForTimeout(1200);
const g=()=>p.evaluate(()=>{const R=s=>{const e=document.querySelector(s);if(!e||!e.getClientRects().length)return null;const r=e.getBoundingClientRect();return [Math.round(r.top),Math.round(r.bottom)]};return {top:R('.top'),names:R('.hub-head'),chip:R('.memchip'),bar:R('#mediasec>summary'),video:R('#player .embed'),y:Math.round(scrollY)}});
await p.evaluate(()=>scrollTo(0,400));await p.waitForTimeout(500);let a=await g();
ok(a.names&&a.chip&&a.names[0]>=a.top[1]-1&&a.chip[0]>=a.top[1],`${w}: names stay visible under the header when scrolled`,JSON.stringify(a));
await p.evaluate(()=>scrollTo(0,0));const bar=p.locator('#mediasec>summary');if(await bar.count()){await bar.click();await p.waitForTimeout(1800);a=await g();
 ok(a.bar[0]>=a.names[1]-1&&a.video[0]>=a.bar[1]-1&&a.video[1]<=h+1,`${w}: Stream & clips bar under the names, whole video on screen`,JSON.stringify(a));
 await p.screenshot({path:S+`sqstick-${w}.png`});}
await p.close()}
console.log(bad?bad+' failed':'ALL PASS');await b.close();
