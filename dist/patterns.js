'use strict';
// Original Touchline implementation inspired by Codeball's configurable patterns.
// No Codeball code, runtime dependency, or physical pitch measurements are used.
var TacticalPatterns = (() => {
  const defaults = {name:'Zone visits',team:'all',trackId:null,x1:0.5,y1:0,x2:1,y2:1,minSeconds:0};
  function validate(value) {
    const p={...defaults,...value};
    if (!['all','home','away','track'].includes(p.team) ||
        !['x1','y1','x2','y2'].every(k=>Number.isFinite(p[k])&&p[k]>=0&&p[k]<=1) ||
        p.x1>=p.x2 || p.y1>=p.y2 || !Number.isFinite(p.minSeconds) || p.minSeconds<0 || p.minSeconds>14400 ||
        (p.team==='track'&&(!Number.isInteger(p.trackId)||p.trackId<0))) throw Error('Choose a valid zone, player filter, and minimum duration.');
    return {name:String(p.name||defaults.name).slice(0,80),team:p.team,trackId:p.team==='track'?p.trackId:null,
      x1:p.x1,y1:p.y1,x2:p.x2,y2:p.y2,minSeconds:p.minSeconds};
  }
  function sanitize(value) {try{return validate(value);}catch{return {...defaults};}}
  // Adjacent observed samples only. Never interpolate a missing player or camera.
  // A first sighting inside is a visit, not evidence of an entry.
  function* scan({frames,pattern,project,players=f=>f.players,info=p=>p,maxGap=.5,limit=2000}) {
    const config=validate(pattern),events=[],previous=new Map(),active=new Map();
    let skippedFrames=0,projectedSamples=0,truncated=false;
    function finish(id,reason) {
      const event=active.get(id);active.delete(id);
      if(event&&event.seconds+1e-9>=config.minSeconds){
        if(events.length<limit)events.push({...event,endReason:reason});else truncated=true;
      }
    }
    for(let i=0;i<frames.length;i++){
      const f=frames[i],seen=new Set();let mapped=0;
      for(const p of players(f)){
        const detail=info(p);
        if(p.role==='referee'||detail.team==='hidden'||(config.team==='track'&&p.id!==config.trackId)||
          (['home','away'].includes(config.team)&&detail.team!==config.team))continue;
        const q=project(p,f,detail);
        if(!q||![q.x,q.y].every(Number.isFinite)||q.x<0||q.x>1||q.y<0||q.y>1)continue;
        mapped++;projectedSamples++;seen.add(p.id);
        const old=previous.get(p.id),continuous=old&&old.index===i-1&&f.t>old.t&&f.t-old.t<=maxGap&&old.scene===f.camera?.scene;
        if(!continuous)finish(p.id,'Observation gap or scene boundary');
        const inside=q.x>=config.x1&&q.x<=config.x2&&q.y>=config.y1&&q.y<=config.y2;
        if(inside){
          if(!active.has(p.id))active.set(p.id,{trackId:p.id,label:detail.name||`Track ${p.id}`,team:detail.team||'neutral',
            start:f.t,end:f.t,seconds:0,samples:1,entry:!!continuous&&!old.inside,
            entryAfter:continuous&&!old.inside?old.t:null,scene:f.camera?.scene});
          else {const e=active.get(p.id);e.seconds+=f.t-e.end;e.end=f.t;e.samples++;}
        }else finish(p.id,'Observed outside zone');
        previous.set(p.id,{index:i,t:f.t,inside,scene:f.camera?.scene});
      }
      for(const id of active.keys())if(!seen.has(id))finish(id,'Missing player or unusable projection');
      // Keep working memory bounded by the current frame's identities.
      for(const id of previous.keys())if(!seen.has(id))previous.delete(id);
      if(!mapped)skippedFrames++;
      if(i%500===0)yield {processed:i+1,total:frames.length};
    }
    for(const id of active.keys())finish(id,'End of tracking');
    events.sort((a,b)=>a.start-b.start||a.trackId-b.trackId);
    return {events,skippedFrames,projectedSamples,truncated,frames:frames.length,pattern:config};
  }
  return {defaults,validate,sanitize,scan};
})();
if(typeof module!=='undefined')module.exports=TacticalPatterns;
