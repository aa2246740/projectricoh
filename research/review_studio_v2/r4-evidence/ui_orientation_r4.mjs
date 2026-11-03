import assert from 'node:assert/strict';
import {readFile,writeFile,copyFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {launchPinnedChromium,pinnedRuntime,verifyPinnedRuntime} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
const root='/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r4';
process.env.TMPDIR=root;
const ready=JSON.parse(await readFile(root+'/server-ready.json','utf8'));
assert.notEqual(ready.port,49667);
const base=`http://127.0.0.1:${ready.port}`;
const R={runtime:verifyPinnedRuntime(),cases:[],errors:[]};
const browser=await launchPinnedChromium({env:{...process.env,TMPDIR:root}});
try{
 const processes=execFileSync('/bin/ps',['-axo','pid=,ppid=,command='],{encoding:'utf8'}).split(String.fromCharCode(10)).filter(s=>s.includes(pinnedRuntime.executablePath)&&s.includes('--user-data-dir='));
 const ours=processes.filter(s=>Number(s.trim().split(/\s+/)[1])===process.pid);
 assert.equal(ours.length,1,JSON.stringify(processes));
 const profile=ours[0].match(/--user-data-dir=([^ ]+)/)?.[1];
 assert.ok(profile?.startsWith(root+'/'),profile);
 R.browserProcess={nodePid:process.pid,command:ours[0].trim(),userDataDir:profile};
 const context=await browser.newContext({viewport:{width:1360,height:860}});
 const page=await context.newPage();page.setDefaultTimeout(180000);
 page.on('pageerror',e=>R.errors.push(String(e)));
 await page.goto(ready.url);
 const api=async(method,url,data)=>{
  const r=await page.request.fetch(base+url,{method,data,headers:{'X-GXR-Token':'independent-review-browser'}});
  assert.equal(r.status(),200,`${url} ${await r.text()}`);return r.json();
 };
 await api('PUT','/api/defaults/finish',{frame:{style:'none'},stamp:{enabled:false}});
 const photos=await api('GET','/api/photos');
 for(const name of ['PORTRAIT_JPG','PORTRAIT_PAIR']){
  const photo=photos.find(p=>p.name===name);assert.ok(photo);
  await api('DELETE',`/api/photos/${photo.id}/edit`);await api('DELETE',`/api/photos/${photo.id}/crop`);
  await page.goto(base+`/#/photo/${photo.id}`);await page.reload();
  await page.getByRole('tab',{name:'配方',exact:true}).waitFor();
  await page.waitForFunction(()=>{const i=document.querySelector('.pv-img');return i?.complete&&i.naturalWidth>0&&!document.querySelector('.status .right')?.textContent.includes('正在');});
  const preview=await page.locator('.pv-img').evaluate(i=>[i.naturalWidth,i.naturalHeight]);
  assert.deepEqual(preview,[480,640]);
  await page.getByRole('tab',{name:'导出',exact:true}).click();
  const size=page.getByRole('button',{name:'长边 2048 像素',exact:true});await size.click();
  assert.equal(await size.getAttribute('aria-pressed'),'true');
  const responsePromise=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/photos/${photo.id}/export`&&r.request().method()==='POST');
  await page.getByRole('button',{name:'导出',exact:true}).last().click();
  const response=await responsePromise;assert.equal(response.status(),200);
  const request=response.request().postDataJSON();assert.equal(request.long_edge,2048);assert.equal(request.source,'auto');
  const meta=await response.json();assert.deepEqual([meta.width,meta.height],[480,640]);
  await page.getByText('已导出 1 张',{exact:false}).waitFor();
  const artifact=`ui-${name}-2048-r4.jpg`;
  await copyFile(meta.path,root+'/evidence/'+artifact);
  await page.screenshot({path:root+`/evidence/ui-${name}-2048-r4.png`,fullPage:true});
  R.cases.push({name,hasRaw:photo.has_raw,hasJpg:photo.has_jpg,preview,request,status:response.status(),meta,artifact});
 }
 assert.deepEqual(R.errors,[]);
 await context.close();
}catch(e){R.failure=String(e.stack||e);process.exitCode=1;}
finally{await browser.close();await writeFile(root+'/evidence/ui-orientation-r4.json',JSON.stringify(R,null,2)+String.fromCharCode(10));console.log(JSON.stringify(R,null,2));}
