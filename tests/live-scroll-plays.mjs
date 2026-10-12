// Live page scroll (2026-10-12): the video keeps playing while you scroll (desktop mini player, phone sticky).
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const [U,w,h]=process.argv.slice(2);
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const p=await b.newPage({viewport:{width:+(w||1440),height:+(h||900)},isMobile:+(w||1440)<700,hasTouch:+(w||1440)<700});
await p.goto(U,{waitUntil:'load'});await p.waitForTimeout(12000);
const vid=async()=>{for(const f of p.frames()){if(!/player\.twitch/.test(f.url())||/clip/.test(f.url()))continue;try{const s=await f.evaluate(()=>{const v=document.querySelector('video');return v?(v.paused?'PAUSED':'play')+'@'+Math.round(v.currentTime):'none'});if(s!=='none')return s}catch(e){}}return 'none'};
const pos=()=>p.evaluate(()=>{const e=document.getElementById('player');const r=e.getBoundingClientRect();const em=e.querySelector('.embed').getBoundingClientRect();return [Math.round(scrollY),Math.round(em.top),Math.round(em.bottom),document.documentElement.classList.contains('vid-pip')?'pip':document.documentElement.classList.contains('vid-pin')?'pin':'-']});
const log=[];log.push(['start',await pos(),await vid()]);
const H=await p.evaluate(()=>document.documentElement.scrollHeight);
for(let y=150;y<Math.min(H,4000);y+=40){await p.mouse.wheel(0,40);await p.waitForTimeout(120);log.push(['down',await pos(),await vid()])}
await p.waitForTimeout(3000);log.push(['bottom wait',await pos(),await vid()]);
await p.evaluate(()=>scrollTo({top:0}));await p.waitForTimeout(6000);log.push(['back top',await pos(),await vid()]);
log.forEach(l=>console.log(JSON.stringify(l)));await b.close();
