const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const constants={READY:'ready',PLAY:'play',PLAYING:'playing',PAUSE:'pause',SEEK:'seek',PLAYBACK_BLOCKED:'playbackBlocked'};
class Parent{};for(const [k,v] of Object.entries(constants))Object.defineProperty(Parent,k,{value:v});
class Player extends Parent {constructor(){super();this.handlers={};global.inner=this;}addEventListener(k,fn){(this.handlers[k]??=[]).push(fn)}}
const context={window:{Twitch:{Player}},document:{getElementById:()=>({querySelectorAll:()=>[],closest:()=>null})},setTimeout};vm.runInNewContext(fs.readFileSync('app/static/archiveplayer.js','utf8'),context);
for(const [k,v] of Object.entries(constants))assert.equal(context.window.Twitch.Player[k],v,k+' is preserved even when inherited and non-enumerable');
const p=new context.window.Twitch.Player('host',{video:'123'});let blocked=false,playing=false;p.addEventListener(context.window.Twitch.Player.PLAYBACK_BLOCKED,()=>blocked=true);p.addEventListener(context.window.Twitch.Player.PLAYING,()=>playing=true);inner.handlers.playbackBlocked[0]();inner.handlers.playing[0]();assert(blocked&&playing);console.log('PASS inherited Twitch constants and real playback event forwarding');
