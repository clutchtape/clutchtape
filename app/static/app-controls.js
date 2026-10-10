(()=>{'use strict';
const q=id=>document.getElementById(id), dialog=q('alerts-dialog'), install=q('install-dialog');
const csrf=JSON.parse(q('app-csrf').textContent);let deferred=null, registration=null, state=null, busy=false, current=null, revision=0;
const ios=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
const supported=(!ios||installed())&&isSecureContext&&'serviceWorker'in navigator&&'PushManager'in window&&'Notification'in window;
const status=text=>{q('alerts-status').textContent=text};
const el=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e};
function safeURL(value){try{const u=new URL(value,location.origin);return u.origin===location.origin?u.pathname+u.search:'/'}catch{return'/'}}
async function api(path,data){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);let response;try{response=await fetch('/api/alerts/'+path,{method:data===undefined?'GET':'POST',headers:data===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:data===undefined?undefined:JSON.stringify(data),signal:controller.signal})}catch{throw Error('Connection interrupted. Try again shortly.')}finally{clearTimeout(timer)}let result;try{result=await response.json()}catch{throw Error(response.status===429?'Please wait a minute and try again.':'Could not update alerts. Reload this page and try again.')};if(!response.ok)throw Error(result.error||'Could not update alerts. Try again shortly.');return result}
function markRead(){try{localStorage.setItem('ct-alert-read',String(state?.events?.[0]?.id||0))}catch{}q('nav-alerts').dataset.unread='false'}
function render(){if(!state)return;
 q('alerts-streams').checked=state.settings.streams;q('alerts-results').checked=state.settings.results;q('alerts-games').checked=!!state.settings.games;const quiet=state.settings.quiet||{};q('alerts-quiet').checked=!!quiet.enabled;q('alerts-quiet-start').value=quiet.start||'22:00';q('alerts-quiet-end').value=quiet.end||'08:00';q('alerts-zone').value=quiet.zone||Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC';
 const enabled=state.enabled&&supported&&Notification.permission==='granted';q('alerts-push').textContent=state.enabled?'Turn off phone alerts':'Enable phone alerts';q('alerts-test').hidden=!enabled;q('alerts-push').disabled=!supported&&!state.enabled;
 const list=q('alerts-following');list.replaceChildren();if(!state.follows.length)list.append(el('p','No one followed yet. Add a player or squad above.'));
 state.follows.forEach(f=>{const row=el('div');row.className='alert-follow';const copy=el('div'),a=el('a',f.label);a.href=safeURL(f.url);copy.append(a,el('small',f.players.some(p=>p.channel)?'Streaming + results available':'Results available · add a Twitch link on the profile for streaming'));const remove=el('button','Unfollow');remove.type='button';remove.setAttribute('aria-label','Unfollow '+f.label);remove.onclick=()=>change(()=>save(state.follows.filter(x=>x.key!==f.key).map(x=>x.url)));const choices=el('div');choices.className='follow-options';for(const [kind,label] of [['streams','Streaming'],['results','Sessions'],['games','Games']]){const wrap=el('label'),input=el('input');input.type='checkbox';input.checked=f.options?.[kind]!==false;input.setAttribute('aria-label',label+' for '+f.label);input.onchange=()=>change(()=>save(undefined,{[f.key]:{...f.options,[kind]:input.checked}}));wrap.append(input,document.createTextNode(label));choices.append(wrap)}copy.append(choices);row.append(copy,remove);list.append(row)});
 const inbox=q('alerts-inbox');inbox.replaceChildren();if(!state.events.length)inbox.append(el('p','New streaming alerts and finished-session results will appear here.'));
 state.events.forEach(e=>{const a=el('a');a.className='alert-entry';a.href=safeURL(e.url);a.append(el('strong',e.title),el('span',e.body),el('small',new Date(e.at*1000).toLocaleString()));inbox.append(a)});
 let read=0;try{read=Number(localStorage.getItem('ct-alert-read')||0)}catch{}q('nav-alerts').dataset.unread=String(state.events.some(e=>e.id>read));
 if(dialog.open)markRead();
 window.dispatchEvent(new CustomEvent('ct-alert-state',{detail:state}));
 if(!supported)q('alerts-support').textContent=ios?'For phone alerts on iPhone or iPad, install ClutchTape using Safari’s Share → Add to Home Screen, then open the installed app.':'Phone notifications are unavailable in this browser. Your in-site inbox still works.';
 else if(Notification.permission==='denied')q('alerts-support').textContent='Notifications are blocked in your browser’s site settings. Allow them there, then enable phone alerts here.';
 else q('alerts-support').textContent=enabled?'Phone alerts are on, including when ClutchTape is closed. Delivery depends on your browser and device settings.':'Phone alerts can arrive while ClutchTape is closed. Enable them when you’re ready.';
}
async function change(fn){if(busy)return;revision++;busy=true;status('Saving…');dialog.querySelectorAll('button,input,select').forEach(e=>e.disabled=true);try{await fn();status('Saved.');render();return true}catch(e){status(e.message);return false}finally{busy=false;dialog.querySelectorAll('button,input,select').forEach(e=>e.disabled=false);render()}}
async function save(targets=state.follows.map(f=>f.url),overrides={}){state=await api('preferences',{targets,overrides,settings:{streams:q('alerts-streams').checked,results:q('alerts-results').checked,games:q('alerts-games').checked,quiet:{enabled:q('alerts-quiet').checked,start:q('alerts-quiet-start').value,end:q('alerts-quiet-end').value,zone:q('alerts-zone').value}}})}
async function add(target){const f=await api('resolve?target='+encodeURIComponent(target));if(state.follows.some(x=>x.key===f.key)){status('Already following this player or squad.');return}await save([...state.follows.map(x=>x.url),f.url]);q('alert-target').value=''}
async function load(){const version=revision,next=await api('state');if(busy||version!==revision)return;state=next;render()}
function openAlerts(){dialog.showModal();status('Loading your alert choices…');load().then(()=>status('')).catch(e=>status(e.message));const target=location.pathname+location.search;q('alerts-current').hidden=true;current=null;if(/^\/(p|sq|squad|live|history|weekly|practice|scrims)\//.test(location.pathname))api('resolve?target='+encodeURIComponent(target)).then(f=>{current=f;q('alerts-current').textContent='Follow '+(f.players.length>1?'this squad':'this player');q('alerts-current').hidden=false}).catch(()=>{current=null});
 try{const saved=JSON.parse(localStorage.getItem('clutchtape.saved.v1')||'[]');const entries=Array.isArray(saved)?saved.filter(s=>s&&typeof s.url==='string'&&typeof s.label==='string'&&safeURL(s.url)!=='/').slice(0,20):[];q('alerts-saved').hidden=!entries.length;q('alert-saved').replaceChildren(...entries.map(s=>{const o=el('option',s.label);o.value=safeURL(s.url);return o}))}catch{q('alerts-saved').hidden=true}
}
q('nav-alerts').onclick=openAlerts;
document.addEventListener('click',e=>{if(e.target.closest('[data-open-alerts]'))openAlerts();if(e.target.closest('[data-open-install]'))q('nav-install').click();if(e.target.closest('[data-close-dialog]'))e.target.closest('dialog').close()});
q('alerts-current').onclick=()=>change(()=>current&&add(current.url));q('alerts-add-saved').onclick=()=>change(()=>add(q('alert-saved').value));q('alerts-add').onsubmit=e=>{e.preventDefault();if(state)change(()=>add(q('alert-target').value.trim()))};
for(const id of ['alerts-streams','alerts-results','alerts-games'])q(id).onchange=()=>{if(state)change(()=>save())};
q('alerts-save-quiet').onclick=()=>{if(state)change(()=>save())};
function keyBytes(value){return Uint8Array.from(atob(value.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-value.length%4)%4)),c=>c.charCodeAt(0))}
q('alerts-push').onclick=async()=>{
 if(!state||busy)return;
 if(!state.enabled&&!state.follows.length){status('Follow a player or squad first.');return}
 // Ask directly in the click gesture, before fetching or waiting for a worker.
 const permission=state.enabled?null:Notification.requestPermission();
 await change(async()=>{
  if(state.enabled){state=await api('unsubscribe',{});const reg=await registration;const sub=await reg?.pushManager.getSubscription();if(sub)await sub.unsubscribe();return}
  if(await permission!=='granted')throw Error('Notifications weren’t allowed. You can still use the in-site inbox.');
  const reg=await registration;if(!reg)throw Error('App setup is unavailable. Reload and try again.');
  let sub=await reg.pushManager.getSubscription(),created=false;
  if(sub){await sub.unsubscribe();sub=null}
  if(!sub){sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:keyBytes(state.key)});created=true}
  try{state=await api('subscribe',sub.toJSON())}catch(e){if(created)await sub.unsubscribe();throw e}
 });
};
q('alerts-test').onclick=async()=>{if(busy)return;const ok=await change(async()=>{await api('test',{})});if(ok)status('Test alert queued for this device. It should arrive within a minute.')};
if('serviceWorker'in navigator&&isSecureContext){registration=navigator.serviceWorker.register('/sw.js',{scope:'/',updateViaCache:'none'}).then(async reg=>{if(reg.active)return reg;await navigator.serviceWorker.ready;return reg}).catch(()=>null)}else registration=Promise.resolve(null);
function installed(){return matchMedia('(display-mode: standalone)').matches||navigator.standalone===true}
function installState(){q('nav-install').textContent=installed()?'Installed':'Install';q('nav-install').disabled=installed();document.querySelectorAll('[data-open-install]').forEach(b=>{b.disabled=installed();b.textContent=installed()?'Installed':'Install app'});q('install-native').hidden=!deferred||installed()}
addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferred=e;installState()});addEventListener('appinstalled',()=>{deferred=null;install.close();installState()});
async function promptInstall(){if(!deferred)return;const prompt=deferred;deferred=null;await prompt.prompt();await prompt.userChoice;installState()}
q('nav-install').onclick=()=>{if(deferred){promptInstall().catch(()=>{install.showModal();installState()});return}q('install-instructions').textContent=ios?'In Safari, tap Share, then Add to Home Screen and Add. Open ClutchTape from that icon.':/Android/.test(navigator.userAgent)?'In Chrome, open the ⋮ menu and choose Add to Home screen or Install app. If it says Create shortcut, refresh this page after your first visit and try again.':'Use your browser’s install icon in the address bar, or choose Install ClutchTape / Install this page as an app from its menu. If installation isn’t supported, bookmark the site instead.';install.showModal();installState()};q('install-native').onclick=()=>promptInstall();installState();
// One lightweight poll per visible page; the server delivers background push independently.
function poll(){if(!document.hidden&&!busy)load().catch(()=>{})}setInterval(poll,60000);addEventListener('visibilitychange',()=>{if(!document.hidden)poll()});load().catch(()=>{});
})();
