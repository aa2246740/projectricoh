(async () => {
  const {state}=await import('/assets/state.js');
  if(!state.settings)state.settings=await(await fetch('/api/settings')).json();
  state.photos=[];
  const gs = await import('/assets/gpu_stage.js');
  const results = [];
  for (const c of window.__reviewCases) {
    const geometry = {straighten:0,vertical:0,horizontal:0,distortion:0,rotate90:0,flip:false,...c.geometry};
    const view = {photo:{id:c.photo,name:c.id},stage:c.stage,ed:{v2:true,lut:c.lut||null,geometry,frame:{style:'none'},stamp:{enabled:false},caps:{recipe:'full'}}};
    const ctx = {stage:c.stage,recipe:c.recipe,adjust:c.adjust||{},curve:c.curve||null,geometry,crop:c.crop||null,geometryKey:'review'};
    let way='wait';
    const transitions=[];
    const started=performance.now();
    for(let n=0;n<80&&way!=='gpu';n++) {
      way=await new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>reject(new Error('No route completion: '+c.id)),45000);
        const done=(r)=>{clearTimeout(timer);resolve(r);};
        const r=gs.route(view,ctx,()=>done('wait'));
        if(transitions[transitions.length-1]!==r)transitions.push(r);
        if(r==='gpu'||(r==='server'&&!c.lut))done(r);
      });
      if(way==='server')break;
    }
    if(way!=='gpu'){results.push({id:c.id,way,transitions});continue;}
    const engine=gs.gpuEngineForTests();
    const t=performance.now();
    const rb=await engine.readback();
    const sent=await fetch(`/__review/readback/${c.id}?w=${rb.w}&h=${rb.h}&mode=${window.__reviewMode}`,{method:'POST',body:rb.data});
    if(!sent.ok)throw new Error('readback receipt failed '+sent.status);
    results.push({id:c.id,way,transitions,toGpuMs:t-started,w:rb.w,h:rb.h,readbackAndTransferMs:performance.now()-t,adapter:engine.info,stats:engine.stats(),label:view.ed.label,calibrated:view.ed.calibrated});
  }
  return results;
})()
