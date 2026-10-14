// Regression: an inactive page, first-poll race, transient render failure and tab return.
const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try { ({ chromium } = require('playwright')); }
catch (_) { ({ chromium } = require('/tmp/node_modules/playwright')); }
(async () => {
  const browser = await chromium.launch({ ...(process.env.CHROMIUM_PATH ? {executablePath: process.env.CHROMIUM_PATH} : {}), args: ['--no-sandbox'] });
  try {
    for (const withPanel of [false, true]) {
      const page = await browser.newPage();
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      await page.route('https://fixture.test/**', route => route.fulfill({contentType:'text/html',body:'<html><body></body></html>'}));
      await page.goto('https://fixture.test/p/test');
      await page.setContent(`<div id="live-source" hidden data-slugs="test" data-seen='{"test":"old"}'></div>
        ${withPanel ? '<section id="live"><div class="lvcard" data-slug="test"></div><button id="lvreload" hidden>Retry</button><p id="lvstatus"></p></section>' : ''}
        <div class="gamelog"><table><tbody><tr data-match="old"><td>Old game</td></tr></tbody></table></div>
        <iframe id="video" src="about:blank"></iframe>`);
      await page.evaluate(() => {
        window.videoBefore = document.querySelector('#video'); window.polls = 0; window.renders = 0;
        window.timers = []; window.setInterval = fn => { timers.push(fn); return timers.length; };
        window.fetch = async url => {
          if (String(url).startsWith('/api/live/')) {
            polls++;
            return {ok:true,json:async()=>({players:[{slug:'test',gamertag:'Test',live:{active:true,record:'1–0',games:1,kda:5,kd:2,pips:['win'],last:{match_id:'new',map:'Test map',mode:'Slayer',outcome:'Win',k:10,d:5,a:0},ended_ago:5}}]})};
          }
          renders++;
          if (renders === 1) throw new Error('Temporary page fetch failure');
          return {ok:true,text:async()=>'<div class="gamelog"><table><tbody><tr data-match="new"><td>New game</td></tr><tr data-match="old"><td>Old game</td></tr></tbody></table></div>'};
        };
      });
      await page.addScriptTag({content:fs.readFileSync('app/static/live.js','utf8')});
      await page.waitForFunction(() => window.renders === 1);
      // Same match on the next poll must retry a failed render without a new match ID.
      await page.evaluate(() => timers[timers.length - 1]());
      await page.waitForSelector('[data-match="new"]');
      assert.equal(await page.evaluate(() => window.renders), 2);
      assert.equal(await page.evaluate(() => document.querySelector('#video') === videoBefore), true);
      const before = await page.evaluate(() => polls);
      await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
      await page.waitForFunction(n => polls > n, before);
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('PASS: polling without a live panel, first-poll new game, render retry, visibility return, video preserved');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
