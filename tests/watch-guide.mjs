// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';const [slug,ch,vod]=process.argv.slice(2);
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
for(const [w,h] of [[1440,1000],[390,844]]){const mob=w<700;const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:mob,hasTouch:mob});const p=await ctx.newPage();
const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
await p.goto(`https://clutchtape.com/p/${slug}?tw=${ch}`);await p.goto(`https://clutchtape.com/p/${slug}${vod?'?vod='+encodeURIComponent(vod):''}`,{waitUntil:'load'});await p.waitForTimeout(3000);
const g=await p.evaluate(()=>{const R=s=>{const e=document.querySelector(s);if(!e||!e.getClientRects().length)return null;const r=e.getBoundingClientRect();return {x:Math.round(r.left),y:Math.round(r.top+scrollY),w:Math.round(r.width),h:Math.round(r.height)}};
 return {guide:R('#watchguide'),games:document.querySelectorAll('#watchguide .wg-g').length,picks:[...document.querySelectorAll('#watchguide .wg-pick')].map(a=>a.textContent.replace(/\s+/g,' ').trim()),player:R('#player'),table:R('#vodvs'),clips:R('main .clipsec'),sideClips:!!document.querySelector('.colside .clipsec')}});
ok(g.guide&&g.games>0,`${w}: watch guide with the session's games`,JSON.stringify({games:g.games,picks:g.picks}));
if(!mob)ok(g.guide.x>g.player.x+g.player.w-5&&!g.sideClips,`${w}: guide is beside the video, clips not in the side column`,JSON.stringify({guide:g.guide,player:g.player}));
ok(g.table&&g.table.y>g.player.y&&g.table.h>60,`${w}: session table under the video`,JSON.stringify(g.table));
ok(!g.clips||g.clips.y>(g.table?g.table.y:g.player.y),`${w}: clips below the video`,JSON.stringify(g.clips));
const play=p.locator('#watchguide .wg-play[href]').first();if(await play.count()){const before=await p.evaluate(()=>{try{return window.__sp.getCurrentTime()}catch(e){return null}});
 mob?await play.tap():await play.click();await p.waitForTimeout(6000);
 const after=await p.evaluate(()=>({t:(()=>{try{return Math.round(window.__sp.getCurrentTime())}catch(e){return null}})(),on:!!document.querySelector('#watchguide .wg-g.on'),url:location.pathname}));
 ok(after.on&&after.url.startsWith('/p/'),`${w}: ▶ in the guide plays that game in the player (stays on the page)`,JSON.stringify({before:Math.round(before||0),after}));}
await p.screenshot({path:S+`wg-${w}.png`,fullPage:mob});
ok(!errs.length,`${w}: no errors`,errs.join('|'));await ctx.close()}
console.log(bad?bad+' failed':'ALL PASS');await b.close();
