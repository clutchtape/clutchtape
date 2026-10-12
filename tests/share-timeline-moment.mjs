// Multistream (2026-10-12): share-timeline-moment.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const [U]=process.argv.slice(2);
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const c1=await b.newContext({viewport:{width:1440,height:900}});await c1.grantPermissions(['clipboard-read','clipboard-write'],{origin:'https://clutchtape.com'});
const p=await c1.newPage();let prompted=null;p.on('dialog',d=>{prompted=d.defaultValue();d.dismiss()});
await p.goto(U,{waitUntil:'load'});await p.waitForSelector('#mtl .et-clip',{state:'attached',timeout:30000});await p.waitForTimeout(2000);
const m=p.locator('#mtl .et-clip').nth(3);const bb=await m.boundingBox();await p.mouse.move(bb.x+bb.width/2,bb.y+bb.height/2);await p.waitForTimeout(400);
const info=await p.evaluate(()=>{const pp=document.querySelector('#mtl .et-popup');return {txt:pp.querySelector('b').textContent,share:!!pp.querySelector('.et-share'),ms:+(pp.querySelector('.et-share')||{dataset:{}}).dataset.ms}});
console.log('popup',JSON.stringify(info));
await p.locator('#mtl .et-popup .et-share').click();await p.waitForTimeout(800);
const link=prompted||await p.evaluate(()=>navigator.clipboard.readText().catch(()=>null));console.log('link',link);
const c2=await b.newContext({viewport:{width:1440,height:900}});const q=await c2.newPage();await q.goto(link,{waitUntil:'load'});await q.waitForTimeout(14000);
const at=+new URL(link).searchParams.get('at');
const gw=await q.evaluate(()=>{const tr=document.querySelector('table.night tr[data-mid^="547a4f94"]');return tr&&tr.dataset.gwatch?JSON.parse(tr.dataset.gwatch).map(x=>({who:x.who,sec:x.sec})):null});
const times=[];for(const f of q.frames()){if(!/player\.twitch/.test(f.url()))continue;try{times.push(await f.evaluate(()=>{const v=document.querySelector('video');return v?Math.round(v.currentTime):null}))}catch(e){times.push('x')}}
console.log('at',at,'film s',Math.round(info.ms/1000),'angles',JSON.stringify(gw&&gw.map(g=>g.who+' should be ~'+(g.sec+at))),'players at',JSON.stringify(times),'multi open',await q.evaluate(()=>!document.getElementById('multi').hidden));
await b.close();
