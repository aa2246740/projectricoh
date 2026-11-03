import {readFileSync,writeFileSync} from 'node:fs';
import {launchPinnedChromium} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
const report=new URL('./',import.meta.url);
const cid=JSON.parse(readFileSync(new URL('real-inputs.json',report),'utf8')).luts.display;
const browser=await launchPinnedChromium({args:['--enable-unsafe-webgpu','--use-angle=metal'],ignoreDefaultArgs:['--use-angle=swiftshader-webgl']});
try {
 const page=await browser.newPage();await page.goto('http://127.0.0.1:49761/?token=review-isolated-local-only');
 const result=await page.evaluate(async cid=>{
  const {Engine}=await import('/assets/gpu/engine.js');const e=await Engine.create();const d=e.device;
  const lr=await fetch('/api/luts/'+cid+'/table');const lm=JSON.parse(decodeURIComponent(lr.headers.get('x-gxr-lut')));const ld=await lr.arrayBuffer();
  const br=await fetch('/api/photos/256a7054fb1de204/bake');const bm=JSON.parse(decodeURIComponent(br.headers.get('x-gxr-bake')));const bd=await br.arrayBuffer();
  const calls={texturesCreated:0,texturesDestroyed:0,textureBytesCreated:0,textureBytesDestroyed:0,buffersCreated:0,buffersDestroyed:0,bufferBytesCreated:0,bufferBytesDestroyed:0};
  const ct=d.createTexture,cb=d.createBuffer;
  d.createTexture=function(desc){const t=ct.call(this,desc);const size=desc.size;const bytes=size[0]*size[1]*size[2]*(desc.format==='rgba8unorm'?4:16);calls.texturesCreated++;calls.textureBytesCreated+=bytes;let dead=false;const destroy=t.destroy;t.destroy=function(){if(!dead){dead=true;calls.texturesDestroyed++;calls.textureBytesDestroyed+=bytes;}return destroy.call(this);};return t;};
  d.createBuffer=function(desc){const b=cb.call(this,desc);calls.buffersCreated++;calls.bufferBytesCreated+=desc.size;let dead=false;const destroy=b.destroy;b.destroy=function(){if(!dead){dead=true;calls.buffersDestroyed++;calls.bufferBytesDestroyed+=desc.size;}return destroy.call(this);};return b;};
  const snap=()=>({...calls,stats:e.stats(),liveTableBytes:calls.textureBytesCreated-calls.textureBytesDestroyed,liveBakeBytes:calls.bufferBytesCreated-calls.bufferBytesDestroyed});
  for(let i=0;i<12;i++){e.addLut('same-key',lm,ld);e.addBake('same-key',bm,bd);}
  const overwrite=snap();
  for(let i=0;i<8;i++)e.addLut('version-'+i,lm,ld);
  for(let i=0;i<28;i++)e.addBake('version-'+i,bm,bd);
  const capped=snap();
  await d.queue.onSubmittedWorkDone();
  e.dispose();
  return {adapter:e.info,tableBytes:ld.byteLength,bakeBytes:bd.byteLength,overwrite,capped,disposed:snap(),scope:'Requested WebGPU allocation sizes and explicit destroy calls; physical driver VRAM is unmeasured.'};
 },cid);
 writeFileSync(new URL('table-resource-probe.json',report),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
} finally {await browser.close();}
