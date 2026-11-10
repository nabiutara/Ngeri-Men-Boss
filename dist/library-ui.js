'use strict';
var LocalLibrary = (() => {
  function mount(options) {
    const dialog=document.createElement('dialog');dialog.id='libraryDialog';dialog.className='library-dialog';
    dialog.innerHTML=`<div class="review-heading"><h2>Local library</h2><button class="button" id="libClose">Close</button></div>
      <p id="libFolder" class="microcopy"></p><p>Videos are copied into this library. Analysis runs and reviewed labels stay on this PC across restarts.</p>
      <div class="library-actions"><button class="button" id="libRefresh">Refresh</button><button class="button" id="libSave">Save current project</button><button class="button" id="libRoot">Open Library folder</button><button class="button" id="libVideos">Videos folder</button><button class="button" id="libAnalyses">Analyses folder</button><button class="button" id="libProjects">Projects folder</button><button class="button" id="libReviews">Reviewed frames folder</button></div>
      <p id="libMessage" role="status"></p><h3>Videos &amp; saved projects</h3><div id="libVideoList"></div><h3>Analysis history</h3><div id="libRuns"></div><h3>Reviewed frames</h3><div id="libFrames" class="library-gallery"></div>`;
    document.body.append(dialog);
    const $=id=>dialog.querySelector('#'+id),knownFiles=new WeakMap(),savedFrames=new Map();
    let timer=null,queue=Promise.resolve(),saving=0,opening=false;
    const message=text=>{$('libMessage').textContent=text;};
    async function json(url,init){const response=await fetch(url,init);const data=await response.json();if(!response.ok)throw Error(data.error||'Library request failed');return data;}
    const post=(url,body)=>json(url,{method:'POST',headers:{'X-Touchline-Client':'studio','Content-Type':'application/json'},body:JSON.stringify(body)});
    async function retain(file){
      if(knownFiles.has(file))return knownFiles.get(file);
      const health=await json('/api/health');if(!health.local_library)return null;
      options.status('Copying video to Library…');
      const row=await json('/api/library/videos?filename='+encodeURIComponent(file.name),{method:'POST',headers:{'X-Touchline-Client':'studio','Content-Type':'application/octet-stream'},body:file});
      knownFiles.set(file,row.id);return row.id;
    }
    function saveNow(){
      clearTimeout(timer);timer=null;
      const c=options.context();if(!c.videoId||c.demo)return queue;
      const includeTracking=!c.runId&&savedFrames.get(c.projectId)!==c.frames;
      const body=JSON.stringify(options.snapshot(includeTracking));const revision=c.frames;
      saving++;
      const operation=queue.catch(()=>{}).then(()=>json('/api/library/projects',{method:'POST',headers:{'X-Touchline-Client':'studio','Content-Type':'application/json'},body})).then(()=>{
        savedFrames.set(c.projectId,revision);
        if(options.context().projectId===c.projectId)options.status('Saved in Library');
      }).catch(error=>{options.status('Library save failed — browser copy retained');message(error.message);throw error;}).finally(()=>saving--);
      queue=operation;return operation;
    }
    function schedule(){clearTimeout(timer);timer=null;const c=options.context();if(c.demo||!c.videoId)return;timer=setTimeout(()=>{saveNow().catch(()=>{});},1200);}
    function button(text,action){const node=document.createElement('button');node.className='button';node.textContent=text;node.onclick=async()=>{node.disabled=true;try{await action();}catch(e){message(e.message);}finally{node.disabled=false;}};return node;}
    function link(text,url){const node=document.createElement('a');node.className='button';node.textContent=text;node.href=url;node.download='';return node;}
    const openFolder=(category,review)=>post('/api/library/open',{category,review});
    async function openVideo(video,run=null,project=null,reviewTime=null){
      if(opening||options.busy())throw Error('Finish the current operation first');
      opening=true;
      try{
        await saveNow();message('Opening copied video…');
        const response=await fetch('/api/library/videos/'+video.id);if(!response.ok)throw Error('Stored video is missing');
        const file=new File([await response.blob()],video.name);knownFiles.set(file,video.id);
        const saved=project?await json('/api/library/projects/'+project.id):null;
        const runId=saved?.libraryRunId||run?.id;
        const tracking=runId?await json('/api/library/analyses/'+runId):saved?.tracking;
        await options.open({file,videoId:video.id,project:saved,runId,tracking,reviewTime});
        dialog.close();
      }finally{opening=false;}
    }
    async function refresh(){
      try{
        const data=await json('/api/library');$('libFolder').textContent=data.folder;
        const videos=new Map(data.videos.map(v=>[v.id,v]));
        $('libVideoList').replaceChildren();$('libRuns').replaceChildren();$('libFrames').replaceChildren();
        for(const video of data.videos){
          const row=document.createElement('article'),title=document.createElement('strong');title.textContent=`${video.name} · ${(video.size/1048576).toFixed(1)} MB · ${video.id.slice(0,8)}`;row.append(title);
          row.append(button('Open video',()=>openVideo(video)));
          for(const project of data.projects.filter(p=>p.video_id===video.id))row.append(button(`Open project: ${project.title} · ${new Date(project.updated).toLocaleString()}`,()=>openVideo(video,null,project)));
          $('libVideoList').append(row);
        }
        if(!data.videos.length)$('libVideoList').textContent='Import a video to copy it here. Older temporary uploads were not retained; import the originals again.';
        for(const run of data.analyses){
          const row=document.createElement('article'),title=document.createElement('p');title.textContent=`${run.name} · ${run.status} · ${new Date(run.created).toLocaleString()} · ${JSON.stringify(run.settings)}${run.error?' · '+run.error:''}`;row.append(title);
          if(run.path)row.append(link('Download tracking JSON','/api/library/analyses/'+run.id));
          if(run.status==='completed'&&videos.has(run.video_id))row.append(button('Open analysis',()=>openVideo(videos.get(run.video_id),run)));
          else if(run.status==='completed'){const hint=document.createElement('p');hint.className='microcopy';hint.textContent=run.video_id?'Import the original video to reconnect this result.':'Legacy result has no video fingerprint. Download it and manually import it with the matching video.';row.append(hint);}
          $('libRuns').append(row);
        }
        for(const review of data.reviews){
          const row=document.createElement('article'),title=document.createElement('p'),image=document.createElement('img');
          title.textContent=`${review.source_name||review.match_id} · ${review.frame.t.toFixed(3)} s · ${review.split} · ${review.frame.objects.length} labels`;
          image.src='/api/library/reviews/'+review.key+'/frame.jpg';image.alt=title.textContent;image.loading='lazy';
          row.append(image,title,link('Download labels','/api/library/reviews/'+review.key+'/review.json'),button('Open frame folder',()=>openFolder('reviewed-frames',review.key)));
          if(videos.has(review.source_sha256))row.append(button('Open label editor',()=>openVideo(videos.get(review.source_sha256),null,null,review.frame.t)));
          $('libFrames').append(row);
        }
        if(!data.reviews.length)$('libFrames').textContent='No confirmed frames on this PC yet. Browser-only drafts appear in the frame editor when the original video is opened.';
        message(`${data.videos.length} videos · ${data.analyses.length} runs · ${data.reviews.length} reviewed frames. File Explorer opens on the host PC only.`);
      }catch(e){message(e.message+' Restart Start Touchline.cmd if the library is unavailable.');}
    }
    $('libClose').onclick=()=>dialog.close();$('libRefresh').onclick=refresh;
    $('libSave').onclick=async()=>{try{await options.ensureCurrent();await saveNow();await refresh();}catch(e){message(e.message);}};
    for(const [id,folder] of [['libRoot',''],['libVideos','videos'],['libAnalyses','analyses'],['libProjects','projects'],['libReviews','reviewed-frames']])$(id).onclick=()=>openFolder(folder).catch(e=>message(e.message));
    options.button.onclick=()=>{dialog.showModal();refresh();};
    return {retain,saveNow,schedule,isSaving:()=>saving>0||timer!==null,refresh};
  }
  return {mount};
})();
