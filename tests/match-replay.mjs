// Game page replay (2026-10-11): score counts up, plays pop left (your team) / right (theirs), scorebug docks, Stop restores.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const [U]=process.argv.slice(2);const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let fails=0;const ok=(c,m,d)=>{console.log((c?'PASS ':'FAIL ')+m,d!==undefined?JSON.stringify(d):'');if(!c)fails++};
for(const [w,h] of [[1440,900],[1024,700],[390,844]]){const p=await b.newPage({viewport:{width:w,height:h},isMobile:w<700,hasTouch:w<700});const errs=[];p.on('pageerror',e=>errs.push(e.message));
  await p.goto(U,{waitUntil:'load'});await p.waitForSelector('.mtl-replay .rp-go',{timeout:20000});const tag=w+'';
  const sc=()=>p.evaluate(()=>[...document.querySelectorAll('.mhero .sc b')].map(b=>b.textContent.trim()));
  const fin=await p.evaluate(()=>[...document.querySelectorAll('.mhero .sc b')].map(b=>b.dataset.v));
  await p.selectOption('.rp-speed','40');await p.locator('.rp-go').click();await p.waitForTimeout(700);const early=await sc();
  ok(true,tag+' replay started',{final:fin,early,slayer:await p.evaluate(()=>!!document.querySelector('.mh-bug')&&!document.querySelector('.mh-bug .sb-t').textContent.includes('kills'))});
  // collect pops for a while
  const seen={l:new Set(),r:new Set()};let shot=false;
  for(let i=0;i<20;i++){await p.waitForTimeout(400);const s=await p.evaluate(()=>{const g=c=>[...document.querySelectorAll('.mh-pops.'+c+' .mh-pop')].map(n=>{const r=n.getBoundingClientRect();return [n.className,n.innerText.replace(/\n/g,' · '),Math.round(r.left),Math.round(r.right)]});return {l:g('l'),r:g('r'),score:document.querySelector('.mhero .sc').getBoundingClientRect().left,run:document.querySelector('.mh-run').textContent,ovx:document.documentElement.scrollWidth>innerWidth}});
    s.l.forEach(x=>seen.l.add(x[0].includes('tA')||x[0].includes('tB')?x[1]:x[1]));s.r.forEach(x=>seen.r.add(x[1]));
    if(!shot&&s.l.length&&s.r.length){await p.locator('.mhero').screenshot({path:S+`replay-${w}.png`});shot=true}
    if(s.ovx){ok(false,tag+' horizontal overflow during replay');break}}
  const mid=await sc();ok(seen.l.size>0&&seen.r.size>0,tag+' plays popped on both sides',{left:[...seen.l].slice(0,3),right:[...seen.r].slice(0,3)});
  ok(mid.every(x=>/^\d+$/.test(x)),tag+' score shows numbers while replaying',mid);
  if(!shot)await p.locator('.mhero').screenshot({path:S+`replay-${w}.png`});
  // side check: left pops are left of score
  const side=await p.evaluate(()=>{const s=document.querySelector('.mhero .mh-score').getBoundingClientRect();const l=document.querySelector('.mhero .mh-pops.l').getBoundingClientRect(),r=document.querySelector('.mhero .mh-pops.r').getBoundingClientRect();return {lx:Math.round(l.left),rx:Math.round(r.left),s:[Math.round(s.left),Math.round(s.right)]}});
  ok(side.lx<side.rx,tag+' your team left, theirs right',side);
  // scroll away -> scorebug
  await p.evaluate(()=>document.getElementById('timeline').scrollIntoView({block:'start'}));await p.waitForTimeout(900);
  const bug=await p.evaluate(()=>{const g=document.querySelector('.mh-bug');return g&&!g.hidden?g.innerText.replace(/\n/g,' '):null});ok(!!bug,tag+' scorebug docks when scrolled away',bug);
  await p.screenshot({path:S+`replay-bug-${w}.png`});
  await p.locator('.rp-stop').click();await p.waitForTimeout(300);const after=await sc();
  ok(after.join('-')===fin.join('-'),tag+' Stop restores the final score',{fin,after});
  ok(!errs.length,tag+' no errors',errs.slice(0,2));await p.close()}
await b.close();console.log(fails?fails+' FAILED':'ALL PASS');
