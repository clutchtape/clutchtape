/* Local SVG charts: no third-party scripts, telemetry or external data requests. */
(function(){'use strict';
const payload=document.getElementById('analysis-data');if(!payload)return;
const data=JSON.parse(payload.textContent),ns='http://www.w3.org/2000/svg';
const $=(s,p=document)=>p.querySelector(s);
function node(tag,text,cls){const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;}
function svg(tag,attrs){const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));return e;}
const num=v=>v==null?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:2});const numK=(k,v)=>k==='kda'&&v!=null&&v!==''?Number(v).toFixed(1):num(v);
const date=t=>new Date(t*1000).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
const form=$('#analysis-filters');
if(innerWidth<=760)$('.filter-panel').open=false;
function period(){form.elements.session.disabled=form.elements.scope.value!=='session';}
form.elements.scope.addEventListener('change',period);period();
['kind','playlist'].forEach(k=>form.elements[k].addEventListener('change',()=>{form.elements.session.value='';}));
form.addEventListener('submit',()=>{form.action=location.pathname+location.hash;});
const views={games:'games',analysis:'analysis',progress:'analysis','map-modes':'analysis',objectives:'analysis',expectations:'analysis','squad-contributions':'analysis',replay:'replay',review:'replay',recap:'replay',notes:'replay'};
function view(){/* 2026-10-09: one scrolling page, no sub-views */document.querySelectorAll('[data-view],[data-views]').forEach(e=>e.hidden=false);document.querySelectorAll('[data-tab]').forEach(e=>{e.classList.toggle('active',e.dataset.tab===active);if(e.dataset.tab===active)e.setAttribute('aria-current','page');else e.removeAttribute('aria-current');});}
addEventListener('hashchange',view);view();
function table(host,headers,rows){host.replaceChildren();const t=node('table'),thead=node('thead'),tr=node('tr'),body=node('tbody');headers.forEach(h=>tr.append(node('th',h)));thead.append(tr);rows.forEach(r=>{const row=node('tr');r.forEach(c=>{const td=node('td');if(c&&typeof c==='object'){const a=node('a',c.label);a.href=c.url;td.append(a);}else td.textContent=c;row.append(td);});body.append(row);});t.append(thead,body);host.append(t);}
let statGroup='key',gamePage=0;
const countMode=$('#stat-counts'),gameRows=data.series.flatMap(s=>s.points.map(p=>({...p,player:s.name}))).sort((a,b)=>b.at-a.at||a.player.localeCompare(b.player));
function included(m){return statGroup==='all'||(statGroup==='key'?m.key_stat:m.group===statGroup);}
function renderGames(){const cols=data.metrics.filter(included),rows=gameRows.slice(gamePage*12,gamePage*12+12);table($('#game-stats-table'),['Game','Player','Result',...cols.map(m=>m.short)],rows.map(r=>[{label:date(r.at)+' · '+r.label,url:r.url},r.player,r.outcome==='Dnf'?'DNF':r.outcome,...cols.map(m=>numK(m.key,r.values[m.key])+(r.values[m.key]!=null?m.unit:''))]));$('#games-page').textContent=gameRows.length?`${gamePage*12+1}–${Math.min(gameRows.length,(gamePage+1)*12)} / ${gameRows.length} player-games`:'No games';$('#games-prev').disabled=gamePage===0;$('#games-next').disabled=(gamePage+1)*12>=gameRows.length;}
function statFilter(){document.querySelectorAll('[data-stat-group]').forEach(e=>e.hidden=!(statGroup==='all'||(statGroup==='key'?e.dataset.keyStat==='1':e.dataset.statGroup===statGroup)));document.querySelectorAll('[data-stat-filter]').forEach(e=>e.setAttribute('aria-pressed',String(e.dataset.statFilter===statGroup)));renderGames();}
function counts(){const total=countMode.value==='total';document.querySelectorAll('[data-stat-value]').forEach(e=>{const v=total&&e.dataset.statTotal!==''?e.dataset.statTotal:e.dataset.statValue;e.textContent=v===''?'—':(e.dataset.dec?Number(v).toFixed(1):num(Number(v)))+(e.dataset.unit||'');});document.querySelectorAll('[data-delta-average]').forEach(e=>{const v=total&&e.dataset.deltaTotal!==''?e.dataset.deltaTotal:e.dataset.deltaAverage;e.textContent=v===''?'—':(Number(v)>0?'+':'')+num(Number(v))+(e.dataset.deltaUnit||'');});document.querySelectorAll('[data-metric-label]').forEach(e=>e.textContent=total&&e.dataset.hasTotal==='1'?e.dataset.metricLabel.replace(' / game',' total'):e.dataset.metricLabel);}
document.querySelectorAll('[data-stat-filter]').forEach(e=>e.addEventListener('click',()=>{statGroup=e.dataset.statFilter;statFilter();}));countMode.addEventListener('change',counts);$('#games-prev').addEventListener('click',()=>{gamePage=Math.max(0,gamePage-1);renderGames();});$('#games-next').addEventListener('click',()=>{if((gamePage+1)*12<gameRows.length)gamePage++;renderGames();});statFilter();counts();
function initChart(card){const rank=card.dataset.chart==='rank',select=$('.chart-series',card),metric=$('.chart-metric',card),host=$('.chart-canvas',card),range=$('input[type=range]',card),readout=$('.chart-readout',card),link=$('.chart-link',card),source=rank?data.ranks:data.series;
source.forEach((s,i)=>select.append(new Option(s.name+(rank?' · '+s.playlist:''),String(i))));
function render(){host.replaceChildren();const s=source[Number(select.value)],key=rank?'rank':metric.value,unit=rank?' CSR':(data.metrics.find(m=>m.key===key)||{}).unit||'',all=s?s.points:[],pts=all.slice(-200),offset=all.length-pts.length;
const value=p=>rank?p.value:p.values[key],rolling=p=>rank?null:p.rolling[key];
const values=pts.flatMap(p=>[value(p),rolling(p)]).filter(v=>v!=null);
if(!values.length){host.append(node('p',rank?'No rated games in this selection. Choose a ranked playlist or a longer period.':'This metric is not available for these games yet.','chart-empty'));range.disabled=true;link.hidden=true;readout.textContent='';if($('.chart-caption',card))$('.chart-caption',card).textContent='';table($('.chart-table',card),['Game','Value'],[]);return;}
range.disabled=false;range.max=String(pts.length-1);range.value=String(pts.length-1);
const W=Math.min(760,Math.max(280,host.clientWidth)),H=260,L=52,R=16,T=24,B=40;
let low=Math.min(...values),high=Math.max(...values);if(low===high){low-=Math.max(1,Math.abs(low)*.05);high+=Math.max(1,Math.abs(high)*.05);}const pad=(high-low)*.12;low-=pad;high+=pad;if(rank||!['kda','dmg_diff'].includes(key))low=Math.max(0,low);
const x=i=>L+(pts.length===1?(W-L-R)/2:i*(W-L-R)/(pts.length-1)),y=v=>T+(high-v)/(high-low)*(H-T-B);
const chart=svg('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':rank?'CSR by match. Use the game slider or chart data table to inspect.':'Performance by match. Solid line is each game; dashed line is a trailing five-game average.'});
for(let i=0;i<=4;i++){let v=low+(high-low)*i/4;chart.append(svg('line',{x1:L,x2:W-R,y1:y(v),y2:y(v),class:'chart-gridline'}));const label=svg('text',{x:L-8,y:y(v)+4,'text-anchor':'end',class:'chart-axis'});label.textContent=num(rank||['dmg_pm','dmg_dealt','dmg_taken','dmg_ka','dmg_diff','dmg_death'].includes(key)?Math.round(v):v);chart.append(label);}
function path(get,cls){let d='',open=false;pts.forEach((p,i)=>{const v=get(p);if(v==null){open=false;return;}d+=(open?'L':'M')+x(i)+' '+y(v)+' ';open=true;});chart.append(svg('path',{d,class:cls,fill:'none'}));}
path(value,'chart-line');if(!rank)path(rolling,'chart-average');
pts.forEach((p,i)=>{if(value(p)!=null)chart.append(svg('circle',{cx:x(i),cy:y(value(p)),r:pts.length>70?2:4,class:p.outcome==='Dnf'||p.outcome==='Left'?'chart-point partial':'chart-point'}));});
const cursor=svg('line',{x1:0,x2:0,y1:T,y2:H-B,class:'chart-cursor'});chart.append(cursor);
[0,pts.length-1].filter((v,i,a)=>a.indexOf(v)===i).forEach(i=>{const label=svg('text',{x:x(i),y:H-12,'text-anchor':i?'end':'start',class:'chart-axis'});label.textContent=new Date(pts[i].at*1000).toLocaleDateString(undefined,{month:'short',day:'numeric'});chart.append(label);});host.append(chart);
function inspect(){const i=Number(range.value),p=pts[i],v=value(p);cursor.setAttribute('x1',x(i));cursor.setAttribute('x2',x(i));readout.textContent=`Game ${offset+i+1} · ${date(p.at)} · ${p.label} · ${p.outcome==='Dnf'?'Did not finish':p.outcome} · ${num(v)}${unit}`+(rank?' · '+(p.value-p.pre>=0?'+':'')+num(p.value-p.pre)+' CSR':` · rolling ${num(rolling(p))}${unit}`);link.href=p.url;link.hidden=false;}
range.oninput=inspect;chart.addEventListener('pointerdown',e=>{const rect=chart.getBoundingClientRect(),px=(e.clientX-rect.left)*W/rect.width;range.value=String(Math.max(0,Math.min(pts.length-1,Math.round((px-L)/(W-L-R)*(pts.length-1)))));inspect();});inspect();
if(rank)$('.chart-caption',card).textContent=`${s.current} current · ${s.delta>=0?'+':''}${s.delta} CSR · ${s.peak} peak in selection · ${all.length} rated games`+(offset?' · chart shows newest 200':'');
else if(offset)readout.textContent+=' · chart shows newest 200 games';
table($('.chart-table',card),['Game','Result',rank?'CSR':'Value',rank?'Change':'Rolling average'],pts.map((p,i)=>[{label:`${offset+i+1} · ${date(p.at)} · ${p.label}`,url:p.url},p.outcome,num(value(p))+unit,rank?num(p.value-p.pre):num(rolling(p))+unit]));
}select.addEventListener('change',render);if(metric)metric.addEventListener('change',render);render();let width=host.clientWidth;new ResizeObserver(()=>{if(host.clientWidth>0&&host.clientWidth!==width){width=host.clientWidth;render();}}).observe(host);}
document.querySelectorAll('[data-chart]').forEach(initChart);
function bars(host,rows,signed=false){host.replaceChildren();const valid=rows.filter(r=>r.value!=null);if(!valid.length){host.append(node('p','No reported data for this selection. Try a different period or metric.','chart-empty'));return;}const max=Math.max(1,...valid.map(r=>Math.abs(r.value)));rows.forEach(r=>{const row=node('div',null,'bar-row'),label=node(r.url?'a':'span',r.label,'bar-label');if(r.url)label.href=r.url;const track=node('div',null,'bar-track'+(signed?' signed':'')),fill=node('i',null,r.value<0?'negative':'positive');if(r.value!=null){fill.style.width=(Math.abs(r.value)/max*(signed?50:100))+'%';if(signed)fill.style.left=(r.value<0?50-Math.abs(r.value)/max*50:50)+'%';track.append(fill);}row.append(label,track,node('b',(signed&&r.value>0?'+':'')+num(r.value)+(r.unit||'')));host.append(row);});}
if($('[data-bars=expectation]')){   /* section removed 2026-10-09 (duplicated the xK± column) */
const expected=$('[data-bars=expectation]');
let expectationPlayer=node('select');expectationPlayer.setAttribute('aria-label','Expected performance player');data.players.forEach(p=>expectationPlayer.append(new Option(p.name,p.name)));
let expectedMetric=node('select');expectedMetric.setAttribute('aria-label','Expected performance metric');expectedMetric.append(new Option('Kills above / below expected','kills'),new Option('Deaths above / below expected','deaths'));
const ef=node('div',null,'expectation-controls');ef.append(expectationPlayer,expectedMetric);expected.before(ef);
function expectation(){const key=expectedMetric.value,rows=data.expectation.filter(e=>e.name===expectationPlayer.value).slice(-30);bars(expected,rows.map(e=>({label:date(e.at)+' · '+e.map,url:e.url,value:e['expected_'+key]==null?null:e[key]-e['expected_'+key]})),true);if(rows.length)expected.prepend(node('p','Newest '+rows.length+' games with reported expectations.','fine'));}
expectationPlayer.addEventListener('change',expectation);expectedMetric.addEventListener('change',expectation);expectation();
}
const objective=$('#objective-metric'),objKeys=new Map(data.objectives.map(e=>[e.key,e.label]));objKeys.forEach((label,key)=>objective.append(new Option(label,key)));
function objectiveBars(){bars($('[data-bars=objectives]'),data.players.map(p=>{const e=data.objectives.find(e=>e.key===objective.value&&e.name===p.name);return {label:p.name+' · '+(e?e.games:0)+' reported games',value:e?e.value:null,unit:e?e.unit:''};}));}objective.addEventListener('change',objectiveBars);objectiveBars();
const squad=$('#squad-metric');if(squad){function squadBars(){bars($('[data-bars=squad]'),data.bars.map(e=>({label:e.name+' · '+e.games+' games',value:e[squad.value],unit:squad.value==='damage_share'?'%':''})));}squad.addEventListener('change',squadBars);squadBars();}
})();
