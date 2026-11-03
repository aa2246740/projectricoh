import{readFile,writeFile}from'node:fs/promises';
import{launchPinnedChromium}from'/Users/wu/.codex/playwright-runtime/runtime.mjs';
const root='/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r2';process.env.TMPDIR=root;
const ready=JSON.parse(await readFile(root+'/server-ready.json','utf8'));if(ready.port===49667)throw Error('forbidden port');
const base=`http://127.0.0.1:${ready.port}`;const R={latency:[],errors:[],renderRequests:[]};
const browser=await launchPinnedChromium({env:{...process.env,TMPDIR:root}});
try{
 const context=await browser.newContext({viewport:{width:1360,height:860}});const page=await context.newPage();page.setDefaultTimeout(60000);
 page.on('pageerror',e=>R.errors.push(String(e)));
 page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/render?'))R.renderRequests.push({url:r.url(),body:r.postDataJSON()});});
 const api=async(method,url,data)=>{const r=await page.request.fetch(base+url,{method,data,headers:{'X-GXR-Token':'independent-review-browser'}});if(!r.ok())throw Error(`${url} ${r.status()} ${await r.text()}`);return r.json();};
 await page.goto(ready.url);const photos=await api('GET','/api/photos');const raw=photos.find(x=>x.name==='R8051219').id;const jpg=photos.find(x=>x.name==='REVIEW').id;
 const waitImage=()=>page.waitForFunction(()=>{const i=document.querySelector('.pv-img');return i?.complete&&i.naturalWidth>0&&!document.querySelector('.status .right')?.textContent.includes('正在');});
 const open=async id=>{await page.goto(base+`/#/photo/${id}`);await page.reload();await page.getByRole('tab',{name:'配方',exact:true}).waitFor();await waitImage();};
 await api('PUT','/api/defaults/finish',{frame:{style:'none'},stamp:{enabled:false}});
 for(let n=0;n<5;n++){
  await api('DELETE',`/api/photos/${raw}/edit`);await api('DELETE',`/api/photos/${raw}/crop`);await open(raw);
  const enter=page.waitForResponse(r=>r.url().includes('stage=uncropped')&&r.request().method()==='POST');
  await page.getByRole('tab',{name:'裁剪',exact:true}).click();await enter;await waitImage();
  const slider=page.getByRole('slider',{name:'垂直',exact:true});const box=await slider.boundingBox();const old=await page.locator('.pv-img').getAttribute('src');
  const saved=page.waitForResponse(r=>r.url().endsWith(`/api/photos/${raw}/edit`)&&r.request().method()==='PUT');
  const cropSaved=page.waitForResponse(r=>r.url().endsWith(`/api/photos/${raw}/crop`)&&r.request().method()==='PUT');
  await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*(.56+n*.01),box.y+box.height*.5);
  const start=performance.now();await page.mouse.up();
  await page.waitForFunction(old=>{const i=document.querySelector('.pv-img');return i?.src!==old&&i?.complete&&i.naturalWidth>0;},old);
  const seconds=(performance.now()-start)/1000;const a=await saved;const b=await cropSaved;
  R.latency.push({seconds,saveStatus:a.status(),cropStatus:b.status(),image:await page.locator('.pv-img').evaluate(i=>[i.naturalWidth,i.naturalHeight])});
 }
 // A restore followed by Undo must recover the original inherited state as well as the current pixels.
 await api('DELETE',`/api/photos/${jpg}/edit`);await api('DELETE',`/api/photos/${jpg}/crop`);
 await api('PUT','/api/defaults/finish',{frame:{style:'gallery'},stamp:{enabled:true,content:'text',font:'sans',text:'FIRST'}});
 await open(jpg);R.beforeRestore=await api('GET',`/api/photos/${jpg}/edit`);
 const restored=page.waitForResponse(r=>r.url().endsWith(`/api/photos/${jpg}/crop`)&&r.request().method()==='PUT');
 await page.getByRole('button',{name:'复原',exact:true}).click();await restored;await waitImage();
 const undo=page.waitForResponse(r=>r.url().endsWith(`/api/photos/${jpg}/edit`)&&r.request().method()==='PUT');
 await page.getByRole('button',{name:'撤销',exact:true}).click();await undo;await waitImage();R.afterUndo=await api('GET',`/api/photos/${jpg}/edit`);
 await api('PUT','/api/defaults/finish',{frame:{style:'leica'},stamp:{enabled:true,content:'text',font:'sans',text:'SECOND'}});
 await page.reload();await waitImage();R.afterDefaultsChange=await page.locator('.pv-img').evaluate(i=>[i.naturalWidth,i.naturalHeight]);
 await page.screenshot({path:root+'/evidence/ui-undo-inheritance-r2.png',fullPage:true});
 await api('PUT','/api/defaults/finish',{frame:{style:'none'},stamp:{enabled:false}});
 await context.close();
}catch(e){R.failure=String(e.stack||e);process.exitCode=1;}
finally{await browser.close();await writeFile(root+'/evidence/ui-latency-defaults-r2.json',JSON.stringify(R,null,2)+'\n');console.log(JSON.stringify(R,null,2));}
