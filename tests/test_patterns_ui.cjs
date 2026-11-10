const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
async function run(){
 class Element{
  constructor(){this.value='';this.children=[];this.events={};this.hidden=false;this.disabled=false;this.textContent='';}
  append(...children){this.children.push(...children);} replaceChildren(...children){this.children=children;}
  setAttribute(){} addEventListener(name,fn){this.events[name]=fn;}
 }
 const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
 get('patternsPanel').querySelector=s=>get(s.slice(1));
 const document={getElementById:get,createElement:()=>new Element()},downloads=[],notes=[],seeks=[];
 const Patterns=require('../dist/patterns.js');let config=Patterns.defaults;
 const camera={scene:0,to_reference:[1,0,0,0,1,0,0,0,1]};
 const context={frames:[0,.1,.2].map((t,i)=>({t,camera,players:[{id:7,team:'home',x:i?.6:.4,y:.5,w:.1,h:.2}]})),ready:true,demo:false,sourceName:'test.mp4',corrections:{},fps:10,stride:1,calibration:{camera},rect:{}};
 const box={document,TacticalPatterns:Patterns,setTimeout,FootMarkers:{unique:p=>p}};vm.createContext(box);
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../dist/patterns-ui.js'),'utf8'),box);
 box.TacticalPatternsUI.mount({config:()=>config,saveConfig:p=>{config=p;},context:()=>context,projector:()=>p=>p,format:t=>String(t),seek:t=>seeks.push(t),saveNote:(t,text,id)=>{notes.push({t,text,id});return 'note-1';},download:(data,name)=>downloads.push({data,name})});
 await get('patternRun').onclick();assert.equal(get('patternResults').children.length,1);
 let row=get('patternResults').children[0],controls=row.children[3];controls.children[0].onclick();assert.equal(seeks[0],.1);
 row.children[2].value='Review overlap';row.children[2].oninput();controls.children[2].onclick();controls.children[2].onclick();
 assert.equal(notes[0].text,'Review overlap');assert.equal(notes[1].id,'note-1','Updating a saved candidate reuses the note');
 controls.children[1].value='dismiss';controls.children[1].onchange();get('patternExport').onclick();assert.equal(downloads[0].data.events[0].review,'dismiss');
 context.corrections[7]={team:'away'};controls.children[0].onclick();get('patternExport').onclick();assert.equal(seeks.length,1);assert.equal(downloads.length,1);assert.match(get('patternStatus').textContent,/changed/);
 await get('patternRun').onclick();assert.equal(get('patternResults').children.length,1);
 get('patternX1').value='100';await get('patternRun').onclick();assert.match(get('patternStatus').textContent,/valid zone/);
 get('patternX1').value='50';const pending=get('patternRun').onclick();get('patternCancel').onclick();await pending;assert.match(get('patternStatus').textContent,/cancelled/);assert.equal(get('patternRun').disabled,false);
 context.ready=false;await get('patternRun').onclick();assert.match(get('patternStatus').textContent,/re-link/);
 console.log('PASS: pattern UI search, seek, note updates, review/export, stale results, validation, cancellation, and missing-video guard.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
