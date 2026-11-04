const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const box={};vm.createContext(box);vm.runInContext(fs.readFileSync(path.join(__dirname,'../dist/player-connections.js'),'utf8'),box);
const c=box.PlayerConnections;
const edges=c.sanitize([{a:1,b:2,scene:0,color:'#ff8800',width:3},{a:2,b:3,scene:0,color:'#ff8800',width:3},{a:1,b:1,scene:0},null]);
assert.equal(edges.length,2);
let points=new Map([[1,{x:100,y:80}],[2,{x:200,y:50}],[3,{x:300,y:30}]]);
let visible=c.visible(edges,points,0);assert.equal(visible[0].from.x,100);assert.equal(visible[1].to.x,300);
// Players cross vertical positions without changing A-B / B-C arrangement.
points=new Map([[1,{x:120,y:20}],[2,{x:250,y:100}],[3,{x:330,y:70}]]);
visible=c.visible(edges,points,0);assert.equal(visible[0].a,1);assert.equal(visible[0].b,2);assert.equal(visible[0].to.x,250);
points.delete(2);assert.equal(c.visible(edges,points,0).length,0,'Do not bridge across missing players');
assert.equal(c.visible(edges,new Map([[1,{}],[2,{}],[3,{}]]),1).length,0,'No lines across camera cuts');
assert.equal(c.sanitize(JSON.parse(JSON.stringify(edges))).length,2);
// Reattach a lost player once: preserve all incident edges and earlier playback.
const repaired=c.reattach(edges,0,2,12,5);
const newPoints=new Map([[1,{x:10}],[2,{x:20}],[3,{x:30}],[12,{x:120}],[22,{x:220}]]);
assert.equal(c.visible(repaired,newPoints,0,4.99)[0].b,2);
assert.equal(c.visible(repaired,newPoints,0,5)[0].b,12);
assert.equal(c.visible(repaired,newPoints,0,5)[1].a,12);
assert.equal(c.visible(repaired,newPoints,1,5).length,0);
assert.equal(edges[0].bBindings.length,0,'Repair must not mutate Undo history');
assert.equal(c.visible(c.sanitize(JSON.parse(JSON.stringify(repaired))),newPoints,0,6)[1].a,12,'Project round trip retains timed repairs');
const again=c.reattach(repaired,0,12,22,8);
assert.equal(c.visible(again,newPoints,0,6)[0].b,12);
assert.equal(c.visible(again,newPoints,0,9)[0].b,22);
assert.throws(()=>c.reattach(edges,0,2,1,5),/other end/,'Do not collapse lines onto their other endpoint');
assert.throws(()=>c.reattach(edges,1,2,12,5),/no connections/);
assert.throws(()=>c.reattach(edges,0,2,12,NaN));
const sanitized=c.sanitize([{...edges[0],aBindings:[{t:3,id:7},{t:1,id:6},{t:-1,id:4},{t:2,id:NaN},null]}]);
assert.equal(c.endpoint(sanitized[0],'a',2),6);
assert.equal(c.endpoint(sanitized[0],'a',4),7);

// Same-ID lookahead bridges brief dropouts, never a new identity or camera cut.
const p={id:1,x:.2,y:.7,w:.04,h:.12,role:'player'},q={...p,x:.26,y:.72};
const sample=(t,players,scene=0)=>({t,players,camera:{scene}});
const gapFrames=[sample(0,[p]),sample(.1,[]),sample(.2,[]),sample(.3,[q])];
const before=JSON.stringify(gapFrames),wanted=new Set([1]);
let bridged=c.bridge(gapFrames,1,.15,[],wanted);
assert.equal(bridged.length,1);assert.ok(Math.abs(bridged[0].x-.23)<1e-9);assert.equal(bridged[0].connectionEstimate,true);
assert.equal(JSON.stringify(gapFrames),before,'Presentation interpolation must not alter source detections');
assert.equal(c.bridge(gapFrames,1,.15,[],new Set([2])).length,0);
assert.equal(c.bridge([sample(0,[p]),sample(.2,[]),sample(.8,[q])],1,.25,[],wanted).length,0,'Long gaps stay hidden');
assert.equal(c.bridge([sample(0,[p]),sample(.1,[]),sample(.3,[{...q,id:2}])],1,.15,[],wanted).length,0,'Never guess a new ID');
assert.equal(c.bridge([sample(0,[p]),sample(.1,[],1),sample(.3,[q],1)],1,.15,[],wanted).length,0,'No interpolation across cuts');
assert.equal(c.bridge([sample(0,[p]),sample(.1,[]),sample(.3,[{...q,x:.9}])],1,.15,[],wanted).length,0,'Reject implausible position jumps');
assert.equal(c.bridge([sample(0,[p]),sample(.1,[])],1,.15,[],wanted).length,0,'No unbounded carry-forward without a later observation');
assert.equal(c.bridge([sample(0,[]),sample(.1,[]),sample(.3,[q])],1,.15,[],wanted).length,0,'Do not invent a player before their first observation');
assert.equal(c.bridge(gapFrames,1,.15,[],wanted)[0].x,bridged[0].x,'Backward seeks are deterministic');
// Exercise production pair/sequence creation, duplicate prevention and undo checkpoint.
const app=fs.readFileSync(path.join(__dirname,'../dist/app.js'),'utf8');
const controls={connectionMode:{value:'sequence'},drawColor:{value:'#ff8800'},drawWidth:{value:'3'},showConnections:{checked:false}};
Object.assign(box,{$:id=>controls[id]??={},state:{demo:false,connections:[],settings:{}},time:0,frameAt:()=>({camera:{scene:0}}),cleanColor:v=>v,clamp:(x,a,b)=>Math.max(a,Math.min(b,x)),toast:()=>{},autosave:()=>{},checkpoint:()=>{box.snapshots.push(JSON.stringify(box.state.connections));},snapshots:[]});
vm.runInContext(app.slice(app.indexOf('let connectionFrom=null;'),app.indexOf('function drawPlayerConnections')),box);
box.connectPlayer(1);box.connectPlayer(2);box.connectPlayer(3);assert.equal(box.state.connections.length,2);
controls.connectionMode.value='pairs';box.connectPlayer(1);box.connectPlayer(1);box.connectPlayer(2);assert.equal(box.state.connections.length,3,'Existing reverse pair not duplicated');
box.state.connections=JSON.parse(box.snapshots.at(-1));assert.equal(box.state.connections.length,2,'Undo snapshot restores previous arrangement');
// Test actual playback integration, including smooth approach to a dropout.
Object.assign(box,{frames:gapFrames,needsRelink:false,trackMeta:{fps:10,stride:1},state:{demo:false,connections:c.sanitize([{a:1,b:2,scene:0}])}});
vm.runInContext(app.slice(app.indexOf('function frameIndex('),app.indexOf('function contentRect(')),box);
assert.ok(Math.abs(box.playersAt(.15)[0].x-.23)<1e-9);
assert.ok(Math.abs(box.playersAt(.05)[0].x-.21)<1e-9);
assert.equal(box.playersAt(.3)[0].connectionEstimate,undefined,'Return to observed track when it reappears');
box.state.connections=[];assert.equal(box.playersAt(.15).length,0,'Only connected endpoints receive gap estimates');
// A pending click cannot create a connection across camera scenes.
box.state.connections=[];box.frameAt=()=>({camera:{scene:0}});
box.connectPlayer(1);box.frameAt=()=>({camera:{scene:1}});box.connectPlayer(12);
assert.equal(box.state.connections.length,0);
// Exercise the production repair controls and drawing, not just the core helper.
const element=()=>({value:'',dataset:{},textContent:'',children:[],replaceChildren(){this.children=[];},append(option){this.children.push(option);}});
box.recording=false;
controls.connectionOldTrack=element();controls.connectionStatus=element();controls.connectReattach=element();
let dashCalls=[];
Object.assign(box,{document:{createElement:element},state:{demo:false,connections:edges,players:{},settings:{showConnections:true}},time:5,selected:{type:'player',id:12},currentPlayers:[{...p,id:12}],setPlaying:()=>{},frameAt:()=>({camera:{scene:0}}),ctx:new Proxy({setLineDash:values=>dashCalls.push([...values])},{get:(target,key)=>target[key]||(()=>{})})});
vm.runInContext(app.slice(app.indexOf('function drawPlayerConnections('),app.indexOf("$('connectionOldTrack').addEventListener")),box);
box.refreshConnectionControls(new Map([[1,{x:10,y:10}],[3,{x:30,y:10}],[12,{x:20,y:20}]]),0);
assert.equal(controls.connectionOldTrack.value,'2','Offer missing endpoint for repair');
assert.equal(controls.connectReattach.disabled,false);
assert.match(controls.connectionStatus.textContent,/0 of 2/);
box.reattachSelectedConnections();
assert.equal(c.visible(box.state.connections,newPoints,0,5)[0].b,12);
assert.equal(c.visible(box.state.connections,newPoints,0,4)[0].b,2);
assert.equal(JSON.parse(box.snapshots.at(-1))[0].b,2,'Repair captures Undo state');
box.drawPlayerConnections(new Map([[1,{x:10,y:10}],[3,{x:30,y:10}],[12,{x:20,y:20,estimated:true}]]),0);
assert.ok(dashCalls.some(v=>v.join(',')==='6,4'),'Estimated edges are visibly dashed');
box.currentPlayers=[{...p,id:12,connectionEstimate:true}];
box.refreshConnectionControls(new Map([[12,{x:20,y:20,estimated:true}]]),0);
assert.equal(controls.connectReattach.disabled,true,'Cannot reattach to a guessed position');
// Decoded media time, including paused seek completion, is the overlay clock.
let callback,seeking;Object.assign(box,{video:{requestVideoFrameCallback:fn=>{callback=fn;},addEventListener:(name,fn)=>{if(name==='seeking')seeking=fn;},currentTime:2,duration:10,playbackRate:1.5},needsRelink:false,playing:true,lastPresentedAt:0,lastPresentedMediaTime:0,updateTime:()=>{}});
vm.runInContext(app.slice(app.indexOf('if(video.requestVideoFrameCallback){'),app.indexOf('let connectionFrom=null;')),box);
callback(100,{mediaTime:1.25});assert.equal(box.lastPresentedMediaTime,1.25);assert.ok(Math.abs(box.mediaTimeAt(116)-1.274)<1e-9,'Interpolate the media clock at display refresh between decoded frames');
box.video.playbackRate=1;assert.ok(Math.abs(box.mediaTimeAt(116)-1.266)<1e-9,'Respect playback speed');
seeking();assert.equal(box.lastPresentedAt,-Infinity);assert.equal(box.mediaTimeAt(200),2,'Fall back to the seek target until a decoded frame arrives');
console.log('PASS: chosen edges follow movement, missing/cut handling, pair/sequence editing, undo, serialization, decoded-frame clock and seeks.');
