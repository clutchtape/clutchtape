// chat | live stats width handle (2026-10-10): drag, persist, double-click reset — stats only + chat, live beside, chat right.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
for(const [name,w,h,lay,so] of [['stats only + chat',1853,950,{sochat:true},'1'],['live, chat beside',1853,950,{chat:'beside'},'0'],['stats only, chat right',1440,1000,{sochat:true,side:'right'},'1']]){
const ctx=await b.newContext({viewport:{width:w,height:h}});const p=await ctx.newPage();
await p.addInitScript(([l,s])=>{localStorage.setItem('ct-show',JSON.stringify({k:location.pathname.split('/').slice(0,3).join('/'),at:Date.now(),video:s!=='1'}));localStorage.setItem('ct-layout',JSON.stringify(l));if(!sessionStorage.getItem('t')){sessionStorage.setItem('t','1');localStorage.removeItem('ct-sidecols')}},[lay,so]);
await p.goto(process.argv[2],{waitUntil:'load'});await p.waitForTimeout(3000);
const W=()=>p.evaluate(()=>({chat:Math.round(document.getElementById('twchat').getBoundingClientRect().width),stats:Math.round(document.getElementById('onair').getBoundingClientRect().width),handle:!document.querySelector('.colsplit').hidden}));
const a=await W();ok(a.handle,`${name}: handle shown`,JSON.stringify(a));
const hb=await p.locator('.colsplit').boundingBox();const dir=lay.side==='right'?1:-1;
await p.mouse.move(hb.x+6,hb.y+hb.height/2);await p.mouse.down();await p.mouse.move(hb.x+6+dir*80,hb.y+hb.height/2,{steps:8});await p.mouse.up();await p.waitForTimeout(300);
const bb=await W();ok(bb.chat<a.chat-50&&bb.stats>a.stats+50,`${name}: dragging makes chat narrower, stats wider`,JSON.stringify(a)+' -> '+JSON.stringify(bb));
await p.screenshot({path:S+`cols-${name.replace(/\W+/g,'-')}.png`});
await p.reload({waitUntil:'load'});await p.waitForTimeout(3000);const c=await W();ok(Math.abs(c.chat-bb.chat)<6,`${name}: kept after reload`,JSON.stringify(c));
await p.locator('.colsplit').dblclick();await p.waitForTimeout(300);const d=await W();ok(Math.abs(d.chat-a.chat)<6,`${name}: double-click resets`,JSON.stringify(d));
await ctx.close()}
console.log(bad?bad+' failed':'ALL PASS');await b.close();
