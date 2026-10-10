import { chromium } from 'playwright';
const b = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH });
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
await ctx.addInitScript(() => {   // stand-in for the visitor's tab capture: an animated canvas stream
  navigator.mediaDevices.getDisplayMedia = async () => { const c = document.createElement('canvas'); c.width = 640; c.height = 360; const g = c.getContext('2d');
    let i = 0; setInterval(() => { g.fillStyle = `hsl(${i++ % 360},70%,50%)`; g.fillRect(0, 0, 640, 360); }, 33); return c.captureStream(30); };
});
const p = await ctx.newPage();
await p.goto('https://test.clutchtape.example/p/cykul', { waitUntil: 'load' }); await p.waitForTimeout(3000);
const row = p.locator('.clipsec .mo').nth(1);
console.log('clip:', (await row.locator('.mtxt b').innerText()), 'dur', await row.locator('.savebtn').getAttribute('data-dur'));
const dl = p.waitForEvent('download', { timeout: 120000 }).catch(() => null);
await row.locator('.savebtn').click();
for (let i = 0; i < 4; i++) { await p.waitForTimeout(4000); console.log('bar:', (await p.locator('.recbar').textContent()).slice(0, 70), '| player at', await p.evaluate(() => Math.round(window.__sp.getCurrentTime()))); }
const d = await dl;
if (d) { const f = '/tmp/' + d.suggestedFilename(); await d.saveAs(f); console.log('DOWNLOADED', f); }
console.log('final bar:', await p.locator('.recbar').textContent());
await b.close();
