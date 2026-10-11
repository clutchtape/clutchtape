// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const p=await b.newPage({viewport:{width:1440,height:900}});
await p.goto(process.argv[2],{waitUntil:'load'});await p.waitForTimeout(800);await p.locator('#mediasec > summary').click();await p.waitForTimeout(10000);
const st=async()=>{const fr=p.frames().find(f=>/player\.twitch/.test(f.url()));return fr.evaluate(()=>{const v=document.querySelector('video');return (v.paused?'PAUSED':'playing')+'@'+Math.round(v.currentTime)}).catch(()=>'err')};
console.log('start',await st(),await p.evaluate(()=>Math.round(document.querySelector('#player .embed').getBoundingClientRect().top)));
for(const dy of [40,90,200]){await p.evaluate(d=>scrollBy(0,d),dy);await p.waitForTimeout(3000);
 console.log('scrolled',dy,await st(),'video top',await p.evaluate(()=>Math.round(document.querySelector('#player .embed').getBoundingClientRect().top)),'covered by:',await p.evaluate(()=>{const e=document.querySelector('#player .embed').getBoundingClientRect();const el=document.elementFromPoint(e.left+e.width/2,Math.max(1,e.top+5));return el?(el.tagName+'.'+String(el.className).slice(0,30)):'-'}));
 await p.evaluate(()=>scrollTo(0,document.querySelector('#mediasec').getBoundingClientRect().top+scrollY-53));await p.waitForTimeout(3000);console.log('  back',await st())}
await b.close();
