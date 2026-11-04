const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../dist/foot-markers.js'), 'utf8'), sandbox);
const rings = sandbox.FootMarkers;
const player={id:1,x:.5,y:.7,w:.04,h:.12,conf:.9,team:'home'};
const duplicate={...player,id:2,x:.5005,y:.7005,conf:.8};
assert.equal(rings.unique([player,duplicate]).length,1);
assert.equal(rings.unique([player,player,{...player,conf:.8}]).length,1);
// Nested partial detections at the same feet do not get their own ring.
assert.equal(rings.unique([player,{...player,id:3,w:.02,h:.04}]).length,1);
// Nearby players and opposing kits retain their own markers.
assert.equal(rings.unique([player,{...player,id:4,x:.53}]).length,2);
assert.equal(rings.unique([player,{...duplicate,team:'away'}]).length,2);
assert.equal(rings.unique([player,duplicate],p=>p.id===2?'away':'home').length,2);
assert.equal(rings.unique([player,{...duplicate,y:.72}]).length,2);
let motion = rings.begin(0, true, 0);
rings.position(1, {x:100,y:100}, 18, motion);
motion = rings.begin(1/60, true, 0);
let point = rings.position(1, {x:110,y:100}, 18, motion);
assert.ok(point.x < 110 && 110-point.x <= 4.5);
motion = rings.begin(1/60, true, 0);
const repeated = rings.position(1, {x:110,y:100}, 18, motion);
assert.equal(repeated.x, point.x);
assert.equal(repeated.y, point.y);
// Seeking, pausing, and camera cuts must snap to the measured position.
motion = rings.begin(5, true, 0);
assert.equal(rings.position(1, {x:400,y:100}, 18, motion).x,400);
motion = rings.begin(5, false, 0);
assert.equal(rings.position(1, {x:420,y:100}, 18, motion).x,420);
motion = rings.begin(5.01, true, 1);
assert.equal(rings.position(1, {x:440,y:100}, 18, motion).x,440);
const calls=[];
const context=new Proxy({}, {get: (_, key) => (...args) => calls.push([key,...args]),set:()=>true});
rings.draw(context, {x:20,y:30}, 18, '#55cc88', 1);
assert.equal(calls.filter(c=>c[0]==='ellipse').length,3);
assert.ok(calls.filter(c=>c[0]==='ellipse').every(c=>c[3]===18&&c[4]===18*.34));
assert.equal(calls.filter(c=>c[0]==='stroke').length,3);
assert.ok(calls.some(c=>c[0]==='clip'&&c[1]==='evenodd'));
assert.equal(calls[0][0],'save');assert.equal(calls.at(-1)[0],'restore');
// Run the real render function: even repeated rows with the same ID draw once.
const app=fs.readFileSync(path.join(__dirname,'../dist/app.js'),'utf8');
let drawn=0;
Object.assign(sandbox,{ctx:context,state:{demo:false,settings:{showFeet:true,overlayOpacity:90,ringSize:18},annotations:[]},video:{readyState:0},needsRelink:false,time:1,playing:true,currentPlayers:[],trackMeta:null,calibrationPoints:null,selected:null,draft:null,playersAt:()=>[player,player,duplicate],playerInfo:p=>({team:p.team}),teamColor:()=>'#55cc88',screenPlayer:p=>({x:p.x*1280,y:p.y*720,w:p.w*1280,h:p.h*720}),frameAt:()=>({camera:{scene:0}}),renderBoard:()=>{},refreshPlayerPicker:()=>{},$:()=>({})});
sandbox.FootMarkers={...rings,draw:()=>drawn++};
sandbox.refreshConnectionControls=()=>{};
vm.runInContext(fs.readFileSync(path.join(__dirname,'../dist/frame-review.js'),'utf8'),sandbox);
vm.runInContext(app.slice(app.indexOf('function overlayColor('),app.indexOf('function teamColor(')),sandbox);
vm.runInContext(app.slice(app.indexOf('function render(){'),app.indexOf('function drawAthlete(')),sandbox);
vm.runInContext('render()',sandbox);
assert.equal(drawn,1);
// Visually reviewed real MATCH1 full-body / torso duplicate pairs.
const fixtures=JSON.parse(fs.readFileSync(path.join(__dirname,'match1-duplicate-fixtures.json'),'utf8'));
for(const fixture of fixtures){
 const result=rings.unique(fixture.players);
 assert.equal(result.length,1,`Duplicate at ${fixture.time}s`);
 const complete=fixture.players.reduce((a,b)=>a.w*a.h>b.w*b.h?a:b);
 assert.equal(result[0].id,complete.id);
 assert.equal(rings.unique(fixture.players,p=>p.team,()=>true).length,2,'Manual overlap override');
}
// Similar aligned players with different head AND foot heights must survive.
assert.equal(rings.unique([player,{...player,id:8,y:.74}]).length,2);
console.log('PASS: 6 reviewed MATCH1 duplicates, manual override, separate nearby players, 3 arcs on one ellipse, one render per player, and smoothing resets.');
