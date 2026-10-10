/* Keep video and timeline in the available screen space. */
(()=>{const player=document.getElementById('player');if(!player)return;let queued=false;
function fit(){queued=false;if(document.fullscreenElement||!player.getClientRects().length)return;
const header=document.querySelector('.top'),bar=document.querySelector('.mediasec[open]>.mediabar');
const anchor=(header?.getBoundingClientRect().height||0)+(bar?.getBoundingClientRect().height||0)+8;
const viewport=window.visualViewport?.height||innerHeight,top=player.getBoundingClientRect().top;
const start=top>=anchor&&top<viewport-360?top:anchor;
const embed=player.querySelector('.embed'),width=embed?.clientWidth||player.clientWidth;
const want=Math.round(width*9/16)+44+16+160+26;
player.style.setProperty('--watch-height',Math.min(want,Math.max(260,viewport-start-10))+'px');
player.style.setProperty('--timeline-height','160px');player.style.scrollMarginTop=anchor+'px';}
function schedule(){if(!queued){queued=true;requestAnimationFrame(fit)}}
addEventListener('resize',fit);addEventListener('load',schedule);window.visualViewport?.addEventListener('resize',schedule);document.addEventListener('fullscreenchange',schedule);
if(window.ResizeObserver){const ro=new ResizeObserver(schedule);document.querySelectorAll('.top,.phead,.kinds,.sync,.mediabar').forEach(e=>ro.observe(e))}fit();
})();
