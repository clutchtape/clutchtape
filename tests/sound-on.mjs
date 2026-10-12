// Sound on (2026-10-12): after a click on the page, the main angle plays with sound on desktop; nothing ends up paused.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const [U]=process.argv.slice(2);
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const p=await b.newPage({viewport:{width:1440,height:900}});
await p.goto(U,{waitUntil:'load'});await p.waitForTimeout(1500);
await p.mouse.click(60,22);                 /* the "Watch together" title: no control there */
await p.waitForTimeout(20000);
const st=[];for(const f of p.frames()){if(!/player\.twitch/.test(f.url()))continue;try{st.push(await f.evaluate(()=>{const v=document.querySelector('video');return v?(v.paused?'PAUSED':'playing')+(v.muted||v.volume===0?' muted':' SOUND'):'none'}))}catch(e){st.push('err')}}
console.log('with a click:',JSON.stringify(st));await b.close();
