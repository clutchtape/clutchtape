// Exercise the deployed UI with a deterministic Twitch SDK double: ads/network must not mask intent regressions.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const BASE = process.argv[2] || 'http://localhost:8140';
const browser = await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const sdk = `window.Twitch={Player:class {
  static READY='ready';
  constructor(id,o){this.paused=!o.autoplay;this.t=100;this.muted=true;this.plays=0;this.handlers={};let el=typeof id==='string'?document.getElementById(id):id;el.appendChild(document.createElement('iframe'));}
  addEventListener(ev,fn){if(ev==='ready')setTimeout(fn,100);}
  play(){this.paused=false;this.plays++;} pause(){this.paused=true;}
  isPaused(){return this.paused;} getCurrentTime(){return this.t;} seek(t){this.t=t;}
  setVideo(v,t){this.t=t||0;} getMuted(){return this.muted;} setMuted(v){this.muted=v;}
  setVolume(){} setQuality(){} getQualities(){return [];}
}};`;
try {
  for(const viewport of [{width:1440,height:1000}])   /* phone flow: mobile-plain-playback.mjs (2026-10-10) */ {
    const context=await browser.newContext({viewport});
    await context.route('https://player.twitch.tv/js/embed/v1.js',r=>r.fulfill({contentType:'application/javascript',body:sdk}));
    const page=await context.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(String(e)));
    await page.goto(BASE+'/sq/a0b1c2?session=a1b2c3d4');   // 2026-10-09: cykul/lethul/falcated were opponents, no Watch together games
    await page.locator('table.night button.watch').first().click();
    await page.waitForFunction(()=>window.__mp?.length && window.__mp.every(p=>typeof p.pause==='function'));
    await page.locator('#mpause').click();
    await page.waitForTimeout(10500); // includes startup retry, watchdog, and drift timers
    assert(await page.evaluate(()=>window.__mp.every(p=>p.isPaused())), 'Pause must survive recovery timers');
    assert(!await page.locator('#mstart').isVisible(), 'Intentional pause must not show blocked-playback warning');
    if(viewport.width<900){
      await page.locator('.angles button').nth(1).click();
      await page.waitForTimeout(1800);
      assert(await page.evaluate(()=>window.__mp.every(p=>p.isPaused())), 'Changing angle must preserve pause');
    }
    await page.locator('#mplay').click();
    assert(await page.evaluate(()=>{const focus=document.querySelector('.angles button.on');return focus?!window.__mp[+focus.dataset.i].isPaused():window.__mp.every(p=>!p.isPaused())}), 'Play resumes visible angles');
    await page.keyboard.press('Escape');
    assert(!await page.locator('#multi').isVisible(), 'Escape closes');
    assert.deepEqual(errors,[]);
    console.log(`PASS ${viewport.width}x${viewport.height}: pause, delayed readiness/recovery, angle switch, resume, close; no page errors`);
    await context.close();
  }
} finally {await browser.close();}
