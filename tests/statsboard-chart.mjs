// Stats board session chart (2026-10-11): All (small multiples) + CSR/CSR±/KDA/Dmg/Score views, shared hover, compact rows, CSR in the table.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
const [U]=process.argv.slice(2);const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
for(const [w,h] of [[1440,1000],[390,844]]){const ctx=await b.newContext({viewport:{width:w,height:h},isMobile:w<700});const p=await ctx.newPage();const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
await p.goto(U,{waitUntil:'load'});await p.evaluate(()=>localStorage.setItem('ct-statsonly','1'));await p.reload({waitUntil:'load'});await p.waitForTimeout(4000);
const r=await p.evaluate(()=>{const c=document.querySelector('.sb-chartbox');if(!c)return null;const s=c.querySelector('svg');return {view:[...c.querySelectorAll('[data-metric][aria-pressed=true]')].map(b=>b.dataset.metric).join(),cells:c.querySelectorAll('.sb-cell').length,svg:!!s,lines:c.querySelectorAll('.sb-line').length,dots:c.querySelectorAll('.sb-dot').length,legend:c.querySelector('.sb-legend').innerText.replace(/\n/g,' '),rows:document.querySelectorAll('.sb-row').length,ovx:document.documentElement.scrollWidth>innerWidth}});
console.log(w,JSON.stringify(r),errs);
const box=p.locator('#statsboard');await box.scrollIntoViewIfNeeded();await box.screenshot({path:S+`sbchart-${w}.png`});
const svg=p.locator('.sb-svg').first();const bb=await svg.boundingBox();await p.mouse.move(bb.x+bb.width*0.6,bb.y+60);await p.waitForTimeout(300);await p.locator('.sb-chartbox').screenshot({path:S+`sbchart-hover-${w}.png`});
console.log(w,'crosshairs visible',await p.evaluate(()=>[...document.querySelectorAll('.sb-cross')].filter(c=>c.getAttribute('visibility')==='visible').length),'tip',await p.evaluate(()=>document.querySelector('.sb-tip').innerText.replace(/\n/g,' | ').slice(0,200)));
await p.locator('[data-metric=rating]').click();await p.waitForTimeout(200);await p.locator('.sb-chartbox').screenshot({path:S+`sbchart-csr-${w}.png`});
console.log(w,'table head',await p.evaluate(()=>[...document.querySelectorAll('#livevs thead th')].slice(0,5).map(th=>th.textContent.trim()).join(' | ')));
for(const m of ['kda','dmg_pm']){await p.locator(`[data-metric=${m}]`).click();await p.waitForTimeout(200)}
await p.locator('.sb-chartbox').screenshot({path:S+`sbchart-dmg-${w}.png`});await p.evaluate(()=>localStorage.removeItem('ct-sbmetric'));
await p.locator('.sb-row summary').first().click();await p.waitForTimeout(300);console.log(w,'row open',await p.evaluate(()=>document.querySelector('.sb-row').open));
await ctx.close()}
await b.close();
