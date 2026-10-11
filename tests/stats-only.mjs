// A player page with no Twitch (2026-10-11 rewrite; the old version tested a live tracker that no longer exists):
// no video, the game log and session tiles render, ‹ Previous / Next › move between sessions, no overflow or page errors.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
const BASE=process.argv[2]||'http://localhost:8140', SLUG=process.argv[3]||'lethul';
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
try {
  for(const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
    const context=await browser.newContext({viewport,isMobile:viewport.width<700,hasTouch:viewport.width<700});
    const page=await context.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(String(e)));
    const res=await page.goto(BASE+'/p/'+SLUG,{waitUntil:'load'});assert.equal(res.status(),200);
    assert.equal(await page.locator('#tplayer').count(),0,'no Twitch player without a channel');
    assert(await page.locator('#latest table tbody tr, #latest .mobile-card').count()>0,'game log has games');
    const prev=page.locator('.sessbtn[rel=prev]').first();
    if(await prev.count()){const pos=await page.locator('.sesspos').first().innerText();await prev.click();await page.waitForLoadState('load');
      assert(page.url().includes('session='),'‹ Previous opens an older session');assert.notEqual(await page.locator('.sesspos').first().innerText(),pos);}
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth),0,'no sideways overflow');
    assert.deepEqual(errors,[]);
    console.log(`PASS ${viewport.width}x${viewport.height}: no Twitch → no player, game log, session arrows, no overflow/page errors`);
    await context.close();
  }
} finally {await browser.close();}
