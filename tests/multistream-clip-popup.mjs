// Multistream (2026-10-12): multistream-clip-popup.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
const [U]=process.argv.slice(2);const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
for(const [w,h] of [[1440,900],[1920,1080],[1366,768]]){const p=await b.newPage({viewport:{width:w,height:h}});
await p.goto(U,{waitUntil:'load'});await p.waitForSelector('#mtl .et-clip',{state:'attached',timeout:30000}).catch(()=>{});await p.waitForTimeout(2000);
const n=await p.locator('#mtl .et-clip').count();let bad=0,res=[];
for(let i=0;i<Math.min(n,6);i++){const m=p.locator('#mtl .et-clip').nth(i);const bb=await m.boundingBox();if(!bb)continue;await p.mouse.move(bb.x+bb.width/2,bb.y+bb.height/2);await p.waitForTimeout(350);
 const r=await p.evaluate(()=>{const pp=document.querySelector('#mtl .et-popup');if(pp.hidden)return null;const r=pp.getBoundingClientRect();const over=[...document.querySelectorAll('iframe')].some(f=>{const q=f.getBoundingClientRect();return q.left<r.right&&q.right>r.left&&q.top<r.bottom&&q.bottom>r.top});return {t:Math.round(r.top),b:Math.round(r.bottom),on:r.top>=0&&r.bottom<=innerHeight,over}});
 res.push(r);if(!r||!r.on||r.over)bad++;}
const vids=await p.evaluate(()=>[...document.querySelectorAll('#multi iframe')].length);
console.log(w+'x'+h,'clips',n,'checked',res.length,bad?'FAIL':'PASS','(on screen, over no video)',JSON.stringify(res.slice(0,3)),'videos',vids);
await p.screenshot({path:S+`mtl2-${w}.png`});await p.close()}
await b.close();
