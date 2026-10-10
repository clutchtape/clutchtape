(function(){
'use strict';
var board=document.getElementById('companion'), session=document.getElementById('board-session');
if(session)session.addEventListener('change',function(){location.assign(this.value)});
var saved=document.getElementById('live-saved');
if(saved){try{var entries=JSON.parse(localStorage.getItem('clutchtape.saved.v1')||'[]');if(Array.isArray(entries))entries.slice(0,20).forEach(function(e){var u=new URL(e.url,location.origin);if(u.origin!==location.origin||!/^\/(p|squad|live)\/[a-z0-9,-]+$/.test(u.pathname))return;var a=document.createElement('a');a.className='saved-live-link';a.textContent=String(e.label).slice(0,180)+' ↗';a.href='/live/'+u.pathname.split('/')[2]+u.search;saved.append(a)});if(saved.childElementCount)document.getElementById('live-saved-status').hidden=true;}catch(e){document.getElementById('live-saved-status').textContent='Saved players are unavailable because browser storage is blocked or unreadable.'}}
var choices=[].slice.call(document.querySelectorAll('.player-choices input'));choices.forEach(function(c){c.addEventListener('change',function(){var n=choices.filter(x=>x.checked).length;choices.forEach(x=>x.disabled=n>=4&&!x.checked)})});
if(board){
 function updateAge(){var e=document.getElementById('last-ended');if(!e||!Number(e.dataset.ended))return;var s=Math.max(0,Date.now()/1000-Number(e.dataset.ended));var value=s>=86400?Math.floor(s/86400)+'d ago':s>=3600?Math.floor(s/3600)+'h ago':s>=60?Math.floor(s/60)+'m ago':'just now';e.textContent='Last game ended '+value;}
 updateAge();setInterval(updateAge,30000);
 var busy=false,version=board.dataset.version,status=document.getElementById('board-status'),button=document.getElementById('board-refresh');
 async function refresh(manual){
  if(busy||(!manual&&document.hidden&&board.dataset.alerts!=='true'))return;
  if(board.dataset.current!=='true'){if(manual)location.reload();return}
  busy=true;button.disabled=true;status.textContent='Checking for completed games…';
  var controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
  try{var u=new URL('/api/companion/'+board.dataset.slugs,location.origin);u.search=location.search;['session','match','at'].forEach(k=>u.searchParams.delete(k));u.searchParams.set('version',version);var r=await fetch(u,{cache:'no-store',signal:controller.signal});if(!r.ok)throw Error();var j=await r.json();
   if(j.changed){window.dispatchEvent(new CustomEvent('clutchtape:result',{detail:j.latest}));version=j.version;document.getElementById('board-new').hidden=false;}
   status.textContent=j.changed?'New results ready. Refresh to update.':j.syncing?'Updating…':'Checked just now.';
  }catch(e){status.textContent='Update failed. Retrying…'}
  finally{clearTimeout(timer);busy=false;button.disabled=false}
 }
 button.addEventListener('click',()=>{if(!document.getElementById('board-new').hidden)location.reload();else refresh(true)});refresh(false);setInterval(()=>refresh(false),30000+Math.random()*10000);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh(false)});
}
// Explicit device-local notes. Copy links only; personal notes never enter the URL.
var key='clutchtape.notes.v1',list=document.getElementById('review-bookmarks'),note=document.getElementById('recap-note');
function safeUrl(raw){try{var u=new URL(raw,location.origin);return u.origin===location.origin&&/^\/live\/[a-z0-9,-]+$/.test(u.pathname)?u.pathname+u.search+u.hash:null}catch(e){return null}}
function read(){var a=JSON.parse(localStorage.getItem(key)||'[]');if(!Array.isArray(a))throw Error();return a.filter(e=>e&&typeof e.id==='string'&&typeof e.note==='string'&&typeof e.label==='string'&&safeUrl(e.url)).slice(0,100)}
function tell(s){if(window.toast)window.toast(s);var status=document.getElementById('bookmark-status');if(status)status.textContent=s}
function write(a){localStorage.setItem(key,JSON.stringify(a));render()}
function smallButton(text,fn){var b=document.createElement('button');b.type='button';b.className='secondary';b.textContent=text;b.addEventListener('click',fn);return b}
async function copy(url){try{await navigator.clipboard.writeText(new URL(url,location.origin).href);tell('Moment link copied. Your note stays private.')}catch(e){prompt('Copy this moment link',new URL(url,location.origin).href)}}
function render(){if(!list)return;list.replaceChildren();try{var a=read();var local=board?a.filter(e=>new URL(e.url,location.origin).pathname==='/live/'+board.dataset.slugs):a;if(!local.length){var empty=document.createElement('p');empty.className='empty-copy';empty.textContent='No bookmarks for these players yet. Save your first moment from the event timeline.';list.append(empty)}local.forEach(function(e){var row=document.createElement('article'),text=document.createElement('div'),link=document.createElement('a'),p=document.createElement('p'),actions=document.createElement('div');row.className='bookmark-row';link.href=safeUrl(e.url);link.textContent=e.label;p.textContent=e.note;text.append(link,p);actions.className='bookmark-actions';actions.append(smallButton('Edit',function(){var area=document.createElement('textarea');area.maxLength=500;area.value=e.note;area.setAttribute('aria-label','Edit review note');p.replaceWith(area);actions.replaceChildren(smallButton('Save note',function(){try{write(read().map(x=>x.id===e.id?Object.assign({},x,{note:area.value.trim()}):x));tell('Note updated on this device')}catch(err){tell('Could not save. Browser storage may be disabled or full.')}}),smallButton('Cancel',render));area.focus()}),smallButton('Copy link',()=>copy(e.url)),smallButton('Remove',function(){try{write(read().filter(x=>x.id!==e.id));tell('Bookmark removed from this device')}catch(err){tell('Could not update device storage.')}}));row.append(text,actions);list.append(row)})}catch(e){tell('Bookmarks are unavailable because browser storage is blocked or unreadable.')}}
var save=document.getElementById('recap-bookmark'),share=document.getElementById('recap-share');
if(save)save.addEventListener('click',function(){var state=window.ClutchRecap&&window.ClutchRecap.state();if(!state)return;tell('');try{var a=read(),id=state.url;if(!a.some(x=>x.id===id)&&a.length>=100){tell('You have 100 bookmarks. Remove an old one before saving another.');return}var entry={id:id,url:state.url,label:state.label,note:note.value.trim().slice(0,500)};write([entry].concat(a.filter(x=>x.id!==id)));note.value='';tell('Moment and note saved on this device.')}catch(e){tell('Could not save. Browser storage may be disabled or full.')}});
if(share)share.addEventListener('click',function(){var state=window.ClutchRecap&&window.ClutchRecap.state();if(state)copy(state.url)});
addEventListener('storage',e=>{if(e.key===key||e.key===null)render()});render();
})();
