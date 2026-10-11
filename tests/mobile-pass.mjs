import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
const base=process.argv[2]||'http://localhost:8140',dir='/tmp/clutchtape-mobile-pass-20261009';
await mkdir(dir,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const context=await browser.newContext({viewport:{width:390,height:844}}),page=await context.newPage(),errors=[],thirdPartyErrors=[],failures=[],results=[];
await context.addInitScript(()=>{window.__appErrors=[];if(window===window.top)window.addEventListener('error',e=>{if(e.error)window.__appErrors.push(e.message)});});
page.on('pageerror',e=>thirdPartyErrors.push(e.message));page.on('response',r=>{if(r.status()>=400&&r.url().startsWith(base)&&!r.url().includes('/api/live'))failures.push([r.status(),r.url()])});
try{
 const routes=[['squad','/sq/a0b1c2?session=a1b2c3d4'],['sessions','/sq/a0b1c2?session=a1b2c3d4&tab=sessions'],['records','/sq/a0b1c2?session=a1b2c3d4&tab=records'],['analysis','/sq/a0b1c2?session=a1b2c3d4&tab=analysis'],['clips','/sq/a0b1c2?session=a1b2c3d4&tab=clips'],['profile','/p/x-ghost-x'],['profile-sessions','/p/x-ghost-x?tab=sessions'],['profile-records','/p/x-ghost-x?tab=records'],['stats-only','/p/lethul'],['match','/match/a1b2c3d4-60d1-462d-8085-620db7355880?player=x-ghost-x'],['home','/'],['color','/p/x-ghost-x/color'],['close','/close'],['history','/history/x-ghost-x,x-echo-x,x-nova-x,x-rook-x'],['practice','/practice/x-ghost-x,x-echo-x,x-nova-x,x-rook-x'],['weekly','/weekly/x-ghost-x,x-echo-x,x-nova-x,x-rook-x'],['scrims','/scrims/x-ghost-x,x-echo-x,x-nova-x,x-rook-x']];
 for(const [name,path] of routes){const response=await page.goto(base+path);assert.equal(response.status(),200,name);await page.waitForTimeout(350);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),name+' no document overflow');
  if(name==='squad'){
   /* 2026-10-10: session totals are an always-visible swipeable table with a pinned player column  */const liveNow=await page.locator('#playnow,#onair').count();   /* while the squad is playing, the session table sits in the live panel instead of the game log */
   assert(await page.locator('#sqtable table.nightper,#playnow table.nightper,#livevs table.nightper,.gamelog table.nightper').first().isVisible());   /* 2026-10-10: the squad table leads the page (#sqtable) */assert.equal(await page.locator('table.nightper.mobile-cards').count(),0);
   const url=page.url();await page.locator('table.night .mobile-expand').first().click();assert.equal(page.url(),url,'expansion does not navigate');assert(await page.locator('table.night .mobile-card').first().locator('.kdacell').first().isVisible());await page.locator('table.night .mobile-expand').first().click();
   await page.getByLabel('Sort games',{exact:true}).selectOption('3');assert.equal(await page.locator('table.night th').nth(3).getAttribute('aria-sort'),'ascending');
   await page.setViewportSize({width:1440,height:1000});await page.waitForTimeout(300);assert(await page.locator('.nightper').isVisible(),'desktop totals visible after resize');assert.equal(await page.locator('table.night').evaluate(t=>getComputedStyle(t).display),'table');await page.screenshot({path:dir+'/desktop-final.png'});await page.setViewportSize({width:390,height:844});
  }
  if(name==='analysis'){   // 2026-10-10: one scrolling page (no sub-tabs); stat-group buttons still filter the grid
   await page.locator('[data-stat-filter="damage"]').click();assert(await page.locator('.stat-grid tbody td[data-stat-group="damage"]').first().isVisible());
   assert(await page.locator('#trends .tr-line').count()>0,'trend charts render');
  }
  errors.push(...await page.evaluate(()=>window.__appErrors||[]));await page.screenshot({path:dir+'/'+name+'-final.png'});results.push({name,status:response.status(),cards:await page.locator('.mobile-card').count()});
 }
 assert.deepEqual(errors,[],'no uncaught app errors');assert.deepEqual(failures,[],'no failed app requests');
 await writeFile(dir+'/verification.json',JSON.stringify({results,errors,thirdPartyErrors,failures},null,2));console.log('PASS mobile: '+results.map(r=>r.name).join(', ')+'; expand, sort, analysis filters/counts, desktop resize');
}finally{await browser.close()}
