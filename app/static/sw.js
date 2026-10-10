/* Only an offline landing page is cached. Stats, sessions and Twitch stay network-only. */
const CACHE='clutchtape-offline-v1';
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.add('/static/offline.html')).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('clutchtape-offline-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
 if(event.request.mode==='navigate'&&new URL(event.request.url).origin===self.location.origin){event.respondWith(fetch(event.request).catch(()=>caches.match('/static/offline.html')))}
});
function safeURL(value){try{const url=new URL(value||'/',self.location.origin);return url.origin===self.location.origin?url.href:self.location.origin+'/'}catch{return self.location.origin+'/'}}
self.addEventListener('push',event=>{
 let data={};try{data=event.data?.json()||{}}catch{}
 event.waitUntil(self.registration.showNotification(String(data.title||'ClutchTape'),{body:String(data.body||'New activity from the players you follow.'),icon:'/static/icon-192.png?v=2',badge:'/static/icon-192.png?v=2',tag:String(data.tag||'clutchtape'),data:{url:safeURL(data.url)}}));
});
self.addEventListener('notificationclick',event=>{
 event.notification.close();const url=safeURL(event.notification.data?.url);
 event.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(async windows=>{
  const exact=windows.find(w=>w.url===url);if(exact)return exact.focus();
  // Open the result separately: never navigate away from a running multistream.
  return self.clients.openWindow(url);
 }));
});
