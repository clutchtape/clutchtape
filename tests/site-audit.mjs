// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
// Checks: status, page errors, sideways overflow, floating footer, squashed/covered video, deep links landing where they promise, dead internal links.
import {chromium} from 'playwright';
const B='https://clutchtape.com',S='/tmp/audit/';
import fs from 'fs';fs.mkdirSync(S,{recursive:true});
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const issues=[];const note=(u,w,m)=>{issues.push(`${w} ${u} :: ${m}`)};
// discover dynamic deep links from real pages
const d=await b.newPage();await d.goto(B+'/p/x-ghost-x?tw=xghostx');
const disc=async(u,fn)=>{await d.goto(B+u,{waitUntil:'load'});await d.waitForTimeout(600);return d.evaluate(fn)};
const prof=await disc('/p/cykul',()=>({match:document.querySelector('.gamelog a[href^="/match/"]')?.getAttribute('href'),prev:document.querySelector('.sessbtn[rel=prev]')?.getAttribute('href'),vod:(document.querySelector('a.vod[href*="/videos/"]')?.href||'').match(/videos\/(\d+)\?t=([0-9hms]+)/)}));
const sq=await disc('/sq/d7c3bb',()=>({watch:document.querySelector('[data-watch][data-key]')?.dataset.key,game:document.querySelector('.gamelog a[href^="/match/"]')?.getAttribute('href'),glink:[...document.querySelectorAll('a[href*="/g/"]')].map(a=>a.getAttribute('href'))[0]}));
const sqs=await disc('/sq/d7c3bb?tab=sessions',()=>[...document.querySelectorAll('a[href*="/sq/"],a[href*="session="]')].map(a=>a.getAttribute('href')).filter(h=>/session=|\/g\//.test(h)).slice(0,2));
console.log('discovered',JSON.stringify({prof,sq,sqs}));
const vodParam=prof.vod?`${prof.vod[1]}@${prof.vod[2]}`:null;
const P=[
 ['/',{}],['/about',{}],['/privacy',{}],['/close',{}],['/nope-404',{status:404}],['/live',{}],
 ['/p/cykul',{}],['/p/cykul?tab=sessions',{}],['/p/cykul?tab=clips',{}],['/p/cykul?tab=analysis',{}],['/p/cykul?tab=records',{}],
 ['/p/cykul?kind=all',{}],['/p/cykul?kind=custom',{}],
 prof.prev&&[prof.prev,{session:true}],
 vodParam&&['/p/cykul?vod='+encodeURIComponent(vodParam),{vod:true}],
 ['/p/x-ghost-x',{}],['/p/x-ghost-x?tab=clips',{}],
 ['/p/cykul/color',{}],
 prof.match&&[prof.match,{}],prof.match&&[prof.match+(prof.match.includes('?')?'&':'?')+'at=60#recap',{recap:true}],
 ['/sq/d7c3bb',{}],['/sq/d7c3bb?tab=sessions',{}],['/sq/d7c3bb?tab=clips',{}],['/sq/d7c3bb?tab=analysis',{}],['/sq/d7c3bb?tab=records',{}],
 sq.watch&&['/sq/d7c3bb?watch='+sq.watch,{watch:true}],sq.glink&&[sq.glink,{}],...(sqs||[]).map(h=>[h,{}]),
 ['/sq/7b802a',{}],['/squad/cykul,itz-so-frosty',{}],
 ['/history/cykul,itz-so-frosty',{}],['/weekly/cykul,itz-so-frosty',{}],['/practice/cykul,itz-so-frosty',{}],['/live/cykul,itz-so-frosty',{}],
].filter(Boolean);
const links=new Set();
for(const [w,h] of [[1440,900],[390,844]]){const mob=w<700;const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:mob,hasTouch:mob});
 const p=await ctx.newPage();await p.goto(B+'/p/x-ghost-x?tw=xghostx');
 for(const [u,exp] of P){const errs=[],bad=[];p.removeAllListeners('pageerror');p.removeAllListeners('response');
  p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message.slice(0,120))});
  p.on('response',r=>{const x=r.url();if(x.startsWith(B)&&r.status()>=400&&!x.includes('/nope-404'))bad.push(r.status()+' '+x.replace(B,''))});
  let res;try{res=await p.goto(B+u,{waitUntil:'load',timeout:45000})}catch(e){note(u,w,'load failed '+e.message.slice(0,80));continue}
  await p.waitForTimeout(exp.vod||exp.watch?6000:1800);
  const st=res?res.status():0;if(st!==(exp.status||200))note(u,w,'status '+st);
  const r=await p.evaluate(()=>{const f=document.querySelector('footer.foot');const fb=f?f.getBoundingClientRect().bottom+scrollY:0;
   const pl=document.querySelector('#player .embed');const pr=pl&&pl.getClientRects().length?pl.getBoundingClientRect():null;
   const ifr=document.querySelector('#player iframe');let cover=[];if(ifr&&pr){const R=ifr.getBoundingClientRect();for(const e of document.querySelectorAll('body *')){if(e===ifr||e.contains(ifr)||ifr.contains(e)||!e.checkVisibility())continue;const c=getComputedStyle(e);if(c.display==='none'||c.visibility==='hidden'||c.pointerEvents==='none'&&+c.opacity===0)continue;const q=e.getBoundingClientRect();if(!q.width||!q.height)continue;const ix=Math.min(q.right,R.right)-Math.max(q.left,R.left),iy=Math.min(q.bottom,R.bottom)-Math.max(q.top,R.top);if(ix>2&&iy>2&&(c.position==='fixed'||c.position==='sticky'||c.position==='absolute'))cover.push((e.tagName+'.'+String(e.className).slice(0,20)))}}
   return {ovf:document.documentElement.scrollWidth-innerWidth,footGap:Math.round(innerHeight-fb),docShort:document.documentElement.scrollHeight<=innerHeight+2,
    vid:pr?{w:Math.round(pr.width),h:Math.round(pr.height),ratio:+(pr.width/pr.height).toFixed(2),top:Math.round(pr.top)}:null,cover:cover.slice(0,4),
    ms:document.getElementById('mediasec')?.open,multi:!!document.querySelector('#multi:not([hidden])'),recap:(()=>{const e=document.getElementById('recap');if(!e)return null;const q=e.getBoundingClientRect();return Math.round(q.top)})(),
    sesspos:document.querySelector('.sesspos')?.textContent,
    hrefs:[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')).filter(h=>h&&h.startsWith('/')&&!h.startsWith('//'))}});
  r.hrefs.forEach(x=>links.add(x.split('#')[0]));
  if(r.ovf>1)note(u,w,'sideways overflow '+r.ovf+'px');
  if(r.docShort&&r.footGap>6)note(u,w,'footer floating '+r.footGap+'px above the bottom');
    if(r.vid&&r.vid.h>40&&(r.vid.ratio<1.6||r.vid.ratio>1.95))note(u,w,`video not 16:9 (${r.vid.w}x${r.vid.h})`);
  if(r.cover.length)note(u,w,'something over the video: '+r.cover.join(', '));
  if(exp.vod&&!r.ms)note(u,w,'?vod link left Stream & clips collapsed');
  if(exp.vod&&r.vid&&(r.vid.top<0||r.vid.top>h))note(u,w,'?vod link: video not on screen (top '+r.vid.top+')');
  if(exp.watch&&!r.multi)note(u,w,'?watch link did not open Watch together');
  if(exp.recap&&(r.recap===null||r.recap<-50||r.recap>h))note(u,w,'#recap link not scrolled to the recap (top '+r.recap+')');
  if(exp.session&&r.sesspos&&/^1\//.test(r.sesspos))note(u,w,'?session link shows session 1 ('+r.sesspos+')');
  errs.forEach(e=>note(u,w,'page error: '+e));bad.forEach(x=>note(u,w,'request failed: '+x));
  await p.screenshot({path:S+(w+u.replace(/[^a-z0-9]+/gi,'_')).slice(0,120)+'.png'});
 }
 await ctx.close()}
// dead internal links (GET each once)
const ctx=await b.newContext();const dead=[];let n=0;
for(const l of [...links].filter(x=>!/^\/(admin|account|api|archive|static|og|report|sw\.js|twitch-links|join|privacy\/request)/.test(x)).slice(0,220)){n++;await new Promise(r=>setTimeout(r,300));try{const r=await ctx.request.get(B+l,{maxRedirects:3,timeout:30000});if(r.status()>=400)dead.push(r.status()+' '+l)}catch(e){dead.push('ERR '+l)}}
console.log('internal links checked',n,'dead',dead.length);dead.forEach(x=>console.log('  DEAD',x));
console.log('\nISSUES',issues.length);issues.forEach(x=>console.log(' -',x));await b.close();
