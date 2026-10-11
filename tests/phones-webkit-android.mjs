// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
// home, player page, Stream & clips glide + 16:9 video, Clips tab, watch guide (?vod), squad, Arrange; overflow/errors.
import {chromium,webkit,devices} from 'playwright';
const B='https://clutchtape.com',S='/tmp/dev/';
import fs from 'fs';fs.mkdirSync(S,{recursive:true});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
for(const [name,type,dev] of [['iPhone 13 (WebKit)',webkit,devices['iPhone 13']],['Pixel 7 (Chrome)',chromium,devices['Pixel 7']]]){
 const b=await type.launch(type===chromium?{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH}:{executablePath:process.env.PLAYWRIGHT_WEBKIT_EXECUTABLE_PATH||undefined});
 const ctx=await b.newContext({...dev});const p=await ctx.newPage();const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap|ResizeObserver/.test(e.message))errs.push(e.message.slice(0,100))});
 const ovf=()=>p.evaluate(()=>document.documentElement.scrollWidth-innerWidth);
 await p.goto(B+'/',{waitUntil:'load'});await p.waitForTimeout(1500);ok(await ovf()<=1,`${name}: home, no sideways overflow`);
 await p.goto(B+'/p/x-ghost-x?tw=xghostx',{waitUntil:'load'});await p.waitForTimeout(1500);
 ok(await ovf()<=1,`${name}: player page, no overflow`);
 const bar=p.locator('#mediasec > summary');await bar.tap();await p.waitForTimeout(2500);
 let g=await p.evaluate(()=>{const e=document.querySelector('#player .embed').getBoundingClientRect();return {w:Math.round(e.width),h:Math.round(e.height),top:Math.round(e.top),bottom:Math.round(e.bottom),vh:innerHeight,y:Math.round(scrollY)}});
 ok(g.h>100&&Math.abs(g.w/g.h-16/9)<0.12&&g.top>=0&&g.bottom<=g.vh+2,`${name}: Stream & clips opens, video 16:9 and on screen`,JSON.stringify(g));
 await p.locator('#mediasec > summary').tap();await p.waitForTimeout(1500);ok(await p.evaluate(()=>scrollY)<5,`${name}: collapse goes back to the top`);
 await p.goto(B+'/p/x-ghost-x?tab=clips',{waitUntil:'load'});await p.waitForTimeout(1500);
 g=await p.evaluate(()=>{const e=document.querySelector('#player .embed');if(!e)return null;const r=e.getBoundingClientRect();return {w:Math.round(r.width),h:Math.round(r.height)}});
 ok(!g||Math.abs(g.w/g.h-16/9)<0.12,`${name}: Clips tab video 16:9`,JSON.stringify(g));
 const vod=await p.evaluate(()=>(document.querySelector('a.vod[href*="/videos/"]')?.href||'').match(/videos\/(\d+)\?t=([0-9hms]+)/));
 if(vod){await p.goto(B+'/p/x-ghost-x?vod='+encodeURIComponent(vod[1]+'@'+vod[2]),{waitUntil:'load'});await p.waitForTimeout(2500);
  const w=await p.evaluate(()=>({open:document.getElementById('mediasec')?.open,guide:document.querySelectorAll('#watchguide .wg-g').length,ovf:document.documentElement.scrollWidth-innerWidth}));
  ok(w.open&&w.guide>0&&w.ovf<=1,`${name}: ?vod link opens the video + watch guide`,JSON.stringify(w));}
 await p.goto(B+'/sq/d7c3bb',{waitUntil:'load'});await p.waitForTimeout(1500);ok(await ovf()<=1&&await p.locator('#sqtable, #playnow').count()>0,`${name}: squad page, table first, no overflow`);
 await p.locator('.arrbtn').tap();await p.waitForTimeout(400);const ac=await p.evaluate(()=>{const r=document.querySelector('.arrcard').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1});ok(ac,`${name}: Arrange sheet fits the screen`);
 await p.screenshot({path:S+name.replace(/\W+/g,'-')+'-squad.png'});
 ok(!errs.length,`${name}: no page errors`,errs.join(' | '));
 await b.close()}
console.log(bad?bad+' failed':'ALL PASS');
