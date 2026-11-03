import {readFile,writeFile} from 'node:fs/promises';
import {launchPinnedChromium} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
const root='/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r3';process.env.TMPDIR=root;
const ready=JSON.parse(await readFile(root+'/server-ready.json','utf8'));if(ready.port===49667)throw Error('forbidden port');
const base=`http://127.0.0.1:${ready.port}`;const R={errors:[],exportRequests:[],states:[]};
const browser=await launchPinnedChromium({env:{...process.env,TMPDIR:root}});
try{
 const context=await browser.newContext({viewport:{width:1360,height:860}});const page=await context.newPage();page.setDefaultTimeout(60000);
 page.on('pageerror',e=>R.errors.push(String(e)));page.on('request',r=>{if(r.method()==='POST'&&/\/export$/.test(new URL(r.url()).pathname))R.exportRequests.push({url:r.url(),body:r.postDataJSON()});});
 const api=async(method,url,data)=>{const r=await page.request.fetch(base+url,{method,data,headers:{'X-GXR-Token':'independent-review-browser'}});if(!r.ok())throw Error(`${url} ${r.status()} ${await r.text()}`);return r.json();};
 await page.goto(ready.url);const photos=await api('GET','/api/photos');const jpg=photos.find(p=>p.name==='REVIEW').id;
 const waitImage=()=>page.waitForFunction(()=>{const i=document.querySelector('.pv-img');return i?.complete&&i.naturalWidth>0&&!document.querySelector('.status .right')?.textContent.includes('正在');});
 const open=async id=>{await page.goto(base+`/#/photo/${id}`);await page.reload();await page.getByRole('tab',{name:'配方',exact:true}).waitFor();await waitImage();};
 const state=async label=>{const edit=await api('GET',`/api/photos/${jpg}/edit`);R.states.push({label,frame:edit.frame,stamp:edit.stamp,adjust:edit.adjust,image:await page.locator('.pv-img').evaluate(i=>[i.naturalWidth,i.naturalHeight])});};
 for(const original of ['inherited','explicit_off']){
  await api('DELETE',`/api/photos/${jpg}/edit`);await api('DELETE',`/api/photos/${jpg}/crop`);
  await api('PUT','/api/defaults/finish',{frame:{style:'gallery'},stamp:{enabled:true,content:'text',text:'FIRST',font:'sans'}});
  if(original==='explicit_off')await api('PUT',`/api/photos/${jpg}/edit`,{frame:{style:'none'},stamp:{enabled:false},adjust:{exposure_ev:0.7}});
  await open(jpg);await state(original+'_before');
  const restored=page.waitForResponse(r=>r.url().endsWith(`/api/photos/${jpg}/crop`)&&r.request().method()==='PUT');
  await page.getByRole('button',{name:'复原',exact:true}).click();await restored;await waitImage();await state(original+'_restored');
  const undone=page.waitForResponse(r=>r.url().endsWith(`/api/photos/${jpg}/edit`)&&r.request().method()==='PUT');
  await page.getByRole('button',{name:'撤销',exact:true}).click();await undone;await waitImage();await state(original+'_undone');
  await api('PUT','/api/defaults/finish',{frame:{style:'leica'},stamp:{enabled:true,content:'text',text:'SECOND',font:'sans'}});
  await page.reload();await waitImage();await state(original+'_new_defaults');
 }
 await api('PUT','/api/defaults/finish',{frame:{style:'none'},stamp:{enabled:false}});
 const portrait=photos.find(p=>p.name==='PORTRAIT_JPG').id;
 await api('DELETE',`/api/photos/${portrait}/edit`);await api('DELETE',`/api/photos/${portrait}/crop`);
 await open(portrait);R.portraitPreview=await page.locator('.pv-img').evaluate(i=>[i.naturalWidth,i.naturalHeight]);
 await page.getByRole('tab',{name:'导出',exact:true}).click();await page.getByRole('button',{name:'长边 2048 像素',exact:true}).click();
 const exp=page.waitForResponse(r=>r.url().endsWith(`/api/photos/${portrait}/export`)&&r.request().method()==='POST');await page.getByRole('button',{name:'导出',exact:true}).last().click();
 const response=await exp;R.portraitExport={status:response.status(),body:await response.json()};await page.getByText('已导出 1 张',{exact:false}).waitFor();
 await page.screenshot({path:root+'/evidence/ui-portrait-sized-export-r3.png',fullPage:true});
 // Select two real gallery entries and submit via the real batch UI.
 for(const name of ['R8051219','REVIEW']){const id=photos.find(p=>p.name===name).id;await api('DELETE',`/api/photos/${id}/edit`);await api('DELETE',`/api/photos/${id}/crop`);}
 await page.goto(base+'/#/photos');await page.reload();
 for(const name of ['R8051219','REVIEW'])await page.getByRole('checkbox',{name:`选中 ${name}`,exact:true}).check();
 await page.getByRole('button',{name:'导出',exact:true}).click();
 const start=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/export'&&r.request().method()==='POST');await page.getByRole('button',{name:'导出',exact:true}).last().click();const successStart=await start;R.batchStart={status:successStart.status(),body:await successStart.json()};
 await page.getByText('已导出 2 张',{exact:false}).waitFor();R.batchSuccess=await api('GET',`/api/jobs/${R.batchStart.body.id}`);
 await page.getByRole('textbox',{name:'导出到',exact:true}).fill(root+'/library');
 const bad=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/export'&&r.request().method()==='POST');await page.getByRole('button',{name:'导出',exact:true}).last().click();const badStart=await bad;const badJob=await badStart.json();
 await page.getByText('已导出 0 张',{exact:false}).waitFor();R.batchFailure=await api('GET',`/api/jobs/${badJob.id}`);
 const details=page.locator('.export-list details');R.batchErrors={visible:await page.locator('.export-list').innerText(),detailsCount:await details.count(),open:await details.evaluateAll(es=>es.map(e=>e.open))};
 await page.screenshot({path:root+'/evidence/ui-batch-errors-r3.png',fullPage:true});
 await context.close();
}catch(e){R.failure=String(e.stack||e);process.exitCode=1;}
finally{await browser.close();await writeFile(root+'/evidence/ui-extra-r3.json',JSON.stringify(R,null,2)+'\n');console.log(JSON.stringify(R,null,2));}
