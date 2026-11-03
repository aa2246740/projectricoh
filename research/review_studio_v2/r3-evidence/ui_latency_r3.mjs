import {readFile,writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {launchPinnedChromium} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
const root='/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r3';process.env.TMPDIR=root;
const ready=JSON.parse(await readFile(root+'/server-ready.json','utf8'));if(ready.port===49667)throw Error('forbidden port');const base=`http://127.0.0.1:${ready.port}`;
const R={claim:'pointerup to first paint of final visible image; native fetch blob provenance must match successful render of saved geometry; no network-idle wait counted',loadBefore:execFileSync('/usr/bin/uptime',{encoding:'utf8'}).trim(),runs:[],errors:[]};
const browser=await launchPinnedChromium({env:{...process.env,TMPDIR:root}});
try{
 const context=await browser.newContext({viewport:{width:1360,height:860}});const page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',e=>R.errors.push(String(e)));
 await page.addInitScript(()=>{
  const fetchNative=window.fetch.bind(window),createNative=URL.createObjectURL.bind(URL),blobMeta=new WeakMap();window.__r3Blobs=new Map();
  window.fetch=async(input,init)=>{
   const response=await fetchNative(input,init);const url=String(input);
   if(url.includes('/render?')){
    const original=response.blob.bind(response);
    response.blob=async()=>{const blob=await original();blobMeta.set(blob,{url,status:response.status,body:init?.body?JSON.parse(init.body):null});return blob;};
   }
   return response;
  };
  URL.createObjectURL=blob=>{const url=createNative(blob);window.__r3Blobs.set(url,{blob,meta:blobMeta.get(blob)});return url;};
 });
 const api=async(method,url,data)=>{const r=await page.request.fetch(base+url,{method,data,headers:{'X-GXR-Token':'independent-review-browser'}});if(!r.ok())throw Error(`${url} ${r.status()} ${await r.text()}`);return r.json();};
 await page.goto(ready.url);const photos=await api('GET','/api/photos');const raw=photos.find(x=>x.name==='R8051219').id;
 const waitImage=()=>page.waitForFunction(()=>{const i=document.querySelector('.pv-img');return i?.complete&&i.naturalWidth>0&&!document.querySelector('.status .right')?.textContent.includes('正在');});
 await api('PUT','/api/defaults/finish',{frame:{style:'none'},stamp:{enabled:false}});
 for(let n=0;n<5;n++){
  await api('DELETE',`/api/photos/${raw}/edit`);await api('DELETE',`/api/photos/${raw}/crop`);
  await page.goto(base+`/#/photo/${raw}`);await page.reload();await page.getByRole('tab',{name:'配方',exact:true}).waitFor();await waitImage();
  const enter=page.waitForResponse(r=>r.url().includes('stage=uncropped')&&r.request().method()==='POST');await page.getByRole('tab',{name:'裁剪',exact:true}).click();await enter;await waitImage();
  const slider=page.getByRole('slider',{name:'垂直',exact:true}),box=await slider.boundingBox(),old=await page.locator('.pv-img').getAttribute('src');
  await page.evaluate(old=>{
   window.__r3={release:null,displays:[]};window.addEventListener('pointerup',()=>{window.__r3.release=performance.now();},{once:true,capture:true});
   document.addEventListener('load',event=>{const image=event.target;if(!image.matches?.('.pv-img')||image.src===old||window.__r3.release===null)return;
    const decoded=performance.now();requestAnimationFrame(()=>requestAnimationFrame(()=>{const current=document.querySelector('.pv-img');if(!current?.complete||current.src!==image.src)return;window.__r3.displays.push({decoded,painted:performance.now(),src:image.src,wh:[image.naturalWidth,image.naturalHeight]});}));
   },true);
  },old);
  const saved=page.waitForResponse(r=>r.url().endsWith(`/api/photos/${raw}/edit`)&&r.request().method()==='PUT').catch(e=>{R.saveWaitFailure=String(e);return null;});
  await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*(.56+n*.01),box.y+box.height*.5);await page.mouse.up();
  await page.waitForFunction(()=>window.__r3?.displays?.length>0);const save=await saved;if(!save)throw Error('save missing');const edit=await save.json();await page.waitForLoadState('networkidle');
  const display=await page.evaluate(async()=>{
   const obs=window.__r3,current=document.querySelector('.pv-img'),shown=obs.displays.find(d=>d.src===current.src);if(!shown)throw Error('no paint observation for current image');
   const source=window.__r3Blobs.get(current.src);if(!source?.meta)throw Error('missing native fetch provenance');
   const bytes=await source.blob.arrayBuffer();const sha256=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');
   return {seconds:(shown.painted-obs.release)/1000,decodedSeconds:(shown.decoded-obs.release)/1000,wh:shown.wh,sha256,source:source.meta,visibleImageCount:obs.displays.length};
  });
  const row={...display,saveStatus:save.status(),savedVertical:edit.geometry?.vertical};row.workVerified=row.saveStatus===200&&row.source.status===200&&row.source.body.geometry?.vertical===row.savedVertical&&row.source.url.includes('stage=uncropped')&&row.source.url.includes('size=preview');R.runs.push(row);if(!row.workVerified)throw Error('visible blob is not the saved render');
 }
 R.loadAfter=execFileSync('/usr/bin/uptime',{encoding:'utf8'}).trim();await context.close();
}catch(e){R.failure=String(e.stack||e);process.exitCode=1;}
finally{await writeFile(root+'/evidence/ui-latency-r3.json',JSON.stringify(R,null,2)+'\n');await browser.close();console.log(JSON.stringify(R,null,2));}
