import {chromium} from 'playwright';
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
const context=await browser.newContext();const page=await context.newPage();const base=process.env.CT_BASE_URL||'https://clutchtape.com';
try{
 await page.goto(base+'/p/lethul');
 const save=page.locator('[data-save-profile]');const label=await save.getAttribute('data-label');
 if(!label)throw Error('Page restore removed bookmark label');
 await save.click();
 const values=await page.evaluate(()=>JSON.parse(localStorage.getItem('clutchtape.saved.v1')||'[]'));
 if(!values.some(x=>x.label===label&&x.url.includes('/p/lethul')))throw Error('Bookmark failed');
 await page.reload();if(await save.getAttribute('data-label')!==label)throw Error('Reload changed bookmark metadata');
 await save.click();if(await page.evaluate(()=>JSON.parse(localStorage.getItem('clutchtape.saved.v1')||'[]').length)!==0)throw Error('Remove shortcut failed');
 await page.goto(base+'/privacy');await page.locator('input[name=gamertag]').fill('<invalid>');await page.getByRole('button',{name:'Request removal',exact:true}).click();
 await page.getByRole('alert').waitFor();if(await page.getByRole('button',{name:'Request removal',exact:true}).isDisabled())throw Error('Validation left submit disabled');
 console.log('Bookmark save/reload/remove and form validation recovery passed.');
}finally{await browser.close()}
