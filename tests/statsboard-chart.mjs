// Stats board session chart (2026-10-11): lines per player, legend, W/L strip, metric switch, compact game rows.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
const [U]=process.argv.slice(2);const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
for(const [w,h] of [[1440,1000],[390,844]]){const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:w<700});const p=await ctx.newPage();const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
await p.goto(U,{waitUntil:'load'});await p.evaluate(()=>localStorage.setItem('ct-statsonly','1'));await p.reload({waitUntil:'load'});await p.waitForTimeout(4000);
const r=await p.evaluate(()=>{const c=document.querySelector('.sb-chartbox');if(!c)return null;const s=c.querySelector('svg');return {svg:!!s,lines:c.querySelectorAll('.sb-line').length,dots:c.querySelectorAll('.sb-dot').length,legend:c.querySelector('.sb-legend').innerText.replace(/\n/g,' '),rows:document.querySelectorAll('.sb-row').length,ovx:document.documentElement.scrollWidth>innerWidth}});
console.log(w,JSON.stringify(r),errs);
const box=p.locator('#statsboard');await box.scrollIntoViewIfNeeded();await box.screenshot({path:S+`sbchart-${w}.png`});
const svg=p.locator('.sb-svg');const bb=await svg.boundingBox();await p.mouse.move(bb.x+bb.width*0.6,bb.y+60);await p.waitForTimeout(300);await p.locator('.sb-chartbox').screenshot({path:S+`sbchart-hover-${w}.png`});
for(const m of ['kda','dmg_pm']){await p.locator(`[data-metric=${m}]`).click();await p.waitForTimeout(200)}
await p.locator('.sb-chartbox').screenshot({path:S+`sbchart-dmg-${w}.png`});await p.evaluate(()=>localStorage.setItem('ct-sbmetric','csr'));
await p.locator('.sb-row summary').first().click();await p.waitForTimeout(300);console.log(w,'row open',await p.evaluate(()=>document.querySelector('.sb-row').open));
await ctx.close()}
await b.close();
