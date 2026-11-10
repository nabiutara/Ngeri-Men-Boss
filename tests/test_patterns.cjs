const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const Patterns=require('../dist/patterns.js');
const camera={scene:0,to_reference:[1,0,0,0,1,0,0,0,1]};
const player=(x,id=1)=>({id,x,y:.5,w:.1,h:.2,team:'home',role:'player'});
const frame=(t,x,id=1)=>({t,camera,players:x===null?[]:[player(x,id)]});
function run(frames,extra={}){const scan=Patterns.scan({frames,pattern:Patterns.defaults,project:p=>p,...extra});let step;do{step=scan.next();}while(!step.done);return step.value;}
let result=run([frame(0,.4),frame(.1,.6),frame(.2,.7),frame(.3,.4)]);
assert.equal(result.events.length,1);assert.equal(result.events[0].entry,true);
assert.equal(result.events[0].entryAfter,0);assert.equal(result.events[0].start,.1);assert.equal(result.events[0].end,.2);assert.equal(result.events[0].seconds,.1);
assert.equal(run([frame(0,.6)]).events[0].entry,false);
result=run([frame(0,.6),frame(.1,null),frame(.2,.6),frame(1,.6),frame(1.1,.6,2)]);
assert.equal(result.events.length,4,'Missing observations, large gaps and changed identities split visits');
assert.ok(result.events.every(e=>!e.entry&&e.seconds===0));
assert.equal(run([frame(0,.6),{...frame(.1,.6),camera:{...camera,scene:1}}]).events.length,2);
assert.equal(run([frame(0,.6),frame(.1,.6)],{pattern:{...Patterns.defaults,minSeconds:.2}}).events.length,0);
assert.equal(run([frame(0,.6)],{info:()=>({team:'hidden'})}).events.length,0);
assert.equal(run([frame(0,.6)],{pattern:{...Patterns.defaults,team:'away'}}).events.length,0);
assert.equal(run([frame(0,.6)],{pattern:{...Patterns.defaults,team:'away'},info:()=>({team:'away',name:'Captain'})}).events[0].label,'Captain');
assert.equal(run([frame(0,.6)],{project:()=>null}).skippedFrames,1);
assert.equal(run([frame(0,.6)],{project:()=>({x:Infinity,y:.5})}).events.length,0);
assert.equal(run([frame(0,.6)],{project:()=>({x:1.1,y:.5})}).events.length,0);
assert.equal(run([frame(0,.5)]).events.length,1,'Zone edges are inclusive');
assert.equal(run([frame(0,.6),frame(1,.6)],{limit:1}).truncated,true);
assert.throws(()=>Patterns.validate({...Patterns.defaults,x1:1,x2:0}));
assert.throws(()=>Patterns.validate({...Patterns.defaults,team:'track',trackId:-1}));
assert.deepEqual(Patterns.sanitize({x1:NaN}),Patterns.defaults);

// Test the actual offline projection against camera movement, letterboxing,
// manual foot corrections, cuts, and singular/missing camera data.
const dir=path.join(__dirname,'../dist'),app=fs.readFileSync(path.join(dir,'app.js'),'utf8'),box={};vm.createContext(box);
vm.runInContext(fs.readFileSync(path.join(dir,'football-features.js'),'utf8'),box);
vm.runInContext(app.slice(app.indexOf('function solveHomography('),app.indexOf("$('calibrateButton').onclick")),box);
const cal={camera,homography:[1,0,0,0,1,0,0,0]};
let project=box.patternProjector(cal,{x:0,y:0,w:1280,h:720});
let q=project(player(.6),{camera:{scene:0,to_reference:[1,0,-.1,0,1,0,0,0,1]}},{footX:10,footY:10});
assert.ok(Math.abs(q.x-.51)<1e-8);assert.ok(Math.abs(q.y-.52)<1e-8);
assert.equal(project(player(.6),{camera:{...camera,scene:1}},{}),null);
assert.equal(project(player(.6),{},{}),null);
assert.throws(()=>box.patternProjector({homography:cal.homography},{}));
project=box.patternProjector(cal,{x:160,y:0,w:960,h:720});q=project(player(0),{camera},{});assert.equal(q.x,.125);
vm.runInContext(fs.readFileSync(path.join(dir,'player-connections.js'),'utf8'),box);
box.TacticalPatterns=Patterns;box.defaults={};box.clamp=(v,a,b)=>Math.max(a,Math.min(b,v));box.cleanColor=()=> '#ffffff';
vm.runInContext(app.slice(app.indexOf('function sanitizeProject('),app.indexOf("$('projectInput').onchange")),box);
const restored=box.sanitizeProject({version:1,annotations:[],patternConfig:{...Patterns.defaults,name:'Wing arrivals',x1:.8}});
assert.equal(restored.patternConfig.name,'Wing arrivals');assert.equal(restored.patternConfig.x1,.8);
assert.equal(box.sanitizeProject({version:1,annotations:[]}).patternConfig.name,'Zone visits');
console.log('PASS: pattern entries, censored visits, missing samples, cuts, filters, caps, projection, and project compatibility.');
