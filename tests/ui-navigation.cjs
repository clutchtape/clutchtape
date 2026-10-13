// Live UI regressions: view switches preserve scroll, raw errors recover,
// timeline clicks reveal events, and Back clears the selected highlight.
// CT_BASE_URL, CT_PLAYWRIGHT_MODULE and PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
// can override the production URL, Playwright module and browser executable.
const { chromium } = require(process.env.CT_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    args: ['--no-sandbox']});
  const base = process.env.CT_BASE_URL || 'https://clutchtape.com';
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({viewport: {width, height: width === 390 ? 844 : 1000}, serviceWorkers: 'block'});
      const page = await context.newPage();
      await page.goto(base + '/p/royai-2');
      if (await page.locator('[data-tipclose]').isVisible()) await page.locator('[data-tipclose]').click();
      await page.locator('.viewsw').scrollIntoViewIfNeeded();
      const y = await page.evaluate(() => scrollY);
      for (const view of ['raw', 'summary', 'summary']) {
        await page.locator(`.viewsw [data-view=${view}]`).click();
        await page.waitForFunction(() => !document.documentElement.classList.contains('vt-view'));
        if (view === 'raw') await page.locator('#raw table').waitFor();
        assert.ok(Math.abs(await page.evaluate(() => scrollY) - y) < 3, `${width}: ${view} scrolled`);
      }
      await page.reload();
      await page.route('**/p/royai-2?*raw=1*', route => route.fulfill({status: 200, contentType: 'text/html', body: '<p>Missing raw data</p>'}));
      await page.locator('.viewsw [data-view=raw]').click();
      await page.locator('[data-raw-retry]').waitFor();
      await page.unroute('**/p/royai-2?*raw=1*');
      await page.locator('[data-raw-retry]').click();
      await page.locator('#raw table').waitFor();
      await page.goto(base + '/p/cykul');
      const match = await page.locator('.gamelog a[href^="/match/"]').first().getAttribute('href');
      await page.goto(base + match);
      await page.locator('#mtl .hit').click();
      assert.ok(await page.locator('.recap-fold').evaluate(e => e.open), 'Timeline must open event list');
      await page.locator('.recap-highlight a').first().click();
      assert.ok(new URL(page.url()).searchParams.has('at'));
      await page.goBack();
      await page.waitForFunction(() => document.querySelector('#recap-clock')?.textContent === 'All events');
      assert.equal(new URL(page.url()).searchParams.has('at'), false);
      const removed = await page.goto(base + '/scrims/cykul');
      assert.equal(removed.status(), 404);
      await context.close();
      console.log(`${width}: navigation regressions passed`);
    }
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
