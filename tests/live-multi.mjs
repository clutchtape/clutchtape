// Squad multistream layout (2026-10-10): fakes a 2nd live member by showing the same live channel twice.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {createRequire} from 'module';const require=createRequire(import.meta.url);
import {chromium} from 'playwright';
const S='/tmp/fr/';  // screenshots
const [url,ch]=process.argv.slice(2);
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
for(const [w,h] of (process.argv[4]?JSON.parse(process.argv[4]):[[1920,1080],[1853,950],[1440,1000],[768,1024],[390,844]])){const mob=w<700;const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:mob,hasTouch:mob});const p=await ctx.newPage();
const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
await p.route(u=>u.href.startsWith(url),async r=>{const res=await r.fetch();let body=await res.text();
 const streams=JSON.stringify([{channel:ch,gamertag:'Player A',title:'t',viewers:1},{channel:ch,gamertag:'Player B',title:'t',viewers:1}]).replace(/'/g,'&#39;');
 body=body.replace('<div class="embed"><div id="tplayer"></div></div>','<div class="embed"><div id="tplayer"></div></div><div class="lm-bar" id="lmbar" data-streams=\''+streams+'\'><span class="lm-lab">🔊 Sound</span><button type="button" class="lm-aud on" data-i="0">Player A</button><button type="button" class="lm-aud" data-i="1">Player B</button><button type="button" class="lm-mode" data-lmmode><span class="lm-one">One stream</span><span class="lm-all">All 2 streams</span></button></div>');
 await r.fulfill({response:res,body,headers:{...res.headers(),'content-length':undefined}})});
await p.goto(url,{waitUntil:'load'});await p.waitForTimeout(13000);
const st=await Promise.all(p.frames().filter(f=>/player\.twitch/.test(f.url())).map(f=>f.evaluate(()=>{const v=document.querySelector('video');return v?(v.paused?'PAUSED':'play')+'@'+Math.round(v.currentTime)+(v.muted?'m':'🔊'):'none'}).catch(()=>'err')));
const g=await p.evaluate(()=>{const R=s=>{const e=document.querySelector(s);if(!e)return '-';const r=e.getBoundingClientRect();return `${Math.round(r.left)},${Math.round(r.top)} ${Math.round(r.width)}x${Math.round(r.height)}`};
 return {cells:[...document.querySelectorAll('.lm-cell')].map(c=>{const r=c.getBoundingClientRect();return Math.round(r.width)+'x'+Math.round(r.height)}),bar:R('#lmbar'),vs:R('#livevs'),onair:R('#onair'),chat:R('#twchat'),side2:!!document.querySelector('.colside.side2'),ovf:document.documentElement.scrollWidth-innerWidth}});
console.log(`${w}x${h}`,JSON.stringify(st),JSON.stringify(g),errs.join('|'));
await p.screenshot({path:S+`lm-${w}.png`});
if(w===1440){await p.click('.lm-aud[data-i="1"]');await p.waitForTimeout(1500);await p.click('[data-lmmode]');await p.waitForTimeout(3000);
 const st2=await Promise.all(p.frames().filter(f=>/player\.twitch/.test(f.url())).map(f=>f.evaluate(()=>{const v=document.querySelector('video');return v?(v.paused?'PAUSED':'play')+(v.muted?'m':'🔊'):'none'}).catch(()=>'err')));
 console.log('  after sound=B + One stream:',JSON.stringify(st2),await p.evaluate(()=>[...document.querySelectorAll('.lm-cell')].map(c=>c.hidden?'hidden':Math.round(c.getBoundingClientRect().width)+'x'+Math.round(c.getBoundingClientRect().height)).join(' ')));
 await p.screenshot({path:S+'lm-1440-one.png'});await p.click('[data-lmmode]');}
await ctx.close()}
await b.close();
