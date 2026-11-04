const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const box={Uint32Array,Uint8Array,DataView,setTimeout};vm.createContext(box);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../dist/frame-review.js'),'utf8'),box);
const C=box.FrameReviewCore;
for(const size of [0,3,55,56,63,64,65,127,128,129,1048576]){
 const input=Buffer.alloc(size);for(let i=0;i<size;i++)input[i]=(i*31+7)%256;
 for(const step of [1,17,64,100000]){const hash=new C.SHA256();for(let i=0;i<size;i+=step)hash.update(input.subarray(i,i+step));assert.equal(hash.hex(),crypto.createHash('sha256').update(input).digest('hex'),'SHA256 chunk boundary '+size+'/'+step);}
}
const objects=C.proposals({players:[{id:9,role:'player',x:.5,y:.8,w:.2,h:.4,team:'away'}],ball:{observed:false,x:.1,y:.1,w:.01,h:.01}});
assert.equal(objects.length,1);assert.deepEqual(Array.from(objects[0].bbox),[.4,.4,.6,.8]);
const frame={t:0,reviewed:true,fully_annotated:true,objects};C.validateFrame(frame,true);
assert.throws(()=>C.validateFrame({...frame,objects:[...objects,...objects]},true),/distinct/);
const doc={schema:'touchline-groundtruth-v1',source_sha256:'a'.repeat(64),match_id:'match-a',frames:[frame,{...frame,t:1,reviewed:false}]};
assert.equal(C.reviewedDocument(doc).frames.length,1);C.invalidate(frame);assert.throws(()=>C.reviewedDocument(doc),/Confirm/);
assert.equal(C.nearest([{t:0},{t:.2},{t:.4}],.31).t,.4);
const settings={useJerseyRingColors:true,homeColor:'#123456',awayColor:'#654321'},palette={home:'#ff0000',away:'#0000ff'};
assert.equal(C.color({team:'home'},settings,palette),'#ff0000');assert.equal(C.color({team:'home'},settings,palette,true),'#0000ff');
assert.equal(C.color({team:'home',colorOverride:'#00ff00'},settings,palette),'#00ff00');
assert.equal(C.color({team:'home'},{...settings,useJerseyRingColors:false},palette),'#123456');
console.log('PASS: source SHA256, box coordinates, review gates, unique identities and consistent overlay colors.');
