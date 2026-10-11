// live stats + chat heights (2026-10-11): handle under the side column + middle handle at 1024-2560 wide; phones none.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const [U]=process.argv.slice(2);const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let fails=0;const ok=(c,m,d)=>{console.log((c?'PASS ':'FAIL ')+m,d?JSON.stringify(d):'');if(!c)fails++};
for(const [w,h] of [[1024,640],[1280,720],[1366,768],[1440,900],[1536,864],[1920,1080],[2560,1440],[390,844]]){
  const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:w<700});const p=await ctx.newPage();const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
  await p.goto(U,{waitUntil:'load'});await p.waitForTimeout(4000);await p.evaluate(()=>{const t=document.querySelector('.firsttip button, .firsttip .got');if(t)t.click()});
  const st=()=>p.evaluate(()=>{const H=s=>{const e=document.querySelector(s);return e&&e.offsetParent?Math.round(e.getBoundingClientRect().height):null};const vis=s=>[...document.querySelectorAll(s)].filter(e=>!e.hidden&&e.offsetParent).length;
    return {oa:H('#onair'),chat:H('#twchat'),bar:vis('.sidesplit:not(.sidefoot)'),foot:vis('.sidefoot'),side2:!!document.querySelector('.colside.side2'),ovx:document.documentElement.scrollWidth>innerWidth}});
  const drag=async(sel,dy)=>{const e=p.locator(sel).first();await e.evaluate(n=>n.scrollIntoView({block:'center'}));await p.waitForTimeout(700);const r=await e.boundingBox();await p.mouse.move(r.x+r.width/2,r.y+r.height/2);await p.mouse.down();for(let i=1;i<=6;i++)await p.mouse.move(r.x+r.width/2,r.y+r.height/2+dy*i/6);await p.mouse.up();await p.waitForTimeout(300)};
  const s0=await st();const tag=w+'x'+h;
  if(w<=700){ok(!s0.bar&&!s0.foot&&!s0.ovx,tag+' phone: no handles (chat is a sheet)',s0);await ctx.close();continue}
  ok(s0.foot===1,tag+' handle under the side shown',s0);
  await drag('.sidefoot',120);const s1=await st();
  const grew=s0.side2||s0.mode==='x'?(s1.oa>s0.oa+60&&s1.chat>s0.chat+60):(s1.chat>s0.chat+60);
  ok(grew,tag+' drag bottom handle down: taller',{before:s0,after:s1});
  if(s0.bar){await drag('.sidesplit:not(.sidefoot)',-60);const s2=await st();ok(s2.oa<s1.oa-30,tag+' drag middle handle up: stats shorter',{before:s1,after:s2})}
  const s3=await st();await p.reload({waitUntil:'load'});await p.waitForTimeout(3000);const s4=await st();
  ok(Math.abs(s4.oa-s3.oa)<12&&Math.abs(s4.chat-s3.chat)<12,tag+' kept after reload',{before:s3,after:s4});
  await p.locator('.sidefoot').first().dblclick();if(s0.bar)await p.locator('.sidesplit:not(.sidefoot)').first().dblclick();await p.waitForTimeout(300);const s5=await st();
  ok(Math.abs(s5.chat-s0.chat)<12&&Math.abs(s5.oa-s0.oa)<12,tag+' double-click resets',{start:s0,reset:s5});
  ok(!s5.ovx&&!errs.length,tag+' no overflow / errors',errs.slice(0,2));
  await drag('.sidefoot',120);await p.screenshot({path:S+`vres-${w}.png`});await ctx.close()}
await b.close();console.log(fails?fails+' FAILED':'ALL PASS');
