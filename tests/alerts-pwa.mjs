import assert from 'node:assert/strict';
import {chromium} from 'playwright';
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const base=process.env.CT_TEST_URL||'http://localhost:8140';
try{for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
 const c=await browser.newContext({viewport,isMobile:viewport.width<900,hasTouch:viewport.width<900});await c.addInitScript(()=>{window._permissionRequests=0;const ask=Notification.requestPermission.bind(Notification);Notification.requestPermission=(...args)=>{window._permissionRequests++;return ask(...args)}});const p=await c.newPage(),errors=[],failed=[];
 p.on('pageerror',e=>errors.push(e.message));p.on('response',r=>{if(r.url().startsWith(base+'/api/alerts')&&r.status()>=500)failed.push(r.status())});
 await p.goto(base+'/sq/d3e4f5',{waitUntil:'domcontentloaded'});await p.locator('#nav-alerts').click();await p.waitForFunction(()=>document.querySelector('#alerts-status').textContent==='');await p.locator('#alerts-current').click();await p.waitForFunction(()=>document.querySelectorAll('.alert-follow').length===1);
 assert(await p.locator('#alerts-following').innerText());assert.equal(await p.evaluate(()=>window._permissionRequests),0);
 await p.evaluate(()=>{Notification.requestPermission=async()=>{window._permissionRequests++;return 'denied'}});await p.locator('#alerts-push').click();await p.waitForFunction(()=>document.querySelector('#alerts-status').textContent.includes('weren’t allowed'));assert.equal(await p.evaluate(()=>window._permissionRequests),1);
 await p.locator('#alerts-results').uncheck();await p.waitForFunction(()=>document.querySelector('#alerts-status').textContent==='Saved.');
 await p.locator('#alerts-dialog [data-close-dialog]').click();await p.goto(base+'/about',{waitUntil:'domcontentloaded'});await p.locator('#nav-alerts').click();await p.waitForFunction(()=>document.querySelectorAll('.alert-follow').length===1);assert.equal(await p.locator('#alerts-results').isChecked(),false);await p.locator('#alerts-results').check();
 await p.locator('.alert-follow button').click();await p.waitForFunction(()=>document.querySelectorAll('.alert-follow').length===0);
 await p.locator('#alert-target').fill('Missing-ct-alert-987');await p.locator('#alerts-add button').click();await p.waitForFunction(()=>document.querySelector('#alerts-status').textContent.includes('first'));
 await p.locator('#alerts-dialog [data-close-dialog]').click();
 const worker=await p.evaluate(async()=>{const r=await navigator.serviceWorker.ready;return {scope:r.scope,active:r.active?.state}});assert.equal(worker.scope,base+'/');assert.equal(worker.active,'activated');
 const session=await c.newCDPSession(p);const manifest=await session.send('Page.getAppManifest');assert.equal(manifest.errors.length,0);
 // Exercise native-prompt handling deterministically; actual OS install UI requires the device.
 await p.evaluate(()=>{const e=new Event('beforeinstallprompt',{cancelable:true});e.prompt=async()=>{window._prompted=true};e.userChoice=Promise.resolve({outcome:'dismissed'});dispatchEvent(e)});await p.locator('#nav-install').click();assert(await p.evaluate(()=>window._prompted));
 await p.locator('#nav-install').click();assert(await p.locator('#install-dialog').isVisible());await p.locator('#install-dialog [data-close-dialog]').click();
 assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth-innerWidth),0);assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
 await c.setOffline(true);await p.goto(base+'/about',{waitUntil:'domcontentloaded'});assert.match(await p.locator('h1').innerText(),/offline/);await c.setOffline(false);
 await c.close();console.log('PASS alerts/PWA '+viewport.width+': follow, persistence, toggles, unfollow, error, manifest, worker, install branches, offline');
}}finally{await browser.close()}
