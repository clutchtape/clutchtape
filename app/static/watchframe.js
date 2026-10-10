/* Keep video and timeline in the available screen space. */
(()=>{const player=document.getElementById('player');if(!player)return;let queued=false;
function fit(){queued=false;if(document.fullscreenElement||!player.getClientRects().length)return;
const header=document.querySelector('.top'),bar=document.querySelector('.mediasec[open]>.mediabar');
const anchor=(header?.getBoundingClientRect().height||0)+(bar?.getBoundingClientRect().height||0)+8;
const viewport=window.visualViewport?.height||innerHeight;
const embed=player.querySelector('.embed'),width=embed?.clientWidth||player.clientWidth;
const live=player.classList.contains('is-live'),tl=live?0:160;   /* live: no event log under the video (2026-10-10) */
const want=Math.round(width*9/16)+(live?0:44+16)+tl+26;   /* live: no title row either */
/* 2026-10-10 (live): the whole video shows on first load without scrolling — fit the screen from where the player sits on
   the page. Only when that would leave less than half the video (phones, where the width sets the size) is it sized
   to the screen below the site header, and on load the page scrolls there by itself (live only, see below). */
const docTop=player.getBoundingClientRect().top+scrollY,fromTop=viewport-docTop-10,fromAnchor=viewport-anchor-10;
const avail=live&&fromTop>=want*0.5?fromTop:fromAnchor;   /* not live: the section opens on demand and the page scrolls to it */
player.style.setProperty('--watch-height',Math.min(want,Math.max(260,avail))+'px');
player.style.setProperty('--timeline-height',tl+'px');player.style.scrollMarginTop=anchor+'px';}
function schedule(){if(!queued){queued=true;requestAnimationFrame(fit)}}
addEventListener('resize',fit);addEventListener('load',schedule);window.visualViewport?.addEventListener('resize',schedule);document.addEventListener('fullscreenchange',schedule);
/* live on a phone: bring the whole video into view once on load (the header, names and tabs above it fill the screen) */
let jumped=false;function jump(){if(jumped||!player.classList.contains('is-live')||scrollY>0)return;jumped=true;const r=player.getBoundingClientRect();
if(r.bottom>(window.visualViewport?.height||innerHeight)){const bar=document.querySelector('.mediasec[open]>.mediabar')||player;const hdr=document.querySelector('.top')?.getBoundingClientRect().height||0;
window.scrollTo({top:bar.getBoundingClientRect().top+scrollY-hdr-4,behavior:'instant'})}}
addEventListener('load',()=>requestAnimationFrame(()=>requestAnimationFrame(jump)));
if(window.ResizeObserver){const ro=new ResizeObserver(schedule);document.querySelectorAll('.top,.phead,.kinds,.sync,.mediabar').forEach(e=>ro.observe(e))}fit();
})();
