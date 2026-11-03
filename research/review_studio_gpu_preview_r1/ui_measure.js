(async()=>{
  const e=(await import('/assets/gpu_stage.js')).gpuEngineForTests();
  if(!e)throw new Error('GPU engine must already be active');
  const perf={adapter:e.info,ua:navigator.userAgent,dpr:devicePixelRatio,visibility:document.visibilityState,inputs:[],frames:[],raf:[],network:[],switches:[]};
  const oldFrame=e.onFrame;
  let last=0,dirtyInput=null;
  const input=(ev)=>{
    if(ev.target.matches('input[type=range]')){
      const row={t:performance.now(),trusted:ev.isTrusted,label:ev.target.getAttribute('aria-label'),value:ev.target.value,hash:location.hash};
      perf.inputs.push(row);dirtyInput=row;
    }
  };
  document.addEventListener('input',input,true);
  e.onFrame=(frame)=>{
    oldFrame?.(frame);
    const row={...frame,t:performance.now(),key:e.currentKey(),hash:location.hash};
    if(dirtyInput){
      row.input=perf.inputs.indexOf(dirtyInput);row.inputToSubmitMs=performance.now()-dirtyInput.t;
      const t=dirtyInput.t;dirtyInput=null;
      e.device.queue.onSubmittedWorkDone().then(()=>{row.inputToDoneMs=performance.now()-t;});
      requestAnimationFrame(()=>{row.inputToNextRafMs=performance.now()-t;});
    }
    perf.frames.push(row);
    if(window.__reviewSwitch&&row.key?.includes(window.__reviewSwitch.id)){
      perf.switches.push({...window.__reviewSwitch,ms:row.t-window.__reviewSwitch.t,key:row.key,hash:row.hash});window.__reviewSwitch=null;
    }
  };
  const observer=new PerformanceObserver(list=>{for(const row of list.getEntries()) if(row.name.includes('/api/')) perf.network.push({url:row.name,duration:row.duration,startTime:row.startTime,transferSize:row.transferSize});});
  observer.observe({entryTypes:['resource']});
  let remaining=240;
  function tick(t){if(last)perf.raf.push(t-last);last=t;if(remaining-->0)requestAnimationFrame(tick);}
  requestAnimationFrame(tick);
  window.__reviewPerf=perf;
  window.__reviewMeasureCleanup=()=>{document.removeEventListener('input',input,true);e.onFrame=oldFrame;observer.disconnect();};
  return {adapter:perf.adapter,visibility:perf.visibility,rangeLabels:[...document.querySelectorAll('input[type=range]')].map(x=>x.getAttribute('aria-label'))};
})()
