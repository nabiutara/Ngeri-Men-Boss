const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
async function run(){
 const elements=new Map();
 class Element{constructor(){this.children=[];this.value='';this.disabled=false;}set innerHTML(html){for(const match of html.matchAll(/id="([^"]+)"/g))elements.set(match[1],new Element());}querySelector(s){return elements.get(s.slice(1));}append(...items){this.children.push(...items);}replaceChildren(){this.children=[];}showModal(){}close(){}}
 const document={body:new Element(),createElement:()=>new Element()},requests=[],statuses=[];
 let c={videoId:'a'.repeat(64),projectId:'b'.repeat(32),runId:null,demo:false,frames:[{t:0,players:[]}]},title='first',fail=false;
 const box={document,setTimeout,clearTimeout,WeakMap,Map,File:require('node:buffer').File,fetch:async(url,init={})=>{
  requests.push({url,init});
  const data=url==='/api/health'?{local_library:true}:url.startsWith('/api/library/videos?')?{id:c.videoId}:fail?{error:'Disk full'}:{saved:true};
  return {ok:!fail,json:async()=>data};
 }};
 vm.createContext(box);vm.runInContext(fs.readFileSync(path.join(__dirname,'../dist/library-ui.js'),'utf8'),box);
 const library=box.LocalLibrary.mount({button:new Element(),context:()=>c,snapshot:include=>({version:1,title,annotations:[],libraryVideoId:c.videoId,libraryProjectId:c.projectId,...(include?{tracking:{frames:c.frames}}:{})}),status:text=>statuses.push(text)});
 const file=new box.File(['video'],'match.mp4');assert.equal(await library.retain(file),c.videoId);await library.retain(file);
 assert.equal(requests.filter(r=>r.url.startsWith('/api/library/videos?')).length,1,'Known copied file is not uploaded twice');
 await library.saveNow();title='edited';await library.saveNow();
 const writes=requests.filter(r=>r.url==='/api/library/projects').map(r=>JSON.parse(r.init.body));
 assert.ok(writes[0].tracking);assert.equal(writes[1].tracking,undefined,'Autosave does not repeatedly serialize tracking');assert.equal(writes[1].title,'edited');
 c.frames=[];await library.saveNow();assert.ok(JSON.parse(requests.at(-1).init.body).tracking,'Changed tracking is persisted');
 fail=true;await assert.rejects(library.saveNow(),/Disk full/);assert.match(statuses.at(-1),/browser copy retained/);
 fail=false;await library.saveNow();assert.equal(statuses.at(-1),'Saved in Library');
 library.schedule();assert.equal(library.isSaving(),true);await library.saveNow();assert.equal(library.isSaving(),false);
 // Ring overrides are independent of the established label/box palette.
 const colors={};vm.createContext(colors);vm.runInContext(fs.readFileSync(path.join(__dirname,'../dist/frame-review.js'),'utf8'),colors);
 const info={team:'home',ringColorOverride:'#123456',colorOverride:'#abcdef'},settings={homeColor:'#aaaaaa',awayColor:'#bbbbbb',ringColorMode:'team',ringHomeColor:'#112233'};
 assert.equal(colors.FrameReviewCore.color(info,settings),'#abcdef');assert.equal(colors.FrameReviewCore.ringColor(info,settings),'#123456');
 delete info.ringColorOverride;assert.equal(colors.FrameReviewCore.ringColor(info,settings),'#112233');
 settings.ringColorMode='kit';assert.equal(colors.FrameReviewCore.ringColor(info,settings,{away:'#987654'},true),'#987654');
 console.log('PASS: local copy reuse, serialized autosaves, recovery after failure, pending-save warning, and independent ring colors.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
