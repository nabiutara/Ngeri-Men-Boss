'use strict';
var PlayerConnections = (() => {
  const validId = id => Number.isInteger(id) && id >= 0;
  function bindings(input) {
    if (!Array.isArray(input)) return [];
    const byTime = new Map();
    for (const b of input.slice(0,500)) {
      if (b && validId(b.id) && Number.isFinite(b.t) && b.t >= 0 && b.t <= 14400) byTime.set(b.t,{t:b.t,id:b.id});
    }
    return [...byTime.values()].sort((a,b)=>a.t-b.t);
  }
  function sanitize(input) {
    if (!Array.isArray(input)) return [];
    return input.slice(0,500).filter(c=>c&&validId(c.a)&&validId(c.b)&&c.a!==c.b&&(c.scene==='demo'||Number.isInteger(c.scene)&&c.scene>=0)).map(c=>({a:c.a,b:c.b,scene:c.scene,color:/^#[0-9a-f]{6}$/i.test(c.color)?c.color:'#eac56a',width:Math.max(1,Math.min(8,Number(c.width)||2)),aBindings:bindings(c.aBindings),bBindings:bindings(c.bBindings)}));
  }
  function endpoint(edge, side, time=0) {
    let id=edge[side];
    for (const binding of edge[side+'Bindings']||[]) {
      if (binding.t > time) break;
      id=binding.id;
    }
    return id;
  }
  function ids(connections,scene,time) {
    return new Set((connections||[]).filter(c=>c.scene===scene).flatMap(c=>[endpoint(c,'a',time),endpoint(c,'b',time)]));
  }
  function visible(connections, anchors, scene, time=0) {
    return (connections||[]).filter(c=>c.scene===scene).map(c=>({...c,a:endpoint(c,'a',time),b:endpoint(c,'b',time)}))
      .filter(c=>c.a!==c.b&&anchors.has(c.a)&&anchors.has(c.b))
      .map(c=>({...c,from:anchors.get(c.a),to:anchors.get(c.b)}));
  }
  function reattach(connections,scene,oldId,newId,time) {
    if (!validId(oldId)||!validId(newId)||oldId===newId||!Number.isFinite(time)||time<0||time>14400) throw Error('Choose two different player tracks at a valid video time.');
    let changed=0;
    const result=(connections||[]).map(edge=>{
      if(edge.scene!==scene)return edge;
      const a=endpoint(edge,'a',time),b=endpoint(edge,'b',time);
      if(a!==oldId&&b!==oldId)return edge;
      if((a===oldId&&b===newId)||(b===oldId&&a===newId)) throw Error('That player is already the other end of a connection. Choose the replacement player.');
      const next={...edge};
      for(const side of ['a','b'])if(endpoint(edge,side,time)===oldId){
        // Preserve earlier playback; this correction supersedes later bindings for this endpoint.
        const history=(edge[side+'Bindings']||[]).filter(b=>b.t<time);
        if(history.length>=500)throw Error('This connection has too many corrections. Create a new connection.');
        next[side+'Bindings']=[...history,{t:time,id:newId}];changed++;
      }
      return next;
    });
    if(!changed)throw Error('That track has no connections in this camera scene.');
    return result;
  }
  function bridge(frames,index,time,players,wanted,maxGap=.6) {
    if(!wanted.size||index<0||!frames[index])return players;
    const scene=frames[index].camera?.scene, left=new Map(),right=new Map();
    // Bounded lookaround, no history of playback: seeking gives the same result.
    for(let i=index;i>=0&&time-frames[i].t<=maxGap;i--){
      const f=frames[i];if(f.camera?.scene!==scene)break;
      for(const p of f.players)if(wanted.has(p.id)&&!left.has(p.id))left.set(p.id,{p,t:f.t,i});
      if(left.size===wanted.size)break;
    }
    for(let i=index+1;i<frames.length&&frames[i].t-time<=maxGap;i++){
      const f=frames[i];if(f.camera?.scene!==scene)break;
      for(const p of f.players)if(wanted.has(p.id)&&!right.has(p.id))right.set(p.id,{p,t:f.t,i});
      if(right.size===wanted.size)break;
    }
    const result=new Map(players.map(p=>[p.id,p]));
    for(const id of wanted){
      const a=left.get(id),b=right.get(id);
      if(!a||!b||b.i-a.i<=1||b.t-a.t>maxGap||!(a.t<time&&time<b.t))continue;
      const p=a.p,q=b.p;
      if(p.role!==q.role||Math.abs(p.x-q.x)>Math.max(.03,3*Math.max(p.w,q.w))||Math.abs(p.y-q.y)>Math.max(.04,1.5*Math.max(p.h,q.h)))continue;
      if(Math.max(p.h,q.h)>2*Math.min(p.h,q.h)||Math.max(p.w,q.w)>2*Math.min(p.w,q.w))continue;
      const ratio=(time-a.t)/(b.t-a.t),sample={...p,connectionEstimate:true};
      for(const key of ['x','y','w','h'])sample[key]=p[key]+(q[key]-p[key])*ratio;
      result.set(id,sample);
    }
    return [...result.values()];
  }
  function geometry(from,to){
    const dx=to.x-from.x,dy=to.y-from.y,length=Math.hypot(dx,dy);
    if(!Number.isFinite(length)||length<1)return null;
    const ux=dx/length,uy=dy/length;
    const inset=p=>{const r=p.radius||0;return r?1/Math.sqrt((ux/r)**2+(uy/(r*.34))**2)+3:3;};
    const a=inset(from),b=inset(to);if(length<=a+b+2)return null;
    return {x1:from.x+ux*a,y1:from.y+2+uy*a,x2:to.x-ux*b,y2:to.y+2-uy*b,ux,uy,length:length-a-b};
  }
  function draw(ctx,edge,settings={}){
    const g=geometry(edge.from,edge.to);if(!g)return;
    const estimated=edge.from.estimated||edge.to.estimated;
    const style=settings.connectionStyle||'solid',width=edge.width||2;
    ctx.save();ctx.globalAlpha*=(settings.connectionOpacity??75)/100*(estimated?.55:1);ctx.lineCap='round';
    ctx.setLineDash(estimated?[6,4]:style==='dashed'?[9,5]:[]);
    ctx.beginPath();ctx.moveTo(g.x1,g.y1);ctx.lineTo(g.x2,g.y2);
    ctx.strokeStyle='#14271d';ctx.lineWidth=width+2;ctx.stroke();ctx.strokeStyle=edge.color;ctx.lineWidth=width;ctx.stroke();
    ctx.setLineDash([]);ctx.fillStyle=edge.color;
    if(style==='arrow'&&g.length>12){const size=Math.min(10,g.length*.3);ctx.beginPath();ctx.moveTo(g.x2,g.y2);ctx.lineTo(g.x2-g.ux*size-g.uy*size*.45,g.y2-g.uy*size+g.ux*size*.45);ctx.lineTo(g.x2-g.ux*size+g.uy*size*.45,g.y2-g.uy*size-g.ux*size*.45);ctx.closePath();ctx.fill();}
    if(settings.connectionDots!==false){for(const [x,y] of [[g.x1,g.y1],[g.x2,g.y2]]){ctx.beginPath();ctx.arc(x,y,Math.max(2,width),0,Math.PI*2);ctx.fill();}}
    ctx.restore();
  }
  return {sanitize,visible,endpoint,ids,reattach,bridge,geometry,draw};
})();
