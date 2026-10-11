// Phone Clips-tab player (2026-10-11): true 16:9 before and after ▶ Watch; the moment picker sits under the timeline.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';const [slug,ch,W,H]=process.argv.slice(2);
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const ctx=await b.newContext({viewport:{width:+(W||412),height:+(H||915)},isMobile:true,hasTouch:true,deviceScaleFactor:2.6});const p=await ctx.newPage();
await p.goto(`https://clutchtape.com/p/${slug}?tw=${ch}`,{waitUntil:'load'});await p.goto(`https://clutchtape.com/p/${slug}?tab=clips`,{waitUntil:'load'});await p.waitForTimeout(1500);
const geo=()=>p.evaluate(()=>{const R=s=>{const e=document.querySelector(s);if(!e||!e.getClientRects().length)return null;const r=e.getBoundingClientRect();return {w:Math.round(r.width),h:Math.round(r.height),t:Math.round(r.top)}};
 const e=document.querySelector('#player .embed');return {player:R('#player'),embed:R('#player .embed'),ratio:e?(e.getBoundingClientRect().width/e.getBoundingClientRect().height).toFixed(2):null,elog:R('#elog'),etl:R('.etl'),picks:R('.et-picks'),watchH:getComputedStyle(document.getElementById('player')).getPropertyValue('--watch-height'),pStyle:document.getElementById('player').getAttribute('style')}});
console.log('before',JSON.stringify(await geo()));
const w=p.locator('.clipsec a.vod').first();if(await w.count()){await w.tap();await p.waitForTimeout(5000);}
console.log('after Watch',JSON.stringify(await geo()));
await p.screenshot({path:S+'mvid.png'});await b.close();
