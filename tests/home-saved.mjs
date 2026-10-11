// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
import fs from 'fs';
const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
for(const [w,h] of [[1440,900],[390,844]]){const p=await b.newPage({viewport:{width:w,height:h},isMobile:w<700});
await p.addInitScript(()=>localStorage.setItem('clutchtape.saved.v1',JSON.stringify([{label:'CyKul + iTz So Frosty',url:'/sq/d7c3bb'},{label:'x Ghost x + x Flint x',url:'/sq/7b802a'},{label:'CyKul',url:'/p/cykul'},{label:'x Ghost x',url:'/p/x-ghost-x'},{label:'TriPPPeY',url:'/p/tripppey'}])));
await p.goto('https://clutchtape.com/',{waitUntil:'load'});await p.waitForTimeout(6000);
console.log(w,JSON.stringify(await p.evaluate(()=>{const R=s=>{const e=document.querySelector(s);if(!e||!e.getClientRects().length)return null;const r=e.getBoundingClientRect();return Math.round(r.top+scrollY)+'+'+Math.round(r.height)};
 return {personal:R('.personal-home'),hero:R('.herowrap'),cards:document.querySelectorAll('#home-cards .personal-card').length,picks:document.querySelectorAll('#home-picks .personal-card').length,inbox:document.querySelectorAll('#home-inbox > *').length,saved:R('#saved-profiles'),doc:document.documentElement.scrollHeight,sections:[...document.querySelectorAll('.personal-home > *')].map(e=>(e.id||e.className).slice(0,20)+':'+Math.round(e.getBoundingClientRect().height))}})));
await p.screenshot({path:S+`home-saved-${w}.png`,fullPage:true});await p.close()}
await b.close();
