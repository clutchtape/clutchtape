// Stats only + Keep chat, desktop (2026-10-10): chat left / live stats right side by side, on screen at 1366-1920, side swap.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
let bad=0;
for(const [w,h,side] of [[1440,1000,'left'],[1853,950,'left'],[1920,1080,'left'],[1366,768,'left'],[1853,950,'right']]){const ctx=await b.newContext({viewport:{width:w,height:h}});const p=await ctx.newPage();
await p.addInitScript(sd=>{localStorage.setItem('ct-show',JSON.stringify({k:location.pathname.split('/').slice(0,3).join('/'),at:Date.now(),video:false}));localStorage.setItem('ct-layout',JSON.stringify({sochat:true,side:sd}))},side);
await p.goto(process.argv[2],{waitUntil:'load'});await p.waitForTimeout(2500);
const g=await p.evaluate(()=>{const R=s=>{const e=document.querySelector(s);if(!e||!e.getClientRects().length)return null;const r=e.getBoundingClientRect();return {x:Math.round(r.left),y:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height),b:Math.round(r.bottom)}};return {board:R('#statsboard'),chat:R('#twchat'),onair:R('#onair'),ovf:document.documentElement.scrollWidth-innerWidth}});
const ok=g.chat&&g.onair&&(side==='left'?g.chat.x<g.onair.x:g.chat.x>g.onair.x)&&Math.abs(g.chat.y-g.onair.y)<4&&g.chat.b<=h&&g.ovf===0&&g.board.x<g.chat.x;
if(!ok)bad++;console.log(`${w}x${h} side=${side}`.padEnd(22),ok?'OK ':'BAD',JSON.stringify(g));
await p.screenshot({path:S+`sochat2-${w}-${side}.png`});await ctx.close()}
console.log(bad?bad+' failed':'ALL PASS');await b.close();
