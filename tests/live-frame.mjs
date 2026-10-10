// Live page: on first load the whole video is on screen with no scrolling, at 13 sizes from 320px phones to 3440px
// ultrawide (2026-10-10). Needs a channel that is LIVE right now:  node tests/live-frame.mjs 'https://clutchtape.com/p/<slug>?tw=<channel>'
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';

const sizes=[[320,568],[375,667],[390,844],[430,932],[768,1024],[1024,768],[1280,720],[1366,768],[1440,900],[1536,864],[1920,1080],[2560,1440],[3440,1440]];
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;
for(const [w,h] of sizes){const p=await b.newPage({viewport:{width:w,height:h}});
await p.goto(process.argv[2]||'https://clutchtape.com/p/x-flint-x?tw=x-flint-x',{waitUntil:'load'});await p.waitForTimeout(5000);
const r=await p.evaluate(()=>{const e=document.querySelector('#player .embed').getBoundingClientRect(),hdr=document.querySelector('.top').getBoundingClientRect();let paused;try{paused=window.__sp.isPaused()}catch(x){paused='?'}
 return {top:Math.round(e.top),bottom:Math.round(e.bottom),w:Math.round(e.width),h:Math.round(e.height),hdrBottom:Math.round(hdr.bottom),scrollY:Math.round(scrollY),paused,ovf:document.documentElement.scrollWidth-innerWidth}});
const ok=r.bottom<=h&&r.top>=r.hdrBottom;if(!ok)bad++;
console.log(`${w}x${h}`.padStart(10),ok?'FULL':'CUT ',`video ${r.w}x${r.h} (${Math.round(100*r.h/(r.w*9/16))}% of 16:9) top=${r.top} bottom=${r.bottom} scrolledTo=${r.scrollY} paused=${r.paused} ovf=${r.ovf}`);
await p.close()}
console.log(bad?`FAIL ${bad} sizes cut`:'PASS live frame: whole video on screen at load, all sizes');await b.close();if(bad)process.exit(1);
