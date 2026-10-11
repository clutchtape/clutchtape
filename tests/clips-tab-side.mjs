// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';const [slug,ch]=process.argv.slice(2);
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
for(const [w,h] of [[1440,1000],[390,844]]){const p=await b.newPage({viewport:{width:w,height:h}});
await p.goto(`https://clutchtape.com/p/${slug}?tw=${ch}`,{waitUntil:'load'});await p.waitForTimeout(800);
await p.goto(`https://clutchtape.com/p/${slug}?tab=clips`,{waitUntil:'load'});await p.waitForTimeout(2500);
console.log(w,JSON.stringify(await p.evaluate(()=>{const R=s=>{const e=document.querySelector(s);if(!e||!e.getClientRects().length)return null;const r=e.getBoundingClientRect();return {x:Math.round(r.left),y:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height)}};
 return {player:R('#player'),autoclips:R('.clipsec'),twclips:R('.twclips'),colside:R('.colside'),mediaOpen:document.getElementById('mediasec')?.open,moments:document.querySelectorAll('.clipsec .mo').length,tw:document.querySelectorAll('.twclips .clip').length}})));
await p.screenshot({path:S+`cliptab-${w}.png`});await p.close()}
await b.close();
