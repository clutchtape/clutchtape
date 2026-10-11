// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';const base=process.argv[2];
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
for(const [w,h] of [[1440,1000],[390,844]]){const p=await b.newPage({viewport:{width:w,height:h}});
for(const t of ['','?tab=sessions','?tab=clips','?tab=analysis','?tab=records']){await p.goto(base+t,{waitUntil:'load'});await p.waitForTimeout(1200);
 const r=await p.evaluate(()=>{const f=document.querySelector('footer.foot').getBoundingClientRect();return {footTop:Math.round(f.top+scrollY),footBottom:Math.round(f.bottom+scrollY),docH:document.documentElement.scrollHeight,vh:innerHeight,gapBelowFooter:Math.round(document.documentElement.scrollHeight-(f.bottom+scrollY)),floating:Math.round(innerHeight-(f.bottom+scrollY))}});
 console.log(w,(t||'latest').padEnd(16),JSON.stringify(r));}
await p.goto(base,{waitUntil:'load'});await p.waitForTimeout(1000);await p.evaluate(()=>scrollTo(0,260));await p.waitForTimeout(500);
console.log(w,'scrolled 260:',JSON.stringify(await p.evaluate(()=>{const t=document.querySelector('.top'),c=document.querySelector('.memchip');const tr=t.getBoundingClientRect(),cr=c&&c.getBoundingClientRect();return {header:[Math.round(tr.top),Math.round(tr.bottom),getComputedStyle(t).position],chip:cr&&[Math.round(cr.top),Math.round(cr.bottom)],hubHead:getComputedStyle(document.querySelector('.hub-head')).position,chipVisible:cr&&cr.bottom>tr.bottom}})));
await p.screenshot({path:S+`sq-scrolled-${w}.png`});await p.close()}
await b.close();
