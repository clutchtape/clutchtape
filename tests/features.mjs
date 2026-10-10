import assert from 'node:assert/strict';
import fs from 'node:fs';
import {chromium} from 'playwright';
const BASE=process.argv[2]||'http://localhost:8140';
const OUT=process.env.AGENT_DECK_EVIDENCE_DIR||'/tmp/clutchtape-features-20261007';fs.mkdirSync(OUT,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const views=[[320,740],[390,844],[768,1024],[1024,768],[844,390],[1366,768],[1440,1000],[1920,1080],[2560,1440],[3440,1440],[3840,2160]];
async function makeContext(options){const context=await browser.newContext(options);if(process.env.CT_CSS_CANDIDATE)await context.route('**/static/style.css*',r=>r.fulfill({contentType:'text/css',body:fs.readFileSync(process.env.CT_CSS_CANDIDATE,'utf8')}));return context;}
const results=[];
function record(name,detail){results.push({name,...detail});console.log('PASS '+name+' '+JSON.stringify(detail));}
const sdk=`window.Twitch={Player:class {static READY='ready';constructor(id,o){this.paused=!o.autoplay;this.t=100;this.muted=true;const el=typeof id==='string'?document.getElementById(id):id;const f=document.createElement('iframe');f.style='width:100%;height:100%;border:0';el.appendChild(f);}addEventListener(e,f){if(e==='ready')setTimeout(f,100);}play(){this.paused=false;}pause(){this.paused=true;}isPaused(){return this.paused;}getCurrentTime(){return this.t;}seek(t){this.t=t;}setVideo(v,t){this.t=t||0;}getMuted(){return this.muted;}setMuted(v){this.muted=v;}setVolume(){}setQuality(){}getQualities(){return [];}}};`;
try{
 if(!process.env.CT_ONLY_FULLSCREEN){
 for(const [w,h] of views){
  const ctx=await makeContext({viewport:{width:w,height:h}});const page=await ctx.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(BASE+'/p/lethul');await page.locator('#recap-status').filter({hasText:/loaded|not available|no readable/}).waitFor();
  const layout=await page.evaluate(()=>{const main=document.querySelector('main').getBoundingClientRect(),cols=document.querySelector('.cols').getBoundingClientRect();return {overflow:document.documentElement.scrollWidth-innerWidth,mainWidth:main.width,colsWidth:cols.width,screen:innerWidth};});
  assert(layout.overflow<=0);assert(layout.mainWidth>=w-2,'outer layout should use screen width');assert(layout.colsWidth>=w-60,'content should use width inside normal gutters');
  assert.equal(await page.locator('#tplayer').count(),0);
  await page.screenshot({path:OUT+`/stats-${w}x${h}.png`,fullPage:true});
  await page.locator('#compare-mode').selectOption('recent');await page.locator('.compare-form button').click();await page.waitForLoadState('load');await page.locator('[data-save-profile][aria-pressed]').waitFor();
  assert(page.url().includes('compare=recent'));assert(await page.locator('.compare-metric').count()===5);
  await page.locator('[data-save-profile]').click();assert.equal(await page.locator('[data-save-profile]').getAttribute('aria-pressed'),'true');
  await page.goto(BASE+'/');assert(await page.locator('#saved-profiles').isVisible());assert.equal(await page.locator('#saved-list a').count(),1);
  await page.locator('#saved-list a').click();assert(page.url().endsWith('/p/lethul'));
  await page.goto(BASE+'/');await page.locator('#saved-list button').click();assert(!await page.locator('#saved-profiles').isVisible());
  await page.screenshot({path:OUT+`/home-${w}x${h}.png`,fullPage:true});
  assert.deepEqual(errors,[]);
  record(`stats, comparison, save/reopen/remove ${w}x${h}`,layout);
  await ctx.close();
 }
 // Recap success, filters, empty/404, transient error, and retry against real page markup.
 const ctx=await makeContext({viewport:{width:1440,height:1000}});const page=await ctx.newPage();
 await page.goto(BASE+'/p/lethul');await page.locator('#recap-status').filter({hasText:/loaded|not available|no readable/}).waitFor();
 const actual=await page.locator('#recap-status').innerText();record('real recap response',{actual});
 await page.route('**/api/match/*/events',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({e:[['k',10000,'LethuL','Opponent'],['m',11000,'LethuL','Double Kill'],['k',70000,'Opponent','LethuL'],['o',90000,'LethuL','Flag'] ]})}));
 await page.reload();await page.locator('#recap-content').waitFor();assert.equal(await page.locator('.recap-event').count(),4);
 await page.locator('#recap-kind').selectOption('d');assert.equal(await page.locator('.recap-event').count(),1);
 await page.locator('#recap-time').fill('30');assert((await page.locator('#recap-events').innerText()).includes('No events'));
 await page.locator('#recap-all').click();assert.equal(await page.locator('.recap-event').count(),1);
 await page.unroute('**/api/match/*/events');await page.route('**/api/match/*/events',r=>r.fulfill({status:404,body:'{}'}));await page.reload();await page.locator('#recap-retry').waitFor();assert((await page.locator('#recap-status').innerText()).includes('not available'));
 await page.unroute('**/api/match/*/events');await page.route('**/api/match/*/events',r=>r.fulfill({status:503,body:'{}'}));await page.locator('#recap-retry').click();await page.locator('#recap-status').filter({hasText:'Could not load'}).waitFor();
 await page.unroute('**/api/match/*/events');await page.locator('#recap-retry').click();await page.locator('#recap-status').filter({hasText:/loaded|not available|no readable/}).waitFor();record('recap filters, time window, empty/error/retry',{recovered:await page.locator('#recap-status').innerText()});await ctx.close();
 }
 // Full-screen and overlay geometry at every resolution; SDK double removes third-party playback timing from geometry checks.
 for(const [w,h] of views){
  const ctx=await makeContext({viewport:{width:w,height:h}});await ctx.route('**/static/twitch-embed-v1.js*',r=>r.fulfill({contentType:'application/javascript',body:sdk}));const page=await ctx.newPage();
  await page.goto(BASE+'/squad/cykul,lethul,falcated');await page.locator('button.watch').first().click();await page.waitForTimeout(400);
  await page.locator('#multi [data-fullscreen]').click();await page.waitForFunction(()=>document.fullscreenElement?.id==='multi');await page.waitForTimeout(150);
  const fit=await page.evaluate(()=>{const m=document.getElementById('multi').getBoundingClientRect();const controls=[...document.querySelectorAll('#multi .mctl button')].filter(e=>e.getBoundingClientRect().width);const vids=[...document.querySelectorAll('#multi .mcell:not(.thumb) .mvid')];return {width:m.width,height:m.height,screen:[innerWidth,innerHeight],controls:controls.every(e=>{const b=e.getBoundingClientRect();return b.right<=innerWidth+1&&b.bottom<=innerHeight+1;}),videos:vids.every(e=>{const b=e.getBoundingClientRect();return b.width>0&&b.height>0&&b.right<=innerWidth+1&&b.bottom<=innerHeight+1;}),overflow:document.documentElement.scrollWidth-innerWidth};});
  assert(fit.controls,'controls fit');assert(fit.videos,'visible videos fit');assert(fit.overflow<=0);assert(Math.abs(fit.width-fit.screen[0])<2&&Math.abs(fit.height-fit.screen[1])<2);
  await page.screenshot({path:OUT+`/fullscreen-${w}x${h}.png`});
  await page.locator('#multi [data-fullscreen]').click();await page.waitForFunction(()=>!document.fullscreenElement);await page.locator('#mclose').click();assert(!await page.locator('#multi').isVisible());
  record(`full-screen geometry ${w}x${h}`,fit);
  await page.locator('#player [data-fullscreen]').click();await page.waitForFunction(()=>document.fullscreenElement?.id==='player');await page.waitForTimeout(150);
  const solo=await page.evaluate(()=>{const p=document.querySelector('#player').getBoundingClientRect(),v=document.querySelector('#player .embed').getBoundingClientRect(),log=document.querySelector('#elog').getBoundingClientRect();return {width:p.width,height:p.height,videoWidth:v.width,videoHeight:v.height,logBottom:log.bottom,screen:[innerWidth,innerHeight]};});
  assert(solo.videoWidth>=solo.screen[0]-30,'solo video should use full width');assert(solo.videoHeight>0);assert(solo.logBottom<=solo.screen[1]+1);assert(solo.logBottom>=solo.screen[1]-30,'solo layout should use full available height');
  await page.screenshot({path:OUT+`/solo-fullscreen-${w}x${h}.png`});
  await page.locator('#player [data-fullscreen]').click();await page.waitForFunction(()=>!document.fullscreenElement);
  record(`solo full-screen geometry ${w}x${h}`,solo);await ctx.close();
 }
}finally{fs.writeFileSync(OUT+'/features-results.json',JSON.stringify(results,null,2));await browser.close();}
