import {writeFileSync} from 'node:fs';
import {launchPinnedChromium} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
const browser=await launchPinnedChromium({args:['--enable-unsafe-webgpu','--use-angle=metal'],ignoreDefaultArgs:['--use-angle=swiftshader-webgl']});
try {
 const page=await browser.newPage();await page.goto('http://127.0.0.1:49761/?token=review-isolated-local-only');
 const result=await page.evaluate(async()=>{
  const {Engine}=await import('/assets/gpu/engine.js');const engine=await Engine.create();const device=engine.device;
  const info=await(await fetch('/api/photos/256a7054fb1de204/gpu')).json();const data=await(await fetch(info.raw.url)).arrayBuffer();
  const ct=device.createTexture,cb=device.createBuffer;let texturesCreated=0,texturesDestroyed=0,buffersCreated=0,buffersDestroyed=0;
  device.createTexture=function(desc){const tex=ct.call(this,desc);texturesCreated++;const destroy=tex.destroy;tex.destroy=function(){texturesDestroyed++;return destroy.call(this);};return tex;};
  device.createBuffer=function(desc){const buf=cb.call(this,desc);buffersCreated++;const destroy=buf.destroy;buf.destroy=function(){buffersDestroyed++;return destroy.call(this);};return buf;};
  const snapshots=[];
  for(let i=0;i<17;i++){
   await engine.addRaw('source_'+i,info.raw,data,info.scene);if(i===0)engine.show('source_0');
   snapshots.push({i,...engine.stats(),texturesCreated,texturesDestroyed,buffersCreated,buffersDestroyed});
  }
  const beforeDispose={...engine.stats(),texturesCreated,texturesDestroyed,buffersCreated,buffersDestroyed,oldCurrentRetained:engine.hasSource('source_0'),oldUnpinnedEvicted:!engine.hasSource('source_1')};
  engine.dispose();return {adapter:engine.info,budget:640<<20,snapshots,beforeDispose,afterDispose:{texturesCreated,texturesDestroyed,buffersCreated,buffersDestroyed},scope:'Explicit tracked source resources. Driver allocation and GC are not inferred from map sizes.'};
 });
 writeFileSync(new URL('resource-probe.json',import.meta.url),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
} finally {await browser.close();}
