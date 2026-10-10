import {chromium} from 'playwright';
import fs from 'node:fs/promises';
const dir='/tmp/clutchtape-match-20261007';
const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,args:['--no-sandbox']});
const ctx=await browser.newContext();const page=await ctx.newPage();const results=[];const base='https://test.clutchtape.example',match='/match/0ffcad10-a648-46b1-9150-a1d56f418433?player=cykul';
function check(name,ok,extra={}){results.push({name,ok,...extra});if(!ok)console.error('FAIL',name,extra)}
try{
 for(const [w,h] of [[320,740],[390,844],[768,1024],[844,390],[1024,768],[1366,768],[1440,1000],[1920,1080],[2560,1440],[3440,1440],[3840,2160]]){
  await page.setViewportSize({width:w,height:h});await page.goto(base+match,{waitUntil:'domcontentloaded'});await page.waitForSelector('.roster-player');
  const geometry=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth-innerWidth,width:document.querySelector('.match-page').getBoundingClientRect().width,columns:document.querySelectorAll('.roster-player').length}));
  check('match '+w+'×'+h,geometry.overflow<=1&&geometry.columns===8&&geometry.width>w*.88,geometry);
 }
 await page.setViewportSize({width:390,height:844});await page.goto(base+match);await page.locator('#recap-content').waitFor({state:'visible'});
 check('mobile event batch',await page.locator('.recap-event').count()===20);
 await page.locator('.roster-player').last().locator('summary').click();await page.locator('.roster-player').last().locator('[data-recap-player]').click();
 check('opponent event filter',await page.locator('#recap-player').inputValue()==='Suppressecl'&&await page.locator('#recap-summary').textContent().then(t=>t.includes('15 kills')));
 await page.locator('#recap-kind').selectOption('m');check('medal filter',await page.locator('.recap-event').count()>0);
 await page.locator('#recap-mine').uncheck();await page.locator('#recap-kind').selectOption('all');await page.locator('#recap-more').click();check('show more',await page.locator('.recap-event').count()===40);
 const scroll=await page.locator('#recap-events').evaluate(e=>{e.scrollIntoView();return {y:scrollY,overflow:getComputedStyle(e).overflowY,height:e.clientHeight,scrollHeight:e.scrollHeight}});await page.mouse.wheel(0,450);await page.waitForTimeout(300);
 check('page scroll over events',await page.evaluate(()=>scrollY)>scroll.y&&scroll.height===scroll.scrollHeight,scroll);
 for(const path of ['/p/cykul','/squad/cykul,lethul,falcated','/live/cykul,lethul,falcated']){
  await page.goto(base+path);await page.locator('#recap').waitFor();const g=await page.evaluate(()=>{let r=document.querySelector('#recap'),e=document.querySelector('#recap-events'),host=r.closest('.timeline-panel')||r;return{overflow:document.documentElement.scrollWidth-innerWidth,listOverflow:e?getComputedStyle(e).overflowY:'empty',below:!host.nextElementSibling,insideSidebar:!!r.closest('.colside')}});
  check('mobile lower timeline '+path,g.overflow<=1&&['visible','empty'].includes(g.listOverflow)&&g.below&&!g.insideSidebar,g);
 }
 await page.route('**/api/match/*/events',route=>route.fulfill({status:503,contentType:'application/json',body:'{}'}));await page.goto(base+match);await page.locator('#recap-retry').waitFor({state:'visible'});check('event API error safe',await page.locator('#recap-status').textContent().then(t=>t.includes('Could not load'))&&await page.locator('.roster-player').count()===8);await page.unroute('**/api/match/*/events');await page.locator('#recap-retry').click();await page.locator('#recap-content').waitFor({state:'visible'});check('event retry recovers',await page.locator('.recap-event').count()>0);
 await page.route('**/api/match/*/events',route=>route.fulfill({status:200,contentType:'application/json',body:'{"e":[]}'}));await page.reload();await page.locator('#recap-retry').waitFor({state:'visible'});check('empty film message',await page.locator('#recap-status').textContent().then(t=>t.includes('no readable events')));
}finally{await fs.writeFile(dir+'/verification.json',JSON.stringify(results,null,2));await browser.close();}
console.log(`${results.filter(r=>r.ok).length}/${results.length} checks passed`);if(results.some(r=>!r.ok))process.exitCode=1;
