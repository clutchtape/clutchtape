// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import {chromium} from 'playwright';
const S='/tmp/fr/';const W=+(process.argv[3]||1440),H=+(process.argv[4]||900);
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const p=await b.newPage({viewport:{width:W,height:H}});
await p.goto(process.argv[2],{waitUntil:'load'});await p.waitForTimeout(800);await p.locator('#mediasec > summary').click();await p.waitForTimeout(12000);
const st=async()=>{const fr=p.frames().find(f=>/player\.twitch/.test(f.url()));return fr?fr.evaluate(()=>{const v=document.querySelector('video');return v?(v.paused?'PAUSED':'playing')+'@'+Math.round(v.currentTime):'novideo'}).catch(()=>'err'):'noframe'};
const info=await p.evaluate(()=>{const bar=document.querySelector('.etl');const R=e=>{if(!e||!e.getClientRects().length)return null;const r=e.getBoundingClientRect();return {x:Math.round(r.left),y:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height)}};
 return {bar:R(bar),hidden:bar?.hidden,marks:bar?bar.querySelectorAll('.etk').length:0,clips:bar?bar.querySelectorAll('.et-clip').length:0,sizes:[...(bar?.querySelectorAll('.etk,.et-clip')||[])].slice(0,6).map(e=>{const r=e.getBoundingClientRect();return Math.round(r.width)+'x'+Math.round(r.height)}),video:R(document.querySelector('#player .embed'))}});
console.log('before hover',await st(),JSON.stringify(info));
await p.locator('#player').screenshot({path:S+'tl-'+W+'.png'});
const k=p.locator('.etl .et-clip:visible');const n=await k.count();
if(n){for(const i of [0,Math.floor(n/2),n-1]){await k.nth(i).hover();await p.waitForTimeout(700);
 const pop=await p.evaluate(()=>{const e=document.querySelector('.et-popup');if(!e||e.hidden)return null;const r=e.getBoundingClientRect(),v=document.querySelector('#player .embed').getBoundingClientRect(),pl=document.querySelector('#player').getBoundingClientRect();return {x:Math.round(r.left),y:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height),overVideo:r.bottom>v.top&&r.top<v.bottom&&r.right>v.left&&r.left<v.right,offPlayer:r.left<pl.left-1||r.right>pl.right+1,offScreen:r.top<0||r.bottom>innerHeight}});
 console.log('hover #'+i,JSON.stringify(pop));if(i===Math.floor(n/2))await p.locator('#player').screenshot({path:S+'tl-hover-'+W+'.png'});}
 await p.waitForTimeout(1500);console.log('after hovers',await st());}
await b.close();
