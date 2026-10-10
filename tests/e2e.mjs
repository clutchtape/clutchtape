// Clutchtape end-to-end test: every page, every interaction, desktop + phone, fresh browser contexts.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
// Refresh trigger: re-run after ANY template/JS change; add a case when a new page or control ships.
import { chromium } from 'playwright';

const BASE = process.argv[2] || 'http://localhost:8140';
const SQUAD = '/squad/cykul,lethul,falcated';
const EXE = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
const DESK = { viewport: { width: 1440, height: 900 } };
const PHONE = { viewport: { width: 412, height: 915 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2.6,
  userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36' };
const IGNORE = /getLayoutMap|scorecardresearch|amazon-adsystem|Permissions-Policy|live-video\.net|twitchcdn|MaxListeners|ttvnw/;

const results = [];
function rec(name, ok, detail = '') { results.push({ name, ok, detail }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`); }

async function withPage(browser, opts, fn, { blockTwitchLib = false } = {}) {
  const ctx = await browser.newContext(opts); const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => { const s = String(e); if (!IGNORE.test(s)) errs.push(s.slice(0, 160)); });
  if (blockTwitchLib) await ctx.route('**/js/embed/v1.js', r => r.abort('failed'));
  try { await fn(p, errs); } finally { await ctx.close(); }
}
const states = p => p.evaluate(() => (window.__mp || []).map(x => { try { return { paused: x.isPaused(), t: x.getCurrentTime() }; } catch (e) { return { err: 1 }; } }));
const overflow = p => p.evaluate(() => document.documentElement.scrollWidth - innerWidth);

const browser = await chromium.launch({ executablePath: EXE });
try {
  // ---------- static pages + HTTP ----------
  for (const [path, want] of [['/', 200], ['/about', 200], ['/p/cykul', 200], ['/p/cykul?kind=all', 200], [SQUAD, 200],
    ['/squad/cykul,lethul,falcated', 200], ['/p/does-not-exist', 404], ['/robots.txt', 200], ['/static/twitch-embed-v1.js', 200],
    ['/api/p/cykul/status', 200], ['/api/live/cykul,lethul', 200]]) {
    const r = await fetch(BASE + path); rec(`HTTP ${path}`, r.status === want, `got ${r.status}`);
  }

  // wide screens: clip rows must stay readable (title not one-word-per-line) and nothing may overflow
  for (const w of [1920, 2200, 2560, 3440]) {
    await withPage(browser, { viewport: { width: w, height: 1100 } }, async (p) => {
      await p.goto(BASE + '/p/cykul', { waitUntil: 'load' });
      const r = await p.evaluate(() => { const c = document.querySelector('.clipsec'); const b = c.querySelector('.mo .mtxt b').getBoundingClientRect();
        const s = c.querySelector('.mo .acts').getBoundingClientRect(); const cb = c.getBoundingClientRect();
        return { lines: Math.round(b.height / 18), inside: s.right <= cb.right + 1, over: document.documentElement.scrollWidth - innerWidth }; });
      rec(`ultrawide ${w}px: clip rows readable, nothing off-screen`, r.lines <= 3 && r.inside && r.over <= 0, JSON.stringify(r));
    });
  }
  // Keep a usable video and its timeline together inside the initial desktop viewport.
  for (const [w, h] of [[1366, 768], [1920, 1080], [2560, 1440]]) {
    await withPage(browser, { viewport: { width: w, height: h } }, async (p) => {
      await p.goto(BASE + '/p/cykul', { waitUntil: 'load' }); await p.waitForTimeout(2500);
      const r = await p.evaluate(() => { const e = document.querySelector('#player .embed').getBoundingClientRect(), p = document.getElementById('player').getBoundingClientRect(); return {width:e.width,height:e.height,column:p.width,bottom:document.getElementById("elog").getBoundingClientRect().bottom,viewport:innerHeight}; });
      rec(`usable full-width video ${w}x${h}`, r.width >= r.column-55 && r.width >= 700 && r.height >= 280 && r.bottom <= r.viewport, JSON.stringify(r));
    });
  }
  for (const [label, opts] of [['desktop', DESK], ['phone', PHONE]]) {
    // ---------- home ----------
    await withPage(browser, opts, async (p, errs) => {
      await p.goto(BASE + '/', { waitUntil: 'load' });
      rec(`${label} home: form + demo links`, await p.locator('#lookup').count() === 1 && await p.locator('.try .pill').count() >= 3);
      for (let i = 0; i < 4; i++) { const b = p.locator('#addmate'); if (await b.isVisible()) await b.click(); }
      rec(`${label} home: squad rows expand to 4`, await p.$$eval('#lookup .prow', r => r.filter(x => !x.hidden).length) === 4);
      await p.locator('#lookup input[name=gamertag]').first().fill('bad<tag>');
      await Promise.all([p.waitForNavigation(), p.locator('#lookup .go').click()]);
      rec(`${label} home: validation error shown`, /valid gamertag/.test(await p.locator('.alert').first().textContent()));
      rec(`${label} home: invalid input retained`, await p.locator('#lookup input[name=gamertag]').first().inputValue() === 'bad<tag>');
      await p.locator('#addmate').click();
      await p.locator('#lookup input[name=gamertag]').nth(1).fill('CyKul');
      await p.locator('#lookup .removemate').first().click();
      rec(`${label} home: remove restores solo form`, await p.locator('#lookup .prow:visible').count() === 1 && await p.locator('#lookup .go').textContent() === 'Show my stats');
      await p.locator('#addmate').click();
      rec(`${label} home: re-added row is empty`, await p.locator('#lookup .prow:visible input[name=gamertag]').nth(1).inputValue() === '');
      rec(`${label} home: no overflow / errors`, await overflow(p) <= 0 && !errs.length, errs.join(' | '));
    });

    // ---------- solo profile ----------
    await withPage(browser, opts, async (p, errs) => {
      await p.goto(BASE + '/p/cykul', { waitUntil: 'load' });
      await p.waitForTimeout(3000);
      rec(`${label} solo: player iframe loaded`, await p.locator('#tplayer iframe').count() === 1);
      const vb = await p.locator('#player .embed').boundingBox();
      rec(`${label} solo: video box has a real 16:9 size`, vb && vb.height > 150 && Math.abs(vb.width / vb.height - 16 / 9) < 0.1, vb ? `${Math.round(vb.width)}x${Math.round(vb.height)}` : 'none');
      await p.locator('.kinds a', { hasText: 'All' }).click(); await p.waitForLoadState('load');
      rec(`${label} solo: filter in URL`, /kind=all/.test(p.url()));
      const vod = p.locator('#latest a.vod, .clipsec a.vod').first();
      if (await vod.count()) {
        await vod.click(); await p.waitForTimeout(9000);
        rec(`${label} solo: VOD jump updates URL`, /vod=\d+/.test(p.url()));
        rec(`${label} solo: event timeline drawn`, await p.locator('#elog .etk').count() > 0, `${await p.locator('#elog .etk').count()} markers`);
      }
      // auto clips: every clip must have a VOD, and ▶ must land at the clip's film time (Twitch ignores setVideo's start time)
      const crow = p.locator('#latest tr.clickrow').first();
      if (await crow.count()) {
        const want = (await crow.getAttribute('data-vod')).match(/t=(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?/);
        const ws = (+want[1] || 0) * 3600 + (+want[2] || 0) * 60 + (+want[3] || 0);
        await crow.locator('td').nth(1).click(); await p.waitForTimeout(9000);
        const at = await p.evaluate(() => window.__sp.getCurrentTime());
        rec(`${label} solo: game row click plays that game`, at >= ws - 3 && at <= ws + 20, `row at ${ws}s → player ${Math.round(at)}s`);
      }
      rec(`${label} solo: no clips without a VOD`, await p.locator('.clipsec .nov').count() === 0);
      const clip = p.locator('.clipsec .mo').first();
      if (await clip.count()) {
        const film = (await clip.locator('.mtxt small').innerText()).match(/film (\d+):(\d+)/);
        await clip.locator('a.vod').click();
        // poll up to 45s: a Twitch pre-roll ad holds the stream at 0:00 for 15-30s before the seek can land
        const want = +film[1] * 60 + +film[2]; let sub = null, got = -999;
        for (let i = 0; i < 15; i++) {
          await p.waitForTimeout(3000);
          sub = ((await p.locator('#elog .elsub').textContent()) || '').match(/(\d+):(\d+)$/);
          got = sub ? +sub[1] * 60 + +sub[2] : -999;
          if (got >= want - 2 && got <= want + 20) break;
        }
        rec(`${label} solo: clip ▶ lands on its moment`, got >= want - 2 && got <= want + 20, `clip ${film[0]} → log at ${sub ? sub[0] : 'nothing'}`);
      }
      rec(`${label} solo: no overflow / errors`, await overflow(p) <= 0 && !errs.length, errs.join(' | '));
    });

    // ---------- squad + watch together (the risky part) ----------
    for (const block of [false, true]) {
      await withPage(browser, opts, async (p, errs) => {
        const tag = `${label} squad${block ? ' [Twitch lib blocked]' : ''}`;
        await p.goto(BASE + SQUAD, { waitUntil: 'load' });
        if (!block) {
          await p.locator('.sesspick a').nth(1).click(); await p.waitForLoadState('load');
          rec(`${tag}: session picker switches night`, /[?&]session=[0-9a-f-]{36}/.test(p.url()) && /Night together/.test(await p.locator('#latest .eyebrow').textContent()));
          await p.goto(BASE + SQUAD, { waitUntil: 'load' });
        }
        rec(`${tag}: teamwork panel`, await p.locator('#teamwork .mo').count() > 0);
        await p.locator('#teamwork .tab[data-tab="bad"]').click();
        rec(`${tag}: tab in URL`, /tab=bad/.test(p.url()));
        await p.locator('#teamwork .tab[data-tab="good"]').click();
        // Twitch keeps VODs ~7 days on small channels, so a moment may have fewer than 4 angles: expect what it lists
        const angles = JSON.parse(await p.locator('button.watch').first().getAttribute('data-watch')).length;
        await p.locator('button.watch').first().click();
        await p.waitForTimeout(16000);
        let st = await states(p);
        if (st.some(s => s.paused) && await p.locator('#mstart').isVisible()) {   // designed fallback: one tap starts every stream
          await p.locator('#mstart').click(); await p.waitForTimeout(5000); st = await states(p);
        }
        const playing = st.filter(s => !s.paused && !s.err).length;
        const want = label === 'phone' ? 1 : angles;
        rec(`${tag}: ${want} stream(s) playing`, playing >= want, JSON.stringify(st.map(s => s.paused ? 'paused' : Math.round(s.t))));
        rec(`${tag}: watch key in URL`, /watch=/.test(p.url()));
        if (label === 'desktop') {                      // every angle at the same in-game moment (drift <= 1.5s)
          // steady state: best of 3 samples 1.5s apart (a single instant can catch one stream mid-buffer)
          let d = [], ok = false;
          for (let k = 0; k < 3 && !ok; k++) {
            d = await p.evaluate(() => { const b = document.querySelector('button.watch'); const tg = JSON.parse(b.dataset.watch).map(w => w.sec);
              return window.__mp.map((x, i) => { try { return x.getCurrentTime() - tg[i]; } catch (e) { return null; } }); });
            const live = d.filter(v => v !== null && v > -60);           // streams sitting at ~0:00 are in a Twitch pre-roll ad / loading
            ok = live.length >= 2 && Math.max(...live) - Math.min(...live) <= 1.5;
            if (!ok) await p.waitForTimeout(2500);
          }
          rec(`${tag}: streams in sync`, ok, JSON.stringify(d.map(v => v === null ? null : +v.toFixed(1))));
        }
        rec(`${tag}: iframes present`, await p.locator('#multi iframe').count() === angles, `${await p.locator('#multi iframe').count()} of ${angles}`);   // phones keep every angle loaded (1 big + strip)
        if (!block) rec(`${tag}: top timeline`, label === 'phone' ? await p.locator('#mtl .etg .ln').count() === 1 : await p.locator('#mtl .etk').count() > 0,
          label === 'phone' ? 'momentum graph' : `${await p.locator('#mtl .etk').count()} markers`);
        if (label === 'phone') {                    // instant angle switch: a loaded player should be playing within ~1.5s
          await p.locator('.angles button').nth(2).tap(); await p.waitForTimeout(1500);
          const s2 = await states(p);
          rec(`${tag}: angle switch plays quickly`, s2[2] && !s2[2].paused, JSON.stringify(s2.map(s => s.paused ? 'paused' : Math.round(s.t))));
        }
        const fits = await p.evaluate(() => [...document.querySelectorAll('#multi .mvid')].every(v => { const b = v.getBoundingClientRect(); return b.bottom <= innerHeight + 1 && b.right <= innerWidth + 1; }));
        rec(`${tag}: videos fit the screen`, label === 'phone' || fits);
        await p.keyboard.press('Escape');
        rec(`${tag}: Esc closes + clears URL`, !(await p.locator('#multi').isVisible()) && !/watch=/.test(p.url()));
        rec(`${tag}: no page errors`, !errs.length, errs.join(' | '));
      }, { blockTwitchLib: block });
    }
  }
} finally { await browser.close(); }
const bad = results.filter(r => !r.ok);
console.log(`\n${results.length - bad.length}/${results.length} passed`);
process.exit(bad.length ? 1 : 0);
