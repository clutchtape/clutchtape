// Show switch (2026-10-11): ▶ Video · 📊 Stats · 💬 Chat — hide/show with animation, stream keeps playing, last view stays, remembered.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const [U]=process.argv.slice(2);const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let fails=0;const ok=(c,m,d)=>{console.log((c?'PASS ':'FAIL ')+m,d!==undefined?JSON.stringify(d):'');if(!c)fails++};
for(const [w,h] of [[1440,900],[1280,720],[1024,640],[390,844]]){
  const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:w<700,hasTouch:w<700});const p=await ctx.newPage();const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
  await p.goto(U,{waitUntil:'load'});await p.waitForTimeout(9000);const tag=w+'x'+h;
  const st=()=>p.evaluate(()=>{const R=s=>{const e=document.querySelector(s);if(!e||!e.getClientRects().length)return null;const b=e.getBoundingClientRect();return [Math.round(b.width),Math.round(b.height)]};
    const f=document.querySelector('#player iframe');let vid='none';try{const v=f&&f.contentDocument&&f.contentDocument.querySelector('video');vid=v?(v.paused?'paused':'playing'):'x'}catch(e){vid='x'}
    return {pressed:[...document.querySelectorAll('.showseg [data-show]')].map(b=>b.dataset.show[0]+(b.getAttribute('aria-pressed')==='true'?'+':'-')).join(' '),player:R('#player'),onair:R('#onair'),chat:R('#twchat'),pill:R('.chattab'),so:document.documentElement.classList.contains('statsonly'),ovx:document.documentElement.scrollWidth>innerWidth}});
  const playing=async()=>{for(const f of p.frames()){if(!/player\.twitch/.test(f.url()))continue;try{const s=await f.evaluate(()=>{const v=document.querySelector('video');return v?(v.paused?'paused':'playing'):'none'});if(s!=='none')return s}catch(e){}}return 'none'};
  const click=async k=>{await p.locator(`.showseg [data-show=${k}]`).click();const an=await p.evaluate(()=>document.getAnimations().filter(a=>a.effect&&a.effect.target&&a.effect.target.closest&&a.effect.target.closest('#player,#onair,#twchat,#statsboard,#livevs')).length);await p.waitForTimeout(2200);return an};
  const s0=await st();ok(s0.pressed==='v+ s+ c+'&&s0.player&&s0.onair,tag+' switch shown, all on',s0);
  ok(await playing()==='playing',tag+' video playing at start');
  let an=await click('stats');let s1=await st();ok(!s1.onair&&s1.pressed==='v+ s- c+',tag+' Stats off: live box hidden',s1);ok(an>0,tag+' Stats off animates',an);
  if(w>=1200)ok(s1.chat&&s0.chat&&s1.chat[1]>=s0.chat[1],tag+' chat takes the room',{before:s0.chat,after:s1.chat});
  ok(await playing()==='playing',tag+' still playing after hiding stats');
  an=await click('chat');let s2=await st();ok(s2.pressed==='v+ s- c-'&&!s2.onair&&(w<=700?!s2.pill:!s2.chat),tag+' Chat off too: video only',s2);ok(an>0,tag+' Chat off animates',an);
  if(w>=1200)ok(s2.player[0]>s1.player[0]+100,tag+' video grows into the empty side',{before:s1.player,after:s2.player});
  await p.locator('.showseg [data-show=video]').click();await p.waitForTimeout(800);let s3=await st();ok(!s3.so&&s3.pressed==='v+ s- c-',tag+' last view stays (Video refuses)',s3);
  await p.reload({waitUntil:'load'});await p.waitForTimeout(6000);let s4=await st();ok(s4.pressed==='v+ s- c-'&&!s4.onair,tag+' remembered after reload',s4);
  an=await click('stats');an+=await click('chat');let s5=await st();ok(s5.pressed==='v+ s+ c+'&&s5.onair&&(w<=700?true:s5.chat),tag+' both back',s5);ok(an>0,tag+' showing animates',an);
  await p.waitForTimeout(3000);ok(await playing()==='playing',tag+' playing after bringing them back');
  await click('video');let s6=await st();ok(s6.so&&s6.onair&&(w<=700?s6.pill:s6.chat),tag+' Video off: stats + chat stay',s6);
  await click('video');await p.waitForTimeout(6000);let s7=await st();ok(!s7.so&&s7.player,tag+' Video back',s7);ok(await playing()==='playing',tag+' video plays again');
  ok(!s7.ovx&&!errs.length,tag+' no overflow / errors',errs.slice(0,2));
  await click('stats');await p.screenshot({path:S+`show-${w}-nostats.png`});await click('stats');await ctx.close()}
await b.close();console.log(fails?fails+' FAILED':'ALL PASS');
