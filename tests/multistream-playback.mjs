import assert from 'node:assert/strict';
import {chromium} from 'playwright';
const base=process.argv[2]||'http://localhost:8140';
const sdk=`window._sdk=[];window.Twitch={Player:class {
 static READY='ready';static PAUSE='pause';static PLAY='play';static PLAYING='playing';static SEEK='seek';static PLAYBACK_BLOCKED='blocked';
 constructor(id,o){this.events={};this.calls=[];this.paused=!o.autoplay;this.muted=o.muted;let m=o.time.match(/(\\d+)h(\\d+)m(\\d+)s/);this.t=m?(+m[1]*3600+ +m[2]*60+ +m[3]):0;this.at=Date.now();this.ready=false;window._sdk.push(this);let h=typeof id==='string'?document.getElementById(id):id;h.appendChild(document.createElement('iframe'));setTimeout(()=>{this.ready=true;this.emit('ready')},50)}
 emit(e){(this.events[e]||[]).forEach(f=>f())} addEventListener(e,f){(this.events[e]??=[]).push(f)}
 getCurrentTime(){return this.t+(this.paused?0:(Date.now()-this.at)/1000)}
 seek(t){this.calls.push(['seek',t]);this.t=t;this.at=Date.now();this.emit('seek')}
 play(){this.calls.push(['play']);if(this.paused){this.paused=false;this.at=Date.now();this.emit('play')}this.emit('playing')}
 pause(){this.calls.push(['pause']);this.t=this.getCurrentTime();this.paused=true;this.emit('pause')}
 isPaused(){return this.paused} setMuted(m){this.calls.push(['mute',m]);this.muted=m} getMuted(){return this.muted}
 setVolume(){} setQuality(){this.calls.push(['quality'])}getQualities(){return []}getVideo(){return ''}
}};`;
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
try{
 for(const viewport of [{width:1440,height:1000}])   /* phone flow: mobile-plain-playback.mjs (2026-10-10) */{
  const context=await browser.newContext({viewport});await context.addInitScript(()=>{try{localStorage.setItem('ct-mobile-stats','off')}catch(e){}});await context.route('https://player.twitch.tv/js/embed/v1.js',r=>r.fulfill({contentType:'application/javascript',body:sdk}));
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(base+'/sq/a0b1c2/g/a1b2c3d4');
  await page.waitForFunction(()=>window.__mp?.length===2&&window._sdk?.filter(p=>p.ready).length>=2);
  await page.waitForTimeout(500);await page.evaluate(()=>window._original=window.__mp.slice());
  if(viewport.width<900){
    assert(await page.locator('#multi').evaluate(e=>e.classList.contains('nolog')),'Stats closed by default on mobile');
    assert(await page.locator('#mobile-options .mg-game-select').count(),'Game navigation lives in the More menu, independent of stats');
    await page.locator('#mobile-views').selectOption('2');
    assert.equal(await page.locator('.mobile-visible').count(),2);
    // Provider PAUSE can precede PLAYBACK_BLOCKED, well after startup grace has ended.
    await page.waitForTimeout(5200);
    await page.evaluate(()=>{window._beforeStartupSeek=window._sdk.slice(-2)[1].calls.filter(c=>c[0]==='seek').length;window._sdk.slice(-2)[0].emit('seek')});
    assert.equal(await page.evaluate(()=>window._sdk.slice(-2)[1].calls.filter(c=>c[0]==='seek').length-window._beforeStartupSeek),0,'Delayed SDK seek must not create a seek feedback loop');

    await page.evaluate(()=>window._sdk.slice(-2)[0].pause());
    assert(await page.evaluate(()=>!window.__mp[1].isPaused()),'One mobile embed pausing must not pause its peer');
    await page.evaluate(()=>window._sdk.slice(-2)[0].emit('blocked'));
    assert(await page.evaluate(()=>!window.__mp[1].isPaused()),'Late autoplay block must not stop the other angle');
    await page.locator('#mplay').click();
    const geometry=await page.locator('.mcell.mobile-visible .mvid').evaluateAll(es=>es.map(e=>JSON.stringify(e.getBoundingClientRect())));
    await page.locator('#mtl .etl').evaluate(e=>e.hidden=true);
    const unloaded=await page.locator('.mcell.mobile-visible .mvid').evaluateAll(es=>es.map(e=>JSON.stringify(e.getBoundingClientRect())));
    assert.deepEqual(unloaded,geometry,'Timeline arrival must not resize or move the two videos');
    await page.locator('#mtl .etl').evaluate(e=>e.hidden=false);

    await page.evaluate(()=>window._switchCalls=window._sdk.slice(-2).map(p=>p.calls.filter(c=>c[0]==='seek').length));
    if(viewport.width<900&&!(await page.locator('.angles button').nth(1).isVisible()))await page.locator('#moptions').click();   // phone: angles live in the More menu
    await page.locator('.angles button').nth(1).click();
    assert(await page.evaluate(()=>window.__mp.every(p=>!p.isPaused())),'Both angles continue playing after focus switch');
    assert(await page.evaluate(()=>window._sdk.slice(-2).every((p,i)=>p.calls.filter(c=>c[0]==='seek').length===window._switchCalls[i])),'Synced switch does not seek');
    await page.locator('#mobile-views').selectOption('1');
    assert.equal(await page.locator('.mobile-visible').count(),1);
    assert(await page.evaluate(()=>window.__mp.every(p=>!p.isPaused())),'App does not pause background angles');
    await page.locator('#mobile-views').selectOption('all');
    await page.locator('#mlogbtn').click();assert(await page.locator('.mgtable').isVisible(),'Stats available on tap');
  }
  await page.locator('#mpause').click();await page.waitForTimeout(2200);assert(await page.evaluate(()=>window.__mp.every(p=>p.isPaused())),'Pause survives timers');
  if(viewport.width<900){await page.locator('.angles button').nth(1).click();assert(await page.evaluate(()=>window.__mp.every(p=>p.isPaused())),'Changing angle preserves pause')}
  await page.locator('#mplay').click();assert(await page.evaluate(()=>{let i=document.querySelector('#multi').classList.contains('focus')?+document.querySelector('.angles button.on').dataset.i:0;return !window.__mp[i].isPaused()}));
  await page.waitForSelector('#mtl .et-clip.clip');
  if(viewport.width<900){
    await page.locator('#mpause').click();
    await page.locator('#mtl .etl').click({position:{x:125,y:65}});
    assert.equal(await page.locator('#mtl .et-popup').isVisible(),false,'Mobile timeline tap never opens popup');
    assert(await page.evaluate(()=>window.__mp.some(p=>!p.isPaused())),'Timeline requests play from paused');
    await page.locator('#mtl .et-clip.clip').first().hover();
    await page.locator('#mtl .et-clip.clip').first().focus();
    assert.equal(await page.locator('#mtl .et-popup').isVisible(),false,'Mobile synthetic hover and focus never open popup');
  }
await page.locator('#mpause').click();await page.locator('#mtl .et-clip.clip').first().click();
  assert(await page.evaluate(()=>!window.__mp[0].isPaused()),'ONE clip click resumes owner from pause');
  if(viewport.width<900)assert.equal(await page.locator('.angles button.on').textContent(),'x Ghost x');
  await page.evaluate(()=>{let p=window.__mp[0];window._clock=p.getCurrentTime;window._seek=p.seek;window._rapid=[];p.getCurrentTime=()=>1000;p.seek=function(t){window._rapid.push(t);return window._seek.call(p,t)}});
  await page.locator('[data-skip="10"]').click();await page.locator('[data-skip="10"]').click();
  const rapid=await page.evaluate(()=>{let p=window.__mp[0];p.getCurrentTime=window._clock;p.seek=window._seek;return window._rapid});
  assert(rapid[1]-rapid[0]>=10&&rapid[1]-rapid[0]<12,'Rapid skips compose against pending intent, not stale clock');
  await page.locator('.mg-game-select').selectOption('cb65aea3');await page.locator('[data-gnav="-1"]').click();
  assert(await page.evaluate(()=>window.__mp.every((p,i)=>p===window._original[i])),'Same VOD navigation retains players');
  await page.evaluate(()=>{window.__mp[0].setMuted(false);window._reference=window._sdk[window._sdk.length-2];window._reference.calls=[]});
  await page.waitForTimeout(6500);
  assert(await page.evaluate(()=>!window.__mp[0].getMuted()),'Unmute is retained');
  assert(await page.evaluate(()=>window.__mp.every((p,i)=>p===window._original[i])),'Unmute never rebuilds');
  assert.equal(await page.evaluate(()=>window._reference.calls.filter(x=>x[0]==='seek'||x[0]==='quality').length),0,'Audible reference is never chased/quality-switched');
  if(viewport.width<900){
    await page.evaluate(()=>{window._workingPeer=window.__mp[1];window._blockedEmbed=window.__mp[0];const raw=window._sdk.slice(-2)[0];raw.pause();raw.play=function(){this.calls.push(['blocked-play']);this.emit('blocked')};});
    await page.locator('#mplay').click();await page.waitForTimeout(1800);
    assert(await page.evaluate(()=>window.__mp[0]!==window._blockedEmbed),'Explicit mobile start retries a blocked embed once');
    assert(await page.evaluate(()=>window.__mp[1]===window._workingPeer),'Recovery preserves the working peer');
    await page.evaluate(()=>window._recovered=window.__mp[0]);await page.waitForTimeout(1800);
    assert(await page.evaluate(()=>window.__mp[0]===window._recovered),'Recovery does not continuously rebuild');
  }
  await page.locator('#mpause').click();await page.locator('#mclose').click();await page.waitForTimeout(1700);assert(await page.evaluate(()=>window._original.every(p=>p.isPaused())),'Close stops all old players');
  assert.deepEqual(errors,[]);console.log('PASS '+viewport.width+'x'+viewport.height+': pause, angle, one-click clip, Prev/Next/dropdown, reuse, audible reference, close');await context.close();
 }
}finally{await browser.close()}
