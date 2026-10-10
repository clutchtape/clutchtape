import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';
import {chromium} from 'playwright';
const source=await fs.readFile(new URL('./multistream-playback.mjs',import.meta.url),'utf8');
const sdk=vm.runInNewContext(source.slice(source.indexOf('const sdk='),source.indexOf('const browser='))+';sdk;').replace("this.muted=o.muted","this.muted=false").replace("this.emit('ready')},50)","this.muted=o.muted;this.emit('ready')},1800)");
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
try{
 const c=await browser.newContext({viewport:{width:1440,height:1000}});await c.route('https://player.twitch.tv/js/embed/v1.js',r=>r.fulfill({contentType:'application/javascript',body:sdk}));const p=await c.newPage(),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto('https://test.clutchtape.example/sq/d3e4f5/g/95131356');await p.waitForFunction(()=>window.__mp?.length===3&&window._sdk?.filter(p=>p.ready).length>=3);
 assert(await p.evaluate(()=>window.__mp.every(p=>!p.isArchive())),'Public playback uses Twitch only');
 await p.evaluate(()=>window._original=window.__mp.slice());await p.locator('#mpause').click();await p.locator('#mplay').click();assert(await p.evaluate(()=>window.__mp.every(p=>!p.isPaused())),'Desktop explicit start works immediately after Pause');assert(await p.evaluate(()=>window.__mp.every((p,i)=>p===window._original[i])),'Desktop retains embeds');
 assert(await p.evaluate(()=>window._sdk.slice(-3).every(p=>!p.calls.some(c=>c[0]==='seek'))),'No redundant startup seek');
 assert.deepEqual(errors,[]);await p.locator('#mclose').click();console.log('PASS desktop: Twitch-only, immediate resume, preserved embeds');await c.close();
}finally{await browser.close()}
