import assert from 'node:assert/strict';
import {chromium} from 'playwright';
const BASE=process.argv[2]||'http://localhost:8140';
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
try {
  for(const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
    const context=await browser.newContext({viewport});
    const page=await context.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(String(e)));
    // Capture the real polling callback, so retry coverage doesn't wait thirty seconds per assertion.
    await page.addInitScript(()=>{const native=window.setInterval;window.setInterval=(fn,ms,...args)=>{if(ms===30000){window.__statsPoll=fn;return 0;}return native(fn,ms,...args);};});
    await page.goto(BASE+'/p/lethul');
    await page.locator('#lvstatus').filter({hasText:/Checked|Updating/}).waitFor();
    assert.equal(await page.locator('#tplayer').count(),0);
    assert(await page.locator('#latest table tbody tr').count()>0);
    await page.locator('.sesspick a').nth(1).click();
    assert(page.url().includes('s=1'));
    await page.locator('#lvstatus').filter({hasText:/Checked|Updating/}).waitFor();
    const before=await page.locator('#latest').innerText();
    await page.route('**/api/live/*',r=>r.fulfill({status:503,contentType:'application/json',body:'{}'}));
    await page.evaluate(()=>window.__statsPoll());
    await page.locator('#lvstatus').filter({hasText:'Could not check'}).waitFor();
    assert.equal(await page.locator('#latest').innerText(),before);
    await page.unroute('**/api/live/*');
    await page.evaluate(()=>window.__statsPoll());
    await page.locator('#lvstatus').filter({hasText:/Checked|Updating/}).waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth),0);
    assert.deepEqual(errors,[]);
    console.log(`PASS ${viewport.width}x${viewport.height}: no Twitch, session switch, stats retained on 503, polling recovery, no overflow/page errors`);
    await context.close();
  }
} finally {await browser.close();}
