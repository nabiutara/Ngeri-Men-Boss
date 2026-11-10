/* Exercise the actual editor event handlers with a simulated DOM/video decoder.
   This covers review state and upload wiring; it is not visual browser QA. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');

async function run(){
 const nodes=new Map(),requests=[],downloads=[],corrections=[],saved=new Map();
 const defer=fn=>queueMicrotask(fn);
 class Element {
  constructor(tag='div'){this.tag=tag;this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.children=[];this.events={};this.style={};this.classList={toggle(){}};this.width=640;this.height=360;this.open=false;this.textContent='';}
  set innerHTML(html){for(const match of html.matchAll(/\bid="([^"]+)"/g))nodes.set(match[1],new Element());for(const id of ['rfRole','rfSplit','rfTeam','rfEpochs','rfSize','rfBatch'])nodes.get(id).value=({rfRole:'player',rfSplit:'train',rfTeam:'neutral',rfEpochs:'1',rfSize:'640',rfBatch:'1'})[id];}
  querySelector(selector){return nodes.get(selector.slice(1));}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
  add(option){this.children.push(option);}
  addEventListener(name,handler){(this.events[name]??=[]).push(handler);}
  removeEventListener(name,handler){this.events[name]=(this.events[name]||[]).filter(h=>h!==handler);}
  emit(name,event={}){for(const handler of [...(this.events[name]||[])])handler(event);}
  showModal(){this.open=true;}
  close(){this.open=false;this.emit('close');}
  setPointerCapture(){}
  getBoundingClientRect(){return {left:0,top:0,width:640,height:360};}
  getContext(){return new Proxy({measureText:()=>({width:45}),getImageData:()=>({data:new Uint8Array([220,30,20,255])})},{get:(o,k)=>o[k]||(()=>{})});}
  toDataURL(){return 'data:image/jpeg;base64,/9j/fixture';}
  click(){return this.onclick?.();}
 }
 class Video extends Element {
  constructor(){super('video');this.videoWidth=640;this.videoHeight=360;this.duration=2;this.readyState=2;this.at=0;}
  set currentTime(value){this.at=value;defer(()=>this.emit('seeked'));}
  get currentTime(){return this.at;}
  load(){if(this.src)defer(()=>this.emit('loadeddata'));}
  removeAttribute(key){delete this[key];}
  pause(){}
 }
 const db={transaction:()=>({objectStore:()=>({get:key=>{const request={};defer(()=>{request.result=saved.get(key);request.onsuccess?.();});return request;},put:(value,key)=>saved.set(key,JSON.parse(JSON.stringify(value)))})})};
 const document={body:new Element(),createElement:tag=>tag==='video'?new Video():new Element(tag)};
 const indexedDB={open:()=>{const request={};defer(()=>{request.result=db;request.onsuccess();});return request;}};
 const emptySummary=()=>({schema:'touchline-training-status-v1',ready:false,promotion:'manual-only',splits:Object.fromEntries(['train','val','test'].map(s=>[s,{frames:0,matches:[],classes:{},backgrounds:0}])),jobs:[]});
 const box={document,indexedDB,Option:class {constructor(text,value){this.text=text;this.value=value;}},Uint32Array,Uint8Array,DataView,Blob,setTimeout,clearTimeout,window:{confirm:()=>true},URL:{createObjectURL:()=> 'blob:synthetic',revokeObjectURL(){}},fetch:async(url,options={})=>{requests.push({url,options});return {ok:true,json:async()=>url==='/api/training'?emptySummary():{saved:true,key:'fixture',kit_calibration_ready:false}};}};
 vm.createContext(box);
 for(const file of ['frame-review.js','frame-review-ui.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../dist',file),'utf8'),box);
 const button=new Element(),blob=new Blob(['synthetic-video']);blob.name='synthetic.webm';
 const editor=box.FrameReviewUI.mount({button,context:()=>({file:blob,time:0,frames:[{t:0,players:[{id:7,role:'player',team:'home',x:.5,y:.8,w:.2,h:.4}]}]}),pause(){},trackInfo:()=>({team:'home'}),correctTrack:(id,patch)=>corrections.push({id,patch}),download:(blob,name)=>downloads.push({blob,name}),toast(){}});
 await editor.open();await new Promise(resolve=>setTimeout(resolve,5));
 assert.equal(nodes.get('rfObjects').children.length,1);
 assert.match(nodes.get('rfTimestamp').textContent,/draft/);
 await nodes.get('rfConfirm').onclick();assert.equal(requests.filter(r=>r.url==='/api/training/frames').length,0);
 nodes.get('rfMatch').value='match-reviewed';nodes.get('rfComplete').checked=true;
 await nodes.get('rfConfirm').onclick();
 let body=JSON.parse(requests.find(r=>r.url==='/api/training/frames').options.body);
 assert.equal(body.match_id,'match-reviewed');assert.equal(body.source_sha256.length,64);
 assert.deepEqual(body.frame.objects[0].bbox,[.4,.4,.6,.8]);assert.equal(body.frame.reviewed,true);
 nodes.get('rfExport').onclick();assert.equal(downloads.length,1);
 const exported=JSON.parse(await downloads[0].blob.text());assert.equal(exported.frames[0].objects[0].id,7);
 nodes.get('rfTeam').value='away';nodes.get('rfTeam').onchange();
 assert.equal(nodes.get('rfComplete').checked,false);assert.match(nodes.get('rfTimestamp').textContent,/draft/);
 nodes.get('rfColor').value='#dd2211';nodes.get('rfColor').onchange();nodes.get('rfApply').onclick();
 assert.equal(corrections[0].id,7);assert.equal(corrections[0].patch.colorOverride,'#dd2211');assert.equal(corrections[0].patch.team,'away');
 nodes.get('rfExport').onclick();assert.equal(downloads.length,1,'Draft edits cannot be exported as reviewed truth');
 nodes.get('rfDelete').onclick();nodes.get('rfComplete').checked=true;await nodes.get('rfConfirm').onclick();
 body=JSON.parse(requests.filter(r=>r.url==='/api/training/frames').at(-1).options.body);
 assert.equal(body.frame.objects.length,0,'A consciously reviewed empty frame becomes a background sample');
 nodes.get('rfDraw').onclick();const c=nodes.get('rfCanvas');
 c.emit('pointerdown',{clientX:64,clientY:36,pointerId:1,preventDefault(){}});
 c.emit('pointermove',{clientX:192,clientY:180});c.emit('pointerup');
 assert.equal(nodes.get('rfObjects').children.length,1);
 nodes.get('rfComplete').checked=true;await nodes.get('rfConfirm').onclick();
 body=JSON.parse(requests.filter(r=>r.url==='/api/training/frames').at(-1).options.body);
 assert.deepEqual(body.frame.objects[0].bbox,[.1,.1,.3,.5]);
 // Every source frame is reachable even when analysis only proposed timestamp 0.
 await nodes.get('rfNextFrame').onclick();
 assert.equal(Number(nodes.get('rfTime').value),.033333);
 assert.equal(nodes.get('rfObjects').children.length,0,'Do not attach nearby-frame proposals to a different image');
 nodes.get('rfCopyPrevious').onclick();
 assert.equal(nodes.get('rfObjects').children.length,1);
 assert.equal(nodes.get('rfComplete').checked,false,'Copied labels always require fresh review');
 nodes.get('rfX1').value=15;nodes.get('rfX1').onchange();
 nodes.get('rfComplete').checked=true;await nodes.get('rfConfirm').onclick();
 body=JSON.parse(requests.filter(r=>r.url==='/api/training/frames').at(-1).options.body);
 assert.equal(body.frame.t,.033333);assert.equal(body.frame.objects[0].bbox[0],.15);
 assert.equal(body.frame.objects[0].source_track_id,undefined,'Copied identities cannot edit unrelated analysis tracks');
 await nodes.get('rfPrevFrame').onclick();
 assert.equal(nodes.get('rfX1').value,10,'Editing the next frame must not mutate the prior frame');
 nodes.get('rfClear').onclick();assert.equal(nodes.get('rfObjects').children.length,0);
 nodes.get('rfUndo').onclick();assert.equal(nodes.get('rfObjects').children.length,1);
 nodes.get('rfRedo').onclick();assert.equal(nodes.get('rfObjects').children.length,0);
 nodes.get('rfNewRole').value='ball';nodes.get('rfNewTeam').value='home';nodes.get('rfDraw').onclick();
 c.emit('pointerdown',{clientX:64,clientY:36,pointerId:2,preventDefault(){}});
 c.emit('pointermove',{clientX:80,clientY:50});c.emit('pointerup');
 nodes.get('rfComplete').checked=true;await nodes.get('rfConfirm').onclick();
 body=JSON.parse(requests.filter(r=>r.url==='/api/training/frames').at(-1).options.body);
 assert.equal(body.frame.objects[0].role,'ball');assert.equal(body.frame.objects[0].id,null);assert.equal(body.frame.objects[0].team,'neutral');
 nodes.get('rfTime').value=.4;await nodes.get('rfGo').onclick();
 assert.equal(Number(nodes.get('rfTime').value),.4);assert.equal(nodes.get('rfObjects').children.length,0);
 await nodes.get('rfPrevFrame').onclick();await nodes.get('rfNextFrame').onclick();
 assert.equal(Number(nodes.get('rfTime').value),.4,'Frame stepping must not accumulate rounded timestamp drift');
 assert.equal(requests.filter(r=>r.url==='/api/training/jobs').length,0,'Reviewing samples never starts model training');
 await nodes.get('rfClose').onclick();
 // Confirmed PC reviews survive clearing the browser review cache.
 saved.clear();
 const remote={source_sha256:body.source_sha256,match_id:body.match_id,split:body.split,frame:body.frame,reviewed_utc:new Date().toISOString()};
 box.fetch=async url=>({ok:true,json:async()=>url.startsWith('/api/library/reviews/')?{records:[remote]}:emptySummary()});
 await editor.open();
 assert.equal(nodes.get('rfObjects').children.length,1);
 assert.equal(nodes.get('rfRole').value,'ball','Load the stored reviewed label, not a new player proposal');
 assert.equal(nodes.get('rfComplete').checked,true);
 await nodes.get('rfClose').onclick();
 console.log('PASS: editor capture, full-frame confirmation, draft invalidation, drawing, manual colors, background samples, and upload/export wiring.');
}
if(require.main===module)run().catch(error=>{console.error(error);process.exitCode=1;});
module.exports=run;
