import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {launchPinnedChromium} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
// Claim: elapsed time from pointerup to a decoded and painted image for the committed vertical value.
const root='/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r3';process.env.TMPDIR=root;
const ready=JSON.parse(await readFile(root+'/server-ready.json','utf8'));if(ready.port===49667)throw Error('forbidden port');const base=`http://127.0.0.1:${ready.port}`;
const R={claim:'pointerup to decoded image and two animation frames; verify displayed blob matches a successful request for committed value',loadBefore:execFileSync('/usr/bin/uptime',{encoding:'utf8'}).trim(),runs:[],errors:[]};
const browser=await launchPinnedChromium({env:{...process.env,TMPDIR:root}});
try{
 const ctx=await browser.newContext({viewport:{width:1360,height:860}});const page=await ctx.newPage();page.setDefaultTimeout(60000);page.on('pageerror',e=>R.errors.push(String(e)));
 const api=async(method,url,data)=>{const r=await page.request.fetch(base+url,{method,data,headers:{'X-GXR-Token':'independent-review-browser'}});if(!r.ok())throw Error(`${url} ${r.status()} ${await r.text()}`);return r.json();};
 await page.goto(ready.url);const photos=await api('GET','/api/photos');const raw=photos.find(x=>x.name==='R8051219').id;
 const waitImage=()=>page.waitForFunction(()=>{const i=document.querySelector('.pv-img');return i?.complete&&i.naturalWidth>0&&!document.querySelector('.status .right')?.textContent.includes('正在');});
 await api('PUT','/api/defaults/finish',{frame:{style:'none'},stamp:{enabled:false}});
 for(let n=0;n<5;n++){
  await api('DELETE',`/api/photos/${raw}/edit`);await api('DELETE',`/api/photos/${raw}/crop`);
  await page.goto(base+`/#/photo/${raw}`);await page.reload();await page.getByRole('tab',{name:'配方',exact:true}).waitFor();await waitImage();
  const enter=page.waitForResponse(r=>r.url().includes('stage=uncropped')&&r.request().method()==='POST');await page.getByRole('tab',{name:'裁剪',exact:true}).click();await enter;await waitImage();
  const slider=page.getByRole('slider',{name:'垂直',exact:true});const box=await slider.boundingBox();const old=await page.locator('.pv-img').getAttribute('src');
  const replies=[];const pending=[];const collect=r=>{if(r.request().method()==='POST'&&r.url().includes('/render?'))pending.push((async()=>{const bytes=await r.body();replies.push({url:r.url(),status:r.status(),body:r.request().postDataJSON(),sha256:createHash('sha256').update(bytes).digest('hex'),timing:r.request().timing()});})());};page.on('response',collect);
  await page.evaluate(old=>{
   window.__r3={old,release:null,display:null};
   window.addEventListener('pointerup',()=>{window.__r3.release=performance.now();},{once:true,capture:true});
   document.querySelector('.pv-img').addEventListener('load',function onload(){
    if(this.src===old||window.__r3.release===null)return;
    const decoded=performance.now();requestAnimationFrame(()=>requestAnimationFrame(()=>{window.__r3.display={decoded,painted:performance.now(),src:this.src,width:this.naturalWidth,height:this.naturalHeight};}));
    this.removeEventListener('load',onload);
   });
  },old);
  const saved=page.waitForResponse(r=>r.url().endsWith(`/api/photos/${raw}/edit`)&&r.request().method()==='PUT');
  await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*(.56+n*.01),box.y+box.height*.5);await page.mouse.up();
  await page.waitForFunction(()=>window.__r3?.display!==null);
  const display=await page.evaluate(async()=>{const r=window.__r3;const bytes=await (await fetch(r.display.src)).arrayBuffer();const sha256=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');return {seconds:(r.display.painted-r.release)/1000,decodedSeconds:(r.display.decoded-r.release)/1000,wh:[r.display.width,r.display.height],sha256};});
  const save=await saved;const edit=await save.json();await page.waitForLoadState('networkidle');page.off('response',collect);await Promise.all(pending);
  const matches=replies.filter(r=>r.sha256===display.sha256);const row={...display,saveStatus:save.status(),savedVertical:edit.geometry?.vertical,matchedResponse:matches,allRenderResponses:replies};
  row.workVerified=matches.some(r=>r.status===200&&r.body.geometry?.vertical===edit.geometry?.vertical&&r.url.includes('stage=uncropped')&&r.url.includes('size=preview'));
  if(!row.workVerified)throw Error('Displayed image did not match the committed geometry');R.runs.push(row);
 }
 R.loadAfter=execFileSync('/usr/bin/uptime',{encoding:'utf8'}).trim();await ctx.close();
}catch(e){R.failure=String(e.stack||e);process.exitCode=1;}
finally{await browser.close();await writeFile(root+'/evidence/ui-latency-r3.json',JSON.stringify(R,null,2)+'\n');console.log(JSON.stringify(R,null,2));}
