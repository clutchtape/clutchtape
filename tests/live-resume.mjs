// Live stream starts again after Stats only -> Show stream (2026-10-10).
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
import fs from 'fs';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const st=async p=>{const fr=p.frames().find(f=>/player\.twitch/.test(f.url()));if(!fr)return 'noframe';try{return await fr.evaluate(()=>{const v=document.querySelector('video');return v?(v.paused?'PAUSED':'playing')+'@'+Math.round(v.currentTime):'novideo'})}catch(e){return 'err'}};
let bad=0;
for(const [name,w,h,start] of [['desk',1440,1000,'stream'],['desk-load-statsonly',1440,1000,'stats'],['phone',390,844,'stream'],['phone-load-statsonly',390,844,'stats']]){
const mob=w<700;const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:mob,hasTouch:mob});const p=await ctx.newPage();
if(start==='stats')await p.addInitScript(()=>{try{localStorage.setItem('ct-statsonly','1')}catch(e){}});
await p.goto(process.argv[2],{waitUntil:'load'});await p.waitForTimeout(start==='stats'?3000:11000);const a=await st(p);
if(start==='stream'){await p.locator('[data-statsonly]:visible').first().click();await p.waitForTimeout(3000)}
const mid=await st(p);
await p.locator('[data-statsonly]:visible').first().click();await p.waitForTimeout(10000);const c=await st(p);
const ok=c.startsWith('playing');if(!ok)bad++;console.log(name.padEnd(22),ok?'OK ':'BAD','load',a,'| stats only',mid,'| back to stream',c);await ctx.close()}
console.log(bad?bad+' failed':'stream plays after leaving Stats only');await b.close();
