(function(){
  const root=document.querySelector('.match-page');if(!root||root.dataset.ready==='true')return;
  const status=document.getElementById('match-status'),button=document.getElementById('match-retry');let attempts=0,busy=false;
  async function check(){if(busy)return;busy=true;button.disabled=true;try{
    const r=await fetch('/api/match/'+root.dataset.mid+'/detail',{cache:'no-store'});if(!r.ok)throw Error();const d=await r.json();
    if(d.state==='ready'){location.reload();return;}
    status.textContent=d.state==='error'?'Halo could not return the full scoreboard. Your saved stats are still here. Try again in a minute.':d.state==='busy'?'Other matches are being loaded. Try again shortly.':'Loading the full roster and stats… You can explore the saved events below while Halo responds.';
    if(d.state==='loading'&&++attempts<40)setTimeout(check,5000);
  }catch(e){status.textContent='Could not check the scoreboard. Your saved stats are still available. Try again.';}finally{busy=false;button.disabled=false;}}
  button.addEventListener('click',()=>{attempts=0;check();});setTimeout(check,3000);
})();
