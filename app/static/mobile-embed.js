/* Apply before the SDK attaches its iframe. Keep mobile playback local while leaving Twitch's controls visible. */
(()=>{'use strict';
const mobile=()=>matchMedia('(pointer:coarse)').matches||innerWidth<900;
function protect(frame){if(!mobile())return frame;const denied=new Set(['allow-popups','allow-popups-to-escape-sandbox','allow-top-navigation','allow-top-navigation-by-user-activation','allow-top-navigation-to-custom-protocols']);const flags=(frame.getAttribute('sandbox')||'allow-scripts allow-same-origin allow-presentation').split(/\s+/).filter(x=>x&&!denied.has(x));frame.setAttribute('sandbox',[...new Set(flags)].join(' '));frame.dataset.localPlayback='true';return frame}
function note(host,video,channel){if(!mobile()||!host.closest('#player'))return;const player=host.closest('#player');let row=player.querySelector('.mobile-playback-note');if(!row){row=document.createElement('div');row.className='mobile-playback-note';const text=document.createElement('span');text.textContent='Playback stays here.';const link=document.createElement('a');link.textContent='Open Twitch ↗';link.target='_blank';link.rel='noopener';row.append(text,link);player.append(row)}const link=row.querySelector('a'),id=String(video||'').replace(/^v/,'');link.href=/^\d+$/.test(id)?'https://www.twitch.tv/videos/'+id:'https://www.twitch.tv/'+encodeURIComponent(channel||'');}
window.ClutchMobileEmbed={protect,note};
// Menus use the browser's top layer instead of a full-screen stacking layer
// above the Twitch surfaces. Their original DOM and event handlers stay intact.
window.ClutchMobileEmbed.panels=function(multi){
  if(multi._mobilePanels)return;
  /* 2026-10-09: the stats/log panel is no longer a pop-up in portrait. It sits inline under 16:9 videos (mobile.css),
     so it never covers the players (a covered Twitch embed pauses itself). Landscape keeps it as a pop-up. */
  const panels=[document.getElementById('mobile-options'),document.getElementById('mhelp-panel')];
  if(matchMedia('(max-height:520px)').matches)panels.push(multi.querySelector('.mlog'));
  function sync(){
    const active=!multi.hidden&&multi.classList.contains('focus');
    panels.forEach(panel=>{
      if(!panel)return;
      if(!active){if(panel.matches(':popover-open'))panel.hidePopover();if(panel.hasAttribute('popover'))panel.removeAttribute('popover');if(panel.classList.contains('mobile-player-panel'))panel.classList.remove('mobile-player-panel');return}
      if(!panel.hasAttribute('popover'))panel.setAttribute('popover','manual');
      if(!panel.classList.contains('mobile-player-panel'))panel.classList.add('mobile-player-panel');
      const wanted=panel.classList.contains('mlog')?(!multi.classList.contains('nolog')||!!panel.querySelector('.multi-moments[open]')):!panel.hidden;
      if(wanted&&!panel.matches(':popover-open'))panel.showPopover();
      else if(!wanted&&panel.matches(':popover-open'))panel.hidePopover();
    });
  }
  multi._mobilePanels=new MutationObserver(sync);
  multi._mobilePanels.observe(multi,{subtree:true,attributes:true,attributeFilter:['hidden','class','open']});
  sync();
};
const Base=window.Twitch&&window.Twitch.Player,build=Base&&Base.prototype.buildIframe;
// Multistream uses the same unrestricted Twitch iframe as the isolated test.
// Keep the official SDK bridge for explicit controls, without the legacy wrapper.
if(build)window.ClutchMobileEmbed.Player=class extends Base{
  constructor(id,options){
    const surface=document.getElementById(id),slot=surface.parentElement;
    // Keep the layout slot in the grid, but create the actual browsing context
    // at the document root. Never reparent a live iframe: that reloads Twitch.
    surface.className='mobile-player-surface';
    surface.style.cssText='';
    const position=()=>{const r=slot.getBoundingClientRect();surface.hidden=!slot.isConnected||!r.width||!r.height;Object.assign(surface.style,{left:r.x+'px',top:r.y+'px',width:r.width+'px',height:r.height+'px'})};
    document.body.appendChild(surface);position();
    try{super(id,options)}catch(error){surface.remove();throw error}
    this._surface=surface;this._position=position;
    this._slotObserver=new ResizeObserver(position);this._slotObserver.observe(slot);
    window.addEventListener('resize',position);window.addEventListener('scroll',position,true);
  }
  destroy(){
    if(this._surfaceDestroyed)return;this._surfaceDestroyed=true;
    this._slotObserver.disconnect();window.removeEventListener('resize',this._position);window.removeEventListener('scroll',this._position,true);
    super.destroy();this._surface.remove();
  }
  buildIframe(){const o=this._options,frame=document.createElement('iframe'),params=new URLSearchParams({video:o.video,time:o.time||'0h0m0s',parent:location.hostname,autoplay:String(o.autoplay!==false),muted:'true'});frame.src='https://player.twitch.tv/?'+params;frame.allow='autoplay; fullscreen';frame.allowFullscreen=true;frame.title='Twitch replay';frame.style.cssText='width:100%;height:100%;border:0';frame.dataset.playbackMode='plain';return frame}
  isArchive(){return false}
};
if(build){Base.prototype.buildIframe=function(){return protect(build.call(this))}}
})();
