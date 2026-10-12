// Shared game link (2026-10-12): /sq/<code>/g/<game>#w=chan..chan opens every angle in a browser that never saw the channels.
// Run (needs playwright):  node tests/e2e.mjs [baseUrl]
const [U]=process.argv.slice(2);const S='/tmp/fr/';
const b=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const p=await b.newPage({viewport:{width:1440,height:900}});const errs=[];p.on('pageerror',e=>{if(!/getLayoutMap/.test(e.message))errs.push(e.message)});
await p.goto(U,{waitUntil:'load'});await p.waitForTimeout(9000);
console.log(JSON.stringify(await p.evaluate(()=>{const m=document.getElementById('multi');const tr=document.querySelector('table.night tr[data-mid^="547a4f94"]');
 return {url:location.pathname+location.search+location.hash,multiOpen:m&&!m.hidden,cells:document.querySelectorAll('#multi .mcell').length,frames:[...document.querySelectorAll('#multi iframe')].length,row:!!tr,gwatch:tr&&tr.dataset.gwatch?JSON.parse(tr.dataset.gwatch).map(x=>x.who||x.video):null}})),errs.slice(0,2));
await p.screenshot({path:S+'angles.png'});await b.close();
