const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const path=require('node:path');
const root=path.join(__dirname,'../dist');
const features=fs.readFileSync(path.join(root,'football-features.js'),'utf8');
const app=fs.readFileSync(path.join(root,'app.js'),'utf8');
const sandbox={};vm.createContext(sandbox);
vm.runInContext(features.slice(0,features.indexOf('function bindFootballControls')),sandbox);
vm.runInContext(app.slice(app.indexOf('function solveHomography('),app.indexOf("$('calibrateButton').onclick")),sandbox);
vm.runInContext(`
const identity=[1,0,0,0,1,0,0,0,1];
let time=1;
const trackMeta={engine_version:2};
const frames=[{t:0,camera:{scene:0,to_reference:identity}},{t:1,camera:{scene:0,to_reference:[1,0,-.1,0,1,-.05,0,0,1]}}];
const state={calibration:{homography:[1,0,0,0,1,0,0,0],camera:{scene:0,to_reference:identity}}};
function frameIndex(t){return t<1?0:1;}
function contentRect(){return {x:0,y:0,w:1280,h:720};}
`,sandbox);
let point=sandbox.calibratedPosition({x:.6,y:.55});
assert.ok(Math.abs(point.x-.5)<1e-8);assert.ok(Math.abs(point.y-.5)<1e-8);
vm.runInContext('frames[1].camera.scene=1;',sandbox);
assert.equal(sandbox.calibrationUsable(),false);assert.equal(sandbox.calibratedPosition({x:.6,y:.55}),null);
assert.equal(sandbox.validateCamera({scene:0,to_reference:[0,0,0,0,0,0,0,0,0]}),false);
assert.equal(sandbox.validateCamera({scene:0,to_reference:[1,0,0,0,1,0,0,0,1]}),true);
vm.runInContext(app.slice(app.indexOf('function validateTracking('),app.indexOf('function loadTracking(')),sandbox);
const valid={schema:'touchline-tracks-v1',fps:25,stride:1,frames:[{t:0,players:[],camera:{scene:0,to_reference:[1,0,0,0,1,0,0,0,1]},ball:null}]};
sandbox.validateTracking(valid);
assert.throws(()=>sandbox.validateTracking({...valid,frames:[{...valid.frames[0],camera:{scene:0,to_reference:[1,2]}}]}));
assert.throws(()=>sandbox.validateTracking({...valid,frames:[{...valid.frames[0],ball:{x:NaN,y:0,w:0,h:0}}]}));
assert.throws(()=>sandbox.validateTracking({...valid,frames:[valid.frames[0],valid.frames[0]]}));
assert.throws(()=>sandbox.validateTracking({...valid,frames:[{...valid.frames[0],t:1},{...valid.frames[0],t:0.5}]}));
console.log('PASS: camera-adjusted pitch mapping, shot-change invalidation, legacy-compatible track validation, and malformed-import rejection.');
