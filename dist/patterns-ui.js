'use strict';
var TacticalPatternsUI=(()=>{
 function mount(api){
  const root=document.getElementById('patternsPanel');if(!root)return;
  const find=id=>root.querySelector('#'+id);
  let result=null,origin=null,generation=0,busy=false;
  const message=text=>{find('patternStatus').textContent=text;};
  function signature(c){return JSON.stringify([c.sourceName,c.calibration,c.corrections,c.rect,c.fps,c.stride,c.demo,c.ready]);}
  function same(c){return origin&&origin.frames===c.frames&&origin.signature===signature(c);}
  function fresh(){if(!same(api.context())){message('Tracking, calibration, or player corrections changed. Run the search again before reviewing or exporting.');return false;}return true;}
  function form(){return TacticalPatterns.validate({name:find('patternName').value,team:find('patternTeam').value,
   trackId:Number(find('patternTrack').value),x1:Number(find('patternX1').value)/100,y1:Number(find('patternY1').value)/100,
   x2:Number(find('patternX2').value)/100,y2:Number(find('patternY2').value)/100,minSeconds:Number(find('patternMin').value)});}
  function preview(){try{const p=form();find('patternZone').setAttribute('x',p.x1*100);find('patternZone').setAttribute('y',p.y1*60);find('patternZone').setAttribute('width',(p.x2-p.x1)*100);find('patternZone').setAttribute('height',(p.y2-p.y1)*60);find('patternZone').setAttribute('visibility','visible');}catch{find('patternZone').setAttribute('visibility','hidden');}find('patternTrack').disabled=find('patternTeam').value!=='track';}
  function fill(p){find('patternName').value=p.name;find('patternTeam').value=p.team;find('patternTrack').value=p.trackId??0;for(const k of ['x1','y1','x2','y2'])find('pattern'+k.toUpperCase()).value=+(p[k]*100).toFixed(4);find('patternMin').value=p.minSeconds;preview();}
  function action(label,fn){const b=document.createElement('button');b.type='button';b.className='button';b.textContent=label;b.onclick=fn;return b;}
  function render(){
   const list=find('patternResults');list.replaceChildren();if(!result)return;
   const entries=result.events.filter(e=>e.entry).length;
   message(`${result.events.length} candidate visits (${entries} observed entries). ${result.skippedFrames} of ${result.frames} frames had no usable matching player. ${result.truncated?'Result limit reached: first 2,000 completed visits retained. Narrow your filter.':''}`);
   for(const [index,e] of result.events.entries()){
    const row=document.createElement('article');row.className='pattern-result';
    const title=document.createElement('strong');title.textContent=`${e.label} · ${api.format(e.start)}–${api.format(e.end)} · ${e.seconds.toFixed(2)} s observed`;
    const detail=document.createElement('p');detail.className='microcopy';detail.textContent=`${e.entry?`Entry between ${e.entryAfter.toFixed(2)} and ${e.start.toFixed(2)} s`:'First seen inside; entry unconfirmed'} · ${e.samples} samples · ${e.endReason}`;
    const controls=document.createElement('div');controls.className='pattern-actions';
    controls.append(action('Review video',()=>{if(fresh())api.seek(e.start);}));
    const status=document.createElement('select');status.setAttribute('aria-label',`Review status for candidate ${index+1}`);
    for(const s of ['unreviewed','keep','dismiss']){const option=document.createElement('option');option.value=s;option.textContent=s;status.append(option);}status.value=e.review;status.onchange=()=>{if(fresh())e.review=status.value;else status.value=e.review;};controls.append(status);
    const note=document.createElement('input');note.maxLength=500;note.value=e.note;note.placeholder='Your interpretation…';note.setAttribute('aria-label',`Interpretation for candidate ${index+1}`);note.oninput=()=>{e.note=note.value;};
    const save=action('Save editable note',()=>{if(!fresh())return;e.noteId=api.saveNote(e.start,e.note,e.noteId);save.textContent='Update saved note';message('Saved to Interpretation notes and your project. You can edit or delete the note there.');});
    if(e.noteId)save.textContent='Update saved note';
    controls.append(save);row.append(title,detail,note,controls);list.append(row);
   }
  }
  find('patternSetup').addEventListener('toggle',()=>{if(find('patternSetup').open){fill(TacticalPatterns.sanitize(api.config()));if(result&&!same(api.context()))message('Results are out of date. Run the search again.');}});
  find('patternForm').addEventListener('input',()=>{preview();if(result)message('Configuration changed. Existing results belong to the last search; run again to apply changes.');});
  find('patternSave').onclick=()=>{try{api.saveConfig(form());message('Pattern settings saved in this project. Export a template to reuse them in another project.');}catch(e){message(e.message);}};
  find('patternTemplateExport').onclick=()=>{try{api.download({schema:'touchline-pattern-v1',pattern:form()},'touchline-pattern.json');}catch(e){message(e.message);}};
  find('patternTemplateImport').onchange=async event=>{try{const file=event.target.files[0];if(!file)return;if(file.size>16000)throw Error('Pattern template is too large.');const data=JSON.parse(await file.text());if(data.schema!=='touchline-pattern-v1')throw Error('Not a Touchline pattern template.');const p=TacticalPatterns.validate(data.pattern);fill(p);api.saveConfig(p);message('Template loaded. Choose the correct player or team for this clip, then search.');}catch(e){message(e.message);}event.target.value='';};
  find('patternRun').onclick=async()=>{
   const token=++generation;busy=true;find('patternRun').disabled=true;find('patternCancel').hidden=false;
   try{
    const p=form(),c=api.context();if(c.demo||!c.ready||!c.frames.length)throw Error('Import or re-link a real video and analyze its tracking first.');
    const project=api.projector(c),snapshot=signature(c);api.saveConfig(p);result=null;origin=null;find('patternResults').replaceChildren();find('patternExport').disabled=true;
    const info=player=>c.corrections[String(player.id)]||{team:player.team||'neutral'};
    const scan=TacticalPatterns.scan({frames:c.frames,pattern:p,project,info,
     players:f=>FootMarkers.unique(f.players.filter(player=>info(player).team!=='hidden'&&player.role!=='referee'),player=>info(player).team,player=>info(player).keepVisible),
     maxGap:Math.min(.5,Math.max(.001,1.5*(c.stride||1)/(c.fps||25)))});
    let step;
    do{
     step=scan.next();if(!step.done){message(`Searching ${step.value.processed} / ${step.value.total} frames…`);await new Promise(resolve=>setTimeout(resolve,0));}
     if(token!==generation)return;
     const now=api.context();if(now.frames!==c.frames||signature(now)!==snapshot)throw Error('Source data changed during search. Run again.');
    }while(!step.done);
    result={...step.value,sourceName:c.sourceName,calibration:JSON.parse(JSON.stringify(c.calibration)),coordinateSystem:'dimensionless pitch [0,1]',algorithm:'touchline-zone-visits-v1',
     events:step.value.events.map(e=>({...e,review:'unreviewed',note:`${p.name}: ${e.label}, ${e.seconds.toFixed(2)} s observed in zone; ${e.entry?'candidate entry':'entry unconfirmed'}.`}))};
    origin={frames:c.frames,signature:snapshot};render();find('patternExport').disabled=false;
   }catch(e){message(e.message);}finally{if(token===generation){busy=false;find('patternRun').disabled=false;find('patternCancel').hidden=true;}}
  };
  find('patternCancel').onclick=()=>{generation++;busy=false;find('patternRun').disabled=false;find('patternCancel').hidden=true;message('Search cancelled.');};
  find('patternExport').onclick=()=>{if(result&&fresh())api.download({schema:'touchline-pattern-results-v1',...result},'touchline-pattern-results.json');};
  fill(TacticalPatterns.sanitize(api.config()));
  return {isBusy:()=>busy};
 }
 return {mount};
})();
