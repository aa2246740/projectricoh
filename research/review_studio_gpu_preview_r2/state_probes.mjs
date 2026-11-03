import {readFileSync,writeFileSync,renameSync} from 'node:fs';
import {launchPinnedChromium} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
const report=new URL('./',import.meta.url);
const temp='/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2/';
const cases=JSON.parse(readFileSync(temp+'real-cases.json','utf8'));
const browser=await launchPinnedChromium({args:['--enable-unsafe-webgpu','--enable-unsafe-swiftshader','--use-webgpu-adapter=swiftshader']});
const rows=[];
async function page(){const p=await browser.newPage();await p.goto('http://127.0.0.1:49761/?token=review-isolated-local-only');await p.evaluate(async()=>{(await import('/assets/state.js')).state.photos=[];});return p;}
const helper=`async function run(c, query='') {
 const gs=await import('/assets/gpu_stage.js'+query);
 const geometry={straighten:0,vertical:0,horizontal:0,distortion:0,rotate90:0,flip:false,...c.geometry};
 const view={photo:{id:c.photo,name:c.id},ed:{v2:true,lut:c.lut||null,geometry,frame:{style:'none'},stamp:{enabled:false}}};
 const ctx={stage:c.stage,recipe:c.recipe,adjust:c.adjust||{},curve:c.curve||null,geometry,crop:c.crop||null,geometryKey:'review'};
 let way='wait';for(let i=0;i<50&&way==='wait';i++)way=await new Promise(resolve=>{const r=gs.route(view,ctx,()=>resolve('wait'));if(r!=='wait')resolve(r);});
 return {way,engine:gs.gpuEngineForTests(),view,ctx,gs};
}`;
let p;
const lutCase=cases.find(c=>c.id==='e_display_lut');
try {
 p=await page();await p.evaluate('(()=>{'+helper+';window.__run=run;return true;})()');
 const cached=await p.evaluate(async c=>{
   const requests=[];const original=window.fetch;window.fetch=(...args)=>{requests.push(String(args[0]));return original(...args);};
   const first=await window.__run(c);const before=first.way;
   const patched=await fetch('/api/luts/'+c.lut,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({output_space:'vlog'})});
   const serverTable=await fetch('/api/luts/'+c.lut+'/table');
   const again=await window.__run(c);(await import('/assets/state.js')).emit('camdata-changed');
   const afterEvent=await window.__run(c);
   const fresh=await window.__run(c,'?independent-review-fresh=lut');
   const result={case:'lut_metadata_cache',before,patch_status:patched.status,new_table_status:serverTable.status,after_patch:again.way,after_event:afterEvent.way,fresh_module:fresh.way,table_requests:requests.filter(x=>x.endsWith('/table')).length};
   await fetch('/api/luts/'+c.lut,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({output_space:'srgb'})});
   first.engine?.dispose();fresh.engine?.dispose();return result;
 },lutCase);rows.push(cached);await p.close();
 p=await page();await p.evaluate('(()=>{'+helper+';window.__run=run;return true;})()');
 const recipe=cases[0];const cameraBefore=await p.evaluate(async c=>{window.__before=await window.__run(c);return window.__before.way;},recipe);
 if(cameraBefore!=='gpu')throw new Error('Invalid fixture: camera-data probe must start on GPU');
 const manifest=temp+'studio/app-home/calib/manifest.json';renameSync(manifest,manifest+'.review-disabled');
 try {
   rows.push(await p.evaluate(async c=>{
     const status=await(await fetch('/api/camdata/status')).json();
     (await import('/assets/state.js')).emit('camdata-changed');
     const cached=await window.__run(c);const fresh=await window.__run(c,'?independent-review-fresh=camdata');
     const result={case:'camdata_cache',server_ready:status.ready,before:window.__before.way,after_event:cached.way,fresh_module:fresh.way};
     window.__before.engine?.dispose();fresh.engine?.dispose();return result;
   },recipe));
 } finally {renameSync(manifest+'.review-disabled',manifest);}
 await p.close();
 p=await page();rows.push(await p.evaluate(async sid=>{
   const {Engine}=await import('/assets/gpu/engine.js');const engine=await Engine.create();
   const device=engine.device;const original=device.createBuffer;
   let made=0,destroyed=0,madeBytes=0,destroyedBytes=0;
   device.createBuffer=function(desc){const buf=original.call(this,desc);made++;madeBytes+=desc.size;const destroy=buf.destroy;buf.destroy=function(){destroyed++;destroyedBytes+=desc.size;return destroy.call(this);};return buf;};
   const res=await fetch('/api/photos/'+sid+'/bake');const meta=JSON.parse(decodeURIComponent(res.headers.get('X-GXR-Bake')));const data=await res.arrayBuffer();
   for(let i=0;i<12;i++)engine.addBake('same-key',meta,data);
   const beforeDispose={made,destroyed,madeBytes,destroyedBytes,mapEntries:engine.stats().bakes};
   engine.dispose();return {case:'duplicate_bake_explicit_lifetime',tableBytes:data.byteLength,beforeDispose,afterDispose:{made,destroyed,madeBytes,destroyedBytes},note:'Explicit destroy calls only. This probe does not measure post-GC driver allocation.'};
 },cases[0].photo));await p.close();
} finally {
 if(p&&!p.isClosed())await p.close();await browser.close();
 writeFileSync(new URL('state-probes.json',report),JSON.stringify(rows,null,2)+'\n');
}
console.log(JSON.stringify(rows));
