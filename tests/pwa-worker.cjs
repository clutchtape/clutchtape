const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const handlers={},notifications=[],opened=[],cached=[];
const self={location:{origin:'https://clutchtape.example'},addEventListener:(k,fn)=>handlers[k]=fn,skipWaiting:async()=>{},registration:{showNotification:async(...x)=>notifications.push(x)},clients:{claim:async()=>{},matchAll:async()=>[],openWindow:async url=>opened.push(url)}};
const context={self,URL,caches:{open:async()=>({add:async path=>cached.push(path)}),keys:async()=>['clutchtape-offline-v0','unrelated-cache'],delete:async key=>cached.push('delete:'+key),match:async()=>({offline:true})},fetch:async()=>{throw Error('offline')}};
vm.runInNewContext(fs.readFileSync('app/static/sw.js','utf8'),context);
async function event(name,props={}){let result;handlers[name]({...props,waitUntil:p=>{result=p},respondWith:p=>{result=p}});return await result}
(async()=>{await event('install');assert(cached.includes('/static/offline.html'));await event('activate');assert(cached.includes('delete:clutchtape-offline-v0'));assert(!cached.includes('delete:unrelated-cache'));
await event('push',{data:{json:()=>({title:'Streaming',body:'Player A',url:'https://evil.example',tag:'broadcast1'})}});assert.equal(notifications[0][1].data.url,'https://clutchtape.example/');
await event('notificationclick',{notification:{data:{url:'/sq/test'},close(){}}});assert.equal(opened[0],'https://clutchtape.example/sq/test');
assert.equal((await event('fetch',{request:{mode:'navigate',url:'https://clutchtape.example/sq/test'}})).offline,true);
assert.equal(await event('fetch',{request:{mode:'navigate',url:'https://player.twitch.tv/'}}),undefined);assert.equal(await event('fetch',{request:{mode:'cors',url:'https://clutchtape.example/api/alerts/state'}}),undefined);
console.log('PASS service worker: offline fallback, network-only API/Twitch, notification routing and origin checks');})().catch(e=>{console.error(e);process.exitCode=1});
