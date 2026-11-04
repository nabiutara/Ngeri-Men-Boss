const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const app=fs.readFileSync(path.join(__dirname,'../dist/app.js'),'utf8');
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{value:'',type:'text',listeners:{},addEventListener(type,fn){this.listeners[type]=fn;},focus(){this.listeners.focus?.();}});return elements.get(id);}
const sandbox={$:element,checkpoints:[],saved:[],state:{players:{},demo:false},selected:{type:'player',id:13},time:0,playersAt:()=>[{id:13,team:'away'}],updateSelection:()=>{},setPlaying:()=>{}};
sandbox.checkpoint=()=>sandbox.checkpoints.push(JSON.stringify(sandbox.state.players));
sandbox.autosave=()=>sandbox.saved.push(JSON.stringify(sandbox.state.players));
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../dist/player-connections.js'),'utf8'),sandbox);
vm.runInContext(app.slice(app.indexOf('function playerInfo('),app.indexOf('function drawRounded(')),sandbox);
vm.runInContext(app.slice(app.indexOf('let nameEditStarted='),app.indexOf("$('annotationText').addEventListener")),sandbox);
const name=element('playerName');name.listeners.focus();name.value='Captain';name.listeners.input();
assert.equal(sandbox.state.players['13'].name,'Captain');
name.value='Captain <10>';name.listeners.input();
assert.equal(sandbox.checkpoints.length,1,'Typing a label is one undo operation');
assert.equal(JSON.parse(sandbox.saved.at(-1))['13'].name,'Captain <10>','Input persists before blur');
name.value='';name.listeners.input();assert.equal(sandbox.state.players['13'].name,'');
name.listeners.focus();name.value='Playmaker';name.listeners.input();assert.equal(sandbox.checkpoints.length,2);
// Reopening a project preserves names and manual overlap corrections, including blank labels.
sandbox.defaults={};sandbox.clamp=(v,a,b)=>Math.max(a,Math.min(b,v));sandbox.cleanColor=()=> '#ffffff';
vm.runInContext(app.slice(app.indexOf('function sanitizeProject('),app.indexOf("$('projectInput').onchange")),sandbox);
const project={version:1,annotations:[],connections:[{a:13,b:15,scene:0,color:'#ff8800',width:2}],players:{13:{name:'Playmaker',team:'away',keepVisible:true,footY:12,footX:-5},15:{name:'',team:'home'}}};
const restored=sandbox.sanitizeProject(JSON.parse(JSON.stringify(project)));
assert.equal(restored.connections[0].a,13);assert.equal(restored.players['13'].footY,12);assert.equal(restored.players['13'].footX,-5);assert.equal(restored.players['13'].name,'Playmaker');assert.equal(restored.players['13'].keepVisible,true);assert.equal(restored.players['15'].name,'');
sandbox.state.players=JSON.parse(sandbox.checkpoints[0]);assert.equal(sandbox.playerInfo({id:13,team:'away'}).name,'','Undo restores the unnamed track');
const degenerateProject={version:1,annotations:[],calibration:{points:[{x:0,y:0},{x:0,y:0},{x:0,y:0},{x:0,y:0}]}};
const safelyRestored=sandbox.sanitizeProject(degenerateProject);
assert.equal(safelyRestored.calibration,null,'Degenerate calibration gracefully falls back to null rather than crashing');
console.log('PASS: live label text, immediate autosave, one undo per edit, blank labels, and project round-trip with overlap override.');
