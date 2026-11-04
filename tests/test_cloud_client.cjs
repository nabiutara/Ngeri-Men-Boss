const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');

async function run(){
  const app=fs.readFileSync(path.join(__dirname,'../dist/app.js'),'utf8');
  const source=("const activeCloudJobKey='touchline-studio-active-cloud-job-v1';\n"+app.slice(app.indexOf('async function startAnalysis'),app.indexOf('\nasync function pollAnalysis'))).replace('async function startAnalysis(){','async function startAnalysis(){const window=__window;');
  const controls={analysisProgress:{hidden:true},progress:{value:0},progressText:{textContent:''},
    modelChoice:{value:'football-best.pt'},confidence:{value:'0.1'},frameStride:{value:'1'},
    trackerChoice:{value:'botsort'},imageSize:{value:'960'}};
  const calls=[];let polled=null;
  const uploadedBlob={part:1};
  const file={name:'match.mp4',size:12*1024*1024,slice:(start,end)=>{assert.equal(start,0);assert.equal(end,file.size);return uploadedBlob;}};
  const memory=new Map();
  const box={clipFile:file,cloudEngine:true,localEngine:false,window:{localStorage:{setItem:(key,value)=>memory.set(key,value),removeItem:key=>memory.delete(key)}},
    jobId:null,jobGeneration:0,uploadController:null,
    setPlaying:()=>{},updateEngineStatus:()=>{},toast:()=>{},AbortController,
    $:id=>controls[id]||{},
    fetch:async(url,options={})=>{calls.push({url,options});
      if(url==='/api/jobs')return {ok:true,json:async()=>({id:'a'.repeat(32),part_size:64*1024*1024,parts:[{part_number:1,upload_url:'https://private-bucket/part'}],upload_headers:{'Content-Type':'application/octet-stream'}})};
      if(url==='https://private-bucket/part')return {ok:true,headers:{get:()=> '"abcdef0123456789abcdef0123456789"'}};
      if(url==='/api/jobs/'+'a'.repeat(32)+'/complete')return {ok:true,json:async()=>({id:'a'.repeat(32)})};
      if(url==='/api/jobs/'+'a'.repeat(32)+'/start')return {ok:true,json:async()=>({id:'a'.repeat(32)})};
      throw new Error('Unexpected request '+url);
    },pollAnalysis:g=>{polled=g;}};
  box.activeCloudJobKey='touchline-studio-active-cloud-job-v1';
  box.__window=box.window;
  vm.createContext(box);vm.runInContext(source,box);
  await vm.runInContext('startAnalysis()',box);
  assert.deepEqual(calls.map(call=>call.url),['/api/jobs','https://private-bucket/part','/api/jobs/'+'a'.repeat(32)+'/complete','/api/jobs/'+'a'.repeat(32)+'/start']);
  assert.equal(JSON.parse(calls[0].options.body).filename,'match.mp4');
  assert.equal(calls[1].options.method,'PUT');
  assert.equal(calls[1].options.body,uploadedBlob);
  assert.equal(JSON.parse(calls[2].options.body).parts[0].ETag,'"abcdef0123456789abcdef0123456789"');
  assert.equal(calls[3].options.method,'POST');
  assert.equal(box.jobId,'a'.repeat(32));
  assert.equal(memory.get('touchline-studio-active-cloud-job-v1'),'a'.repeat(32));
  assert.equal(polled,1);
  assert.equal(controls.progressText.textContent,'Queueing cloud GPU tracking and candidate training…');
  console.log('PASS: cloud multipart upload, ETag completion, job submission and polling handoff.');
}

if(require.main===module)run().catch(error=>{console.error(error);process.exitCode=1;});
module.exports=run;
