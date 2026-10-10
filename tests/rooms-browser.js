async (page) => {
 const base='https://test.clutchtape.example',stamp=Date.now().toString(36),password='Review-test-'+stamp+'-passphrase',results=[],errors=[];
 const check=(name,pass)=>{results.push({name,pass:!!pass});if(!pass)throw Error(name)};
 const browser=page.context().browser(),ca=await browser.newContext({viewport:{width:1440,height:1000}}),cb=await browser.newContext({viewport:{width:390,height:844}}),cc=await browser.newContext();
 const a=await ca.newPage(),b=await cb.newPage(),c=await cc.newPage();
 for(const p of [a,b,c])p.on('pageerror',e=>errors.push(e.message));
 async function register(p,name){await p.goto(base+'/rooms');await p.locator('[name=name]').fill(name);await p.locator('[name=password]').fill(password);await p.getByRole('button',{name:'Create account',exact:true}).click();await p.waitForURL(base+'/rooms');await p.getByRole('heading',{name:'Your rooms',exact:true}).waitFor()}
 let roomUrl;
 try{
 await register(a,'ct_verify_owner_'+stamp);await register(b,'ct_verify_member_'+stamp);
 await a.locator('[name=name]').fill('Verification squad '+stamp);await a.getByRole('button',{name:'Create room',exact:true}).click();await a.waitForURL(/\/rooms\/.+/);roomUrl=a.url();check('Room creation',await a.getByRole('heading',{name:'Review board',exact:true}).isVisible());
 const anon=await c.request.get(roomUrl);check('Anonymous cannot open private room',anon.status()===401);
 const outsider=await b.request.get(roomUrl);check('Signed-in outsider cannot open private room',outsider.status()===404);
 await a.getByRole('button',{name:'Create invitation',exact:true}).click();const invite=await a.locator('#invite-link').inputValue();check('Private invitation no-store',(await a.request.get(roomUrl)).headers()['cache-control']==='no-store');
 await b.goto(invite);await b.getByRole('button',{name:'Join room',exact:true}).click();await b.waitForURL(roomUrl);check('Invite joins correct room',await b.getByRole('heading',{name:'Review board',exact:true}).isVisible());check('Member has no owner controls',await b.getByRole('button',{name:'Create invitation',exact:true}).count()===0);
 await a.goto(base+'/history/lethul');const moment=base+await a.locator('.history-row').first().getAttribute('href');await a.goto(roomUrl);await a.locator('[name=url]').fill(moment);await a.locator('textarea[name=body]').first().fill('Review this opening together. Verification note.');await a.getByRole('button',{name:'Post to this room',exact:true}).click();await a.waitForURL(/#discussion$/);check('Shared game moment posted',await a.getByRole('link',{name:'Open shared moment',exact:false}).count()===1);
 await b.reload();await b.getByText('Reply to this discussion',{exact:true}).click();await b.locator('.discussion-post textarea').fill('Check the first decision after the opening fight.');await b.getByRole('button',{name:'Post reply',exact:true}).click();await b.waitForURL(/#discussion$/);check('Member reply posted',await b.getByText('Check the first decision after the opening fight.',{exact:true}).isVisible());
 check('Private room fits mobile',await b.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await b.screenshot({path:'/tmp/clutchtape-growth-20261007/room-mobile.png',fullPage:true});
 await a.reload();await a.screenshot({path:'/tmp/clutchtape-growth-20261007/room-desktop.png',fullPage:true});await a.getByRole('button',{name:'Revoke invitation',exact:true}).click();check('Revoked invite rejects joining',(await c.request.get(invite)).status()===404);
 await a.getByRole('button',{name:'Remove',exact:true}).click();check('Removed member immediately loses access',(await b.request.get(roomUrl)).status()===404);
 await a.goto(base+'/rooms');await a.getByRole('button',{name:'Sign out',exact:true}).click();check('Sign out ends access',(await a.request.get(roomUrl)).status()===401);
 await a.locator('[name=name]').fill('ct_verify_owner_'+stamp);await a.locator('[name=password]').fill(password);await a.getByRole('button',{name:'Sign in',exact:true}).click();await a.getByRole('heading',{name:'Your rooms',exact:true}).waitFor();check('Existing account signs in',true);
 // Remove only the empty-purpose verification room created by this test.
 await a.goto(roomUrl);await a.getByText('Delete this room',{exact:true}).click();await a.getByRole('button',{name:'Permanently delete room',exact:true}).click();await a.waitForURL(base+'/rooms');check('Own verification room cleanup',(await a.request.get(roomUrl)).status()===404);
 check('No uncaught browser errors',errors.length===0);
 return {results,errors};
 }finally{await ca.close();await cb.close();await cc.close()}
}
