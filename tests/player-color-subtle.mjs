// Gamertag color is subtle (2026-10-10): name text only, site accent unchanged, no tinted backgrounds.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const ctx=await b.newContext({viewport:{width:1440,height:1000}});const p=await ctx.newPage();
await p.addInitScript(()=>localStorage.setItem('clutchtape.colors.v1',JSON.stringify({cykul:{color:'#5588db',ink:'#6392de',rgb:'85, 136, 219',name:'CyKul'}})));
for(const u of ['/p/cykul','/sq/d7c3bb']){await p.goto('https://clutchtape.com'+u,{waitUntil:'load'});await p.waitForTimeout(1500);
console.log(u,JSON.stringify(await p.evaluate(()=>{const tag=document.querySelector('.ct-player-tag'),cs=tag&&getComputedStyle(tag),btn=document.querySelector('.hub-tabs a.on');
 return {tags:document.querySelectorAll('.ct-player-tag').length,tagColor:cs&&cs.color,tagBg:cs&&cs.backgroundColor,acc:getComputedStyle(document.body).getPropertyValue('--acc').trim(),tabColor:btn&&getComputedStyle(btn).color,bodyBg:getComputedStyle(document.body).backgroundImage.slice(0,30)}})));
await p.screenshot({path:S+`pc${u.replace(/\W/g,'-')}.png`})}
await b.close();
