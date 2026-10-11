// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
for(const [w,h] of [[1440,900],[1366,768],[1920,1080],[390,844]]){const mob=w<700;const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:mob,hasTouch:mob});const p=await ctx.newPage();
await p.goto(process.argv[2],{waitUntil:'load'});await p.waitForTimeout(1200);
await p.evaluate(()=>scrollTo(0,0));const bar=p.locator('#mediasec > summary');mob?await bar.tap():await bar.click();await p.waitForTimeout(1600);
const g=await p.evaluate(()=>{const e=document.querySelector('#player .embed').getBoundingClientRect(),s=document.querySelector('#mediasec>summary').getBoundingClientRect(),t=document.querySelector('.top').getBoundingClientRect();return {embedTop:Math.round(e.top),embedBottom:Math.round(e.bottom),barTop:Math.round(s.top),hdr:Math.round(t.bottom),scrollY:Math.round(scrollY),vh:innerHeight}});
ok(g.embedBottom<=g.vh+2&&g.embedTop>=g.hdr-2&&g.scrollY>0,`${w}x${h}: opened from the bar → whole video on screen`,JSON.stringify(g));
await p.locator('#mediasec > summary').click();await p.waitForTimeout(1400);
const y=await p.evaluate(()=>Math.round(scrollY));ok(y===0,`${w}x${h}: collapsed → back at the top`,'scrollY '+y);await ctx.close()}
console.log(bad?bad+' failed':'ALL PASS');await b.close();
