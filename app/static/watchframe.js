/* Keep video and timeline in the available screen space. */
(()=>{const player=document.getElementById('player');if(!player)return;let queued=false;
function fit(){queued=false;
/* stats-only live mode: no player, so no fixed video-width column either */
if(document.documentElement.classList.contains('statsonly')){player.closest('.cols')?.style.removeProperty('grid-template-columns');return;}
if(document.fullscreenElement||!player.getClientRects().length)return;
const header=document.querySelector('.top'),bar=document.querySelector('.mediasec[open]>.mediabar');
const anchor=(header?.getBoundingClientRect().height||0)+(bar?.getBoundingClientRect().height||0)+8;
const viewport=window.visualViewport?.height||innerHeight;
const embed=player.querySelector('.embed'),width=embed?.clientWidth||player.clientWidth;
const live=player.classList.contains('is-live'),tl=live?0:160;   /* live: no event log under the video (2026-10-10) */
const cols=player.closest('.cols'),two=live&&innerWidth>=1200&&cols,padX=player.offsetWidth-(embed?.clientWidth||player.clientWidth),
  gap=cols?parseFloat(getComputedStyle(cols).columnGap)||16:16,maxW=two?cols.clientWidth-380-gap-padX:width;
/* live two-column: size from the widest the video could be (the column then shrinks to fit it), never from its
   current width, or narrowing the column would shrink the target again on the next pass */
const want=Math.round(maxW*9/16)+(live?0:44+16)+tl+26;   /* live: no title row either */
/* 2026-10-10 (live): the whole video shows on first load without scrolling — fit the screen from where the player sits on
   the page. Only when that would leave less than half the video (phones, where the width sets the size) is it sized
   to the screen below the site header, and on load the page scrolls there by itself (live only, see below). */
/* live, side-by-side layout: leave room under the video for the session-vs-usual table (#livevs) so both are on screen */
const vs=live&&innerWidth>=1200?document.getElementById('livevs'):null,below=vs?vs.offsetHeight+12+8:0;   /* gap above + a little air below */
const docTop=player.getBoundingClientRect().top+scrollY,fromTop=viewport-docTop-10-below,fromAnchor=viewport-anchor-10-below;
let avail=live&&fromTop>=want*0.5?fromTop:fromAnchor;   /* not live: the section opens on demand and the page scrolls to it */
/* the table always stays in frame with the video (2026-10-10): the video gives way instead */
player.style.setProperty('--watch-height',Math.min(want,Math.max(260,avail))+'px');
player.style.setProperty('--timeline-height',tl+'px');
/* live, two columns: the left column is exactly as wide as the 16:9 video at that height (no black bars beside it);
   the space left over goes to the right column (live stats + chat) */
if(cols){if(two){const h=Math.min(want,Math.max(260,avail))-26,mainW=Math.round(Math.min(h*16/9,maxW)+padX);
  cols.style.setProperty('grid-template-columns',mainW+'px minmax(380px,1fr)','important');}else cols.style.removeProperty('grid-template-columns');}   /* the .cols.video-layout rules are !important */player.style.scrollMarginTop=anchor+'px';}
function schedule(){if(!queued){queued=true;requestAnimationFrame(fit)}}
addEventListener('resize',fit);addEventListener('load',schedule);window.visualViewport?.addEventListener('resize',schedule);document.addEventListener('fullscreenchange',schedule);
/* live on a phone: bring the whole video into view once on load (the header, names and tabs above it fill the screen) */
let jumped=false;function jump(){if(jumped||!player.classList.contains('is-live')||scrollY>0)return;jumped=true;const r=player.getBoundingClientRect();
if(r.bottom>(window.visualViewport?.height||innerHeight)){const bar=document.querySelector('.mediasec[open]>.mediabar')||player;const hdr=document.querySelector('.top')?.getBoundingClientRect().height||0;
window.scrollTo({top:bar.getBoundingClientRect().top+scrollY-hdr-4,behavior:'instant'})}}
addEventListener('load',()=>requestAnimationFrame(()=>requestAnimationFrame(jump)));
if(window.ResizeObserver){const ro=new ResizeObserver(schedule);document.querySelectorAll('.top,.phead,.kinds,.sync,.mediabar,#livevs').forEach(e=>ro.observe(e));
  /* live.js swaps #livevs on every new game: re-fit and watch the new one */
  if(player.parentElement)new MutationObserver(()=>{const v=document.getElementById('livevs');if(v)ro.observe(v);schedule()}).observe(player.parentElement,{childList:true})}fit();
})();
