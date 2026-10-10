/* Stored match statistics and transparent derived rates. Missing data is never zero-filled. */
(function(root){
  var rows=[
    ['Score share','sc','%'],['Personal score','score'],['K / D / A','line',null,0],['KDA','kda'],['K / D ratio','kd'],['Kills','k'],['Deaths','d',null,-1],['Assists','a'],['Net kills','net'],
    ['Damage / min','dpm'],['Damage ±','dd'],['Accuracy','acc','%'],['Team damage','sh','%'],['Damage dealt','dmg'],['Damage taken','taken',null,0],['Damage / K+A','dka',null,0],['Damage ratio','damageRatio'],
    ['Average life','life','s'],['Headshot kills','hs','%'],['Headshots','headshots'],['Shots fired','fired',null,0],['Shots hit','hit'],['Shots missed','missed',null,0],['Shots / min','shotsPm',null,0],['Hits / min','hitsPm'],
    ['Kills / min','kpm'],['Deaths / min','dpmDeaths',null,-1],['Assists / min','apm'],['K+A / min','pressure'],['Score / min','scorePm'],['Damage / life','damageLife'],
    ['Expected kills','expected_kills',null,0],['Expected deaths','expected_deaths',null,0],['Kills vs expected','xk'],['Deaths avoided','xd'],['CSR change','csr'],
    ['Max killing spree','spree'],['Melee kills','melee_kills'],['Grenade kills','grenade_kills'],['Power weapon kills','power_weapon_kills'],['Vehicle destroys','vehicle_destroys'],
    ['Spawns','spawns',null,0],['Suicides','suicides',null,-1],['Betrayals','betrayals',null,-1],['Callouts','callouts',null,0],['Objective','obj',null,0],['Objectives done','objectives_completed'],['Rounds won','rounds_won'],['Rounds lost','rounds_lost',null,-1]
  ];
  function ratio(a,b){return a!=null&&b!=null&&b>0?a/b:null}
  function derive(p){var v=Object.assign({},p.extra||{},p),mins=p.seconds>0?p.seconds/60:null;
    v.line=[p.k,p.d,p.a].map(function(x){return x==null?'—':x}).join(' / ');
    v.kd=ratio(p.k,p.d);v.net=p.k!=null&&p.d!=null?p.k-p.d:null;
    v.kpm=ratio(p.k,mins);v.dpmDeaths=ratio(p.d,mins);v.apm=ratio(p.a,mins);v.pressure=ratio(p.k!=null&&p.a!=null?p.k+p.a:null,mins);
    v.scorePm=ratio(p.score,mins);v.shotsPm=ratio(p.fired,mins);v.hitsPm=ratio(p.hit,mins);v.damageRatio=ratio(p.dmg,p.taken);
    v.damageLife=ratio(p.dmg,p.d!=null?p.d+1:null);v.missed=p.fired!=null&&p.hit!=null?Math.max(0,p.fired-p.hit):null;return v;
  }
  function heat(value, values, direction){
    if(typeof value!=='number'||!Number.isFinite(value))return {kind:'',alpha:0};
    values=values.filter(function(v){return typeof v==='number'&&Number.isFinite(v)});
    var lo=Math.min.apply(null,values),hi=Math.max.apply(null,values),p=hi===lo?.5:(value-lo)/(hi-lo);
    return {kind:hi===lo?'equal':direction===0?'magnitude':(p-.5)*(direction==null?1:direction)>=0?'good':'bad',alpha:hi===lo?.14:direction===0?.10+.32*p:.12+.24*Math.abs(2*p-1)};
  }
  root.ClutchStats={rows:rows,derive:derive,heat:heat};
})(typeof window==='undefined'?globalThis:window);
