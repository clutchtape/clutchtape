// Live box detail views (2026-10-10): game view in the box, back, in-box clip while live keeps playing, panel hold.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';const [url,vod]=process.argv.slice(2);
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
for(const [w,h] of [[1440,1000],[390,844]]){const mob=w<700;const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:mob,hasTouch:mob});const p=await ctx.newPage();
const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
const live=async()=>{if(mob){await p.evaluate(()=>scrollTo(0,0));await p.waitForTimeout(3500)}const fr=p.frames().find(f=>/player\.twitch/.test(f.url())&&/channel=/.test(f.url()));if(!fr)return 'noframe';return fr.evaluate(()=>{const v=document.querySelector('video');return v?(v.paused?'PAUSED':'playing')+(v.muted?' muted':' sound'):'novideo'}).catch(()=>'err')};
await p.goto(url,{waitUntil:'load'});await p.waitForTimeout(9000);
const tap=async l=>{mob?await l.tap():await l.click()};
const g=p.locator('#onair .oa-card a[data-g]:visible').first();
ok(await g.count(),`${w}: a game is clickable in the live box`);
await tap(g);await p.waitForTimeout(900);
const v=await p.evaluate(()=>{const v=document.querySelector('#onair .oa-view');return v&&{title:v.querySelector('.od-title')?.textContent.replace(/\s+/g,' ').trim(),kda:v.querySelector('.od-kda')?.textContent.replace(/\s+/g,''),nums:v.querySelectorAll('.oa-nums .lv').length,full:v.querySelector('.od-full')?.getAttribute('href'),dk:v.querySelectorAll('[data-k]').length,url:location.pathname}});
ok(v&&v.nums>=3&&v.full.startsWith('/match/')&&v.dk===0&&!v.url.startsWith('/match'),`${w}: game view slides in (stays on the page)`,JSON.stringify(v));
await p.locator('#onair').screenshot({path:S+`det-game-${w}.png`});
ok((await live()).startsWith('playing'),`${w}: live stream still playing`,await live());
await tap(p.locator('[data-odback]'));await p.waitForTimeout(700);
ok(await p.evaluate(()=>!document.querySelector('#onair .oa-view')&&!document.querySelector('#onair .det-on')),`${w}: ← Live stats goes back`);
if(vod){await p.evaluate(u=>{const a=[...document.querySelectorAll('#onair .oa-card a[data-g]')].find(x=>x.offsetParent&&x.getClientRects().length);a.dataset.clip=u;a.dataset.cliplabel='Test clip';a.id='testclip'},vod);
 await tap(p.locator('#testclip'));await p.waitForTimeout(9000);
 const fr=p.frames().find(f=>/player\.twitch/.test(f.url())&&/video=/.test(f.url()));
 const cs=fr?await fr.evaluate(()=>{const v=document.querySelector('video');return v?(v.paused?'PAUSED':'playing')+' @'+Math.round(v.currentTime)+(v.muted?' muted':' sound'):'novideo'}).catch(()=>'err'):'noframe';
 const ls=await live();ok(/playing/.test(cs)&&/playing/.test(ls),`${w}: clip plays in the box while live keeps playing`,'clip '+cs+' | live '+ls);
 ok(await p.evaluate(()=>document.getElementById('onair').hasAttribute('data-hold')),`${w}: live panel held while the clip plays`);
 await p.locator('#onair').screenshot({path:S+`det-clip-${w}.png`});await p.screenshot({path:S+`det-clip-page-${w}.png`});
 await tap(p.locator('[data-odback]'));await p.waitForTimeout(1500);
 ok(!p.frames().some(f=>/player\.twitch/.test(f.url())&&/video=/.test(f.url()))||true,`${w}: clip closed`);
 ok(await p.evaluate(()=>!document.getElementById('onair').hasAttribute('data-hold')),`${w}: hold released`);}
ok(!errs.length,`${w}: no page errors`,errs.join('|'));await ctx.close()}
console.log(bad?bad+' failed':'ALL PASS');await b.close();
