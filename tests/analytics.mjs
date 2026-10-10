import { chromium } from 'playwright';
import fs from 'node:fs/promises';
const out=process.env.CT_EVIDENCE_DIR||'./test-results/analytics';await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,headless:true});
const page=await browser.newPage();const errors=[],failed=[],checks=[];
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});page.on('response',r=>{if(r.status()>=400&&!r.url().includes('twitch'))failed.push({status:r.status(),url:new URL(r.url()).pathname});});
const origin=process.env.CT_BASE_URL||'http://localhost:8140';
const base=origin+'/live/cykul?scope=30&compare=month';
await page.goto(base,{waitUntil:'networkidle'});await page.waitForSelector('.filter-panel');
for(const [w,h] of [[390,844],[768,1024],[1024,768],[1440,1000],[1920,1080],[2560,1440],[3440,1440],[3840,2160]]){
 await page.setViewportSize({width:w,height:h});await page.goto(base,{waitUntil:'networkidle'});await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(200);
 for(const tab of ['overview','analysis','games','replay']){
  await page.locator(`[data-tab=${tab}]`).click();await page.waitForTimeout(150);
  const state=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth-innerWidth,visible:[...document.querySelectorAll('[data-view]')].filter(e=>!e.hidden).map(e=>e.dataset.view),nestedTimeline:[...document.querySelectorAll('.recap-events')].some(e=>e.clientHeight&&e.scrollHeight>e.clientHeight+2&&['auto','scroll'].includes(getComputedStyle(e).overflowY))}));
  if(state.overflow>1)throw Error(`Overflow ${w} ${tab}: ${state.overflow}`);
  if(state.visible.some(v=>v!==tab))throw Error('Mixed tabs');
  if(w===390&&state.nestedTimeline)throw Error('Nested mobile timeline');
  checks.push({w,h,tab,...state});
  if((w===390||w===1440)&&['overview','analysis'].includes(tab))await page.screenshot({path:`${out}/${tab}-${w}.png`,fullPage:true});
 }
}
await page.setViewportSize({width:390,height:844});await page.goto(base,{waitUntil:'networkidle'});
await page.locator('.filter-panel summary').click();await page.locator('select[name=kind]').selectOption('ranked');await page.locator('select[name=playlist]').selectOption('Ranked Arena');await page.locator('select[name=scope]').selectOption('90');await page.getByRole('button',{name:'Apply filters'}).click();await page.waitForLoadState('networkidle');
const filter=await page.locator('.selection-caption').innerText();if(!filter.includes('Last 90 days · Ranked Arena'))throw Error('Filters not preserved');checks.push({interaction:'global filters',text:filter});
await page.getByLabel('Performance metric',{exact:true}).selectOption('acc');await page.getByLabel('Inspect performance game',{exact:true}).fill('0');await page.getByLabel('Inspect performance game',{exact:true}).dispatchEvent('input');const readout=await page.locator('[data-chart=performance] .chart-readout').innerText();if(!readout.includes('%'))throw Error('Metric switch');
await page.locator('[data-chart=performance] .chart-canvas svg').click({position:{x:140,y:100}});const gameUrl=await page.locator('[data-chart=performance] .chart-link').getAttribute('href');await page.locator('[data-chart=performance] .chart-link').click();await page.waitForLoadState('networkidle');if(!page.url().includes('/match/'))throw Error('Game drilldown');checks.push({interaction:'metric, slider, chart tap, match drilldown',url:gameUrl});
await page.goto(base+'#analysis',{waitUntil:'networkidle'});await page.locator('.heat-cell').first().click();await page.waitForLoadState('networkidle');if(!await page.locator('.map-detail .filtered-game').count())throw Error('Map drilldown');checks.push({interaction:'map/mode drilldown',games:await page.locator('.map-detail .filtered-game').count()});
const options=await page.locator('#objective-metric option').count();if(options){await page.locator('#objective-metric').selectOption({index:options-1});if(!await page.locator('[data-bars=objectives] .bar-row').count())throw Error('Objective bars');checks.push({interaction:'objective chart'});}
await page.getByLabel('Expected performance metric',{exact:true}).selectOption('deaths');checks.push({interaction:'expected deaths selector',rows:await page.locator('[data-bars=expectation] .bar-row').count()});
await page.goto(origin+'/live/cykul',{waitUntil:'networkidle'});const latest=await page.locator('#analysis-data').evaluate(e=>JSON.parse(e.textContent).series[0]?.points.at(-1)?.outcome);if(latest==='Dnf'&&!(await page.locator('.compact-summary').innerText()).includes('Did not finish'))throw Error('DNF label');if(await page.getByText('LAST COMPLETED GAME',{exact:true}).count())throw Error('Old label');checks.push({interaction:'DNF label'});
await page.goto(origin+'/live/cykul?kind=custom&playlist=NoSuchPlaylist',{waitUntil:'networkidle'});if(!await page.getByText('Ready when you are.',{exact:true}).count())throw Error('Empty view');checks.push({interaction:'empty selection'});
await page.goto(origin+'/live/cykul,lethul,falcated?scope=all#analysis',{waitUntil:'networkidle'});await page.getByLabel('Squad contribution metric',{exact:true}).selectOption('damage_share');checks.push({interaction:'squad contribution empty state'});
await page.goto(base,{waitUntil:'networkidle'});await page.getByRole('button',{name:'Full screen',exact:true}).click();await page.waitForFunction(()=>!!document.fullscreenElement);await page.evaluate(()=>document.exitFullscreen());checks.push({interaction:'fullscreen'});
await fs.writeFile(out+'/checks.json',JSON.stringify({checks,errors,failed},null,2));await browser.close();console.log(JSON.stringify({checks:checks.length,errors,failed,out}));if(errors.length||failed.length)process.exitCode=1;
