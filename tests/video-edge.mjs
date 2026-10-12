// Video | side edge handle (2026-10-10): drag for a bigger/smaller video (live) or board vs side (Stats only), persist, reset.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;const ok=(c,m,x='')=>{console.log((c?'PASS ':'FAIL ')+m,x);if(!c)bad++};
const geo=p=>p.evaluate(()=>{const R=s=>{const e=document.querySelector(s);if(!e||!e.getClientRects().length)return null;const r=e.getBoundingClientRect();return {x:Math.round(r.left),w:Math.round(r.width),h:Math.round(r.height)}};return {video:R('#player .embed'),side:R('.colside'),board:R('#statsboard'),handle:!document.querySelector('.mainsplit').hidden,ovf:document.documentElement.scrollWidth-innerWidth}});
const drag=async(p,dx)=>{const hb=await p.locator('.mainsplit').boundingBox();const y=hb.y+Math.min(300,hb.height/2);await p.mouse.move(hb.x+6,y);await p.mouse.down();await p.mouse.move(hb.x+6+dx,y,{steps:10});await p.mouse.up();await p.waitForTimeout(600)};
for(const [name,so,lay] of [['live video',false,{}],['stats only + chat',true,{sochat:true}]]){
const ctx=await b.newContext({viewport:{width:1853,height:950}});const p=await ctx.newPage();
await p.addInitScript(([s,l])=>{if(!sessionStorage.getItem('t')){sessionStorage.setItem('t','1');localStorage.setItem('ct-show',JSON.stringify({k:location.pathname.split('/').slice(0,3).join('/'),at:Date.now(),video:!(s)}));localStorage.setItem('ct-layout',JSON.stringify(l));['ct-mainw','ct-sow','ct-sidecols'].forEach(k=>localStorage.removeItem(k))}},[so,lay]);
await p.goto(process.argv[2],{waitUntil:'load'});await p.waitForTimeout(3500);
const a=await geo(p);ok(a.handle,`${name}: handle on chat's left edge`,JSON.stringify(a));
await drag(p,180);const c=await geo(p);
if(!so)ok(c.video.w>a.video.w+120&&c.video.h>a.video.h+60&&c.side.w<a.side.w,`${name}: drag right → bigger video`,`${a.video.w}x${a.video.h} -> ${c.video.w}x${c.video.h}, side ${a.side.w} -> ${c.side.w}`);
else ok(c.board.w>a.board.w+120&&c.side.w<a.side.w,`${name}: drag right → wider board, narrower side`,`board ${a.board.w} -> ${c.board.w}, side ${a.side.w} -> ${c.side.w}`);
await p.screenshot({path:S+`main-${so?'so':'live'}.png`});
await drag(p,-360);const d=await geo(p);
if(!so)ok(d.video.w<c.video.w-200,`${name}: drag left → smaller video`,`${c.video.w} -> ${d.video.w}`);else ok(d.side.w>c.side.w+200,`${name}: drag left → wider side`,`${c.side.w} -> ${d.side.w}`);
await p.reload({waitUntil:'load'});await p.waitForTimeout(3500);const e=await geo(p);
ok(so?Math.abs(e.side.w-d.side.w)<8:Math.abs(e.video.w-d.video.w)<8,`${name}: kept after reload`,JSON.stringify(so?e.side:e.video));
await p.locator('.mainsplit').dblclick();await p.waitForTimeout(800);const f=await geo(p);
ok(so?Math.abs(f.side.w-a.side.w)<8:Math.abs(f.video.w-a.video.w)<8,`${name}: double-click → automatic size`,JSON.stringify(so?f.side:f.video));
ok(f.ovf===0,`${name}: no sideways overflow`);await ctx.close()}
console.log(bad?bad+' failed':'ALL PASS');await b.close();
