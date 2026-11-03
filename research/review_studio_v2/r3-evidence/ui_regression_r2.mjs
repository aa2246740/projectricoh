import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {launchPinnedChromium} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
const root='/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r3';
const out=path.join(root,'evidence');process.env.TMPDIR=root;
const ready=JSON.parse(await readFile(path.join(root,'server-ready.json'),'utf8'));
if(ready.port===49667)throw Error('forbidden port');
const base=`http://127.0.0.1:${ready.port}`;
const browser=await launchPinnedChromium({env:{...process.env,TMPDIR:root}});
const R={errors:[],exports:[],requests:[]};
try{
 const context=await browser.newContext({viewport:{width:1360,height:860}});
 const page=await context.newPage();page.setDefaultTimeout(60000);
 page.on('pageerror',e=>R.errors.push(String(e)));
 page.on('request',r=>{if(r.url().endsWith('/export')&&r.method()==='POST')R.requests.push({url:r.url(),body:r.postDataJSON()});});
 const api=async(method,url,data)=>{
  const r=await page.request.fetch(base+url,{method,data,headers:{'X-GXR-Token':'independent-review-browser'}});
  if(!r.ok())throw Error(`${url} ${r.status()} ${await r.text()}`);return r.json();
 };
 await page.goto(ready.url);
 const photos=await api('GET','/api/photos');
 const raw=photos.find(p=>p.name==='R8051219').id;
 const jpg=photos.find(p=>p.name==='REVIEW').id;
 const waitImage=()=>page.waitForFunction(()=>{const i=document.querySelector('.pv-img');return i?.complete&&i.naturalWidth>0&&!document.querySelector('.status .right')?.textContent.includes('正在');});
 const open=async id=>{await page.goto(base+`/#/photo/${id}`);await page.reload();await page.getByRole('tab',{name:'配方',exact:true}).waitFor();await waitImage();};
 const snap=n=>page.screenshot({path:path.join(out,n),fullPage:true});
 await api('DELETE',`/api/photos/${raw}/edit`);await api('DELETE',`/api/photos/${raw}/crop`);
 await api('PUT','/api/defaults/finish',{frame:{style:'none'},stamp:{enabled:false}});
 await open(raw);
 R.rawEditBefore=await api('GET',`/api/photos/${raw}/edit`);
 R.rawPreview=await page.locator('.pv-img').evaluate(i=>({src:i.src,wh:[i.naturalWidth,i.naturalHeight]}));
 await page.getByRole('tab',{name:'导出',exact:true}).click();
 const exp=page.waitForResponse(r=>r.url().endsWith(`/api/photos/${raw}/export`)&&r.request().method()==='POST');
 await page.getByRole('button',{name:'导出',exact:true}).last().click();
 const response=await exp;R.exports.push({status:response.status(),body:await response.json()});
 await page.getByText('已导出 1 张',{exact:false}).last().waitFor();
 await snap('ui-export-complete-r2.png');
 // Invalid user-chosen destination: record whether the API's detail survives the export panel.
 await page.getByRole('textbox',{name:'导出到',exact:true}).fill(path.join(root,'library'));
 const failed=page.waitForResponse(r=>r.url().endsWith(`/api/photos/${raw}/export`)&&r.request().method()==='POST');
 await page.getByRole('button',{name:'导出',exact:true}).last().click();
 const failure=await failed;R.exportFailure={status:failure.status(),body:await failure.json()};
 await page.getByText('无法导出到这个位置。请换一个文件夹。',{exact:true}).waitFor();
 R.exportFailure.visible=await page.locator('.side-body').innerText();R.exportFailure.detailsCount=await page.locator('.side-body details').count();
 await snap('ui-export-error-r2.png');
 await api('PUT',`/api/photos/${raw}/edit`,{recipe:{unit:'jlaunch',slot:8}});
 await open(raw);R.predictionBadge=await page.locator('.status').innerText();
 await snap('ui-prediction-label-r2.png');
 // A malformed LUT is sent through the actual file input and backend parser.
 await page.goto(base+'/#/recipes');
 await page.locator('input[type=file][accept=".cube,text/plain"]').waitFor({state:'attached'});
 const upload=page.waitForResponse(r=>r.url().endsWith('/api/lut/upload')&&r.request().method()==='POST');
 await page.locator('input[type=file][accept=".cube,text/plain"]').setInputFiles({name:'broken.cube',mimeType:'text/plain',buffer:Buffer.from('LUT_3D_SIZE 2\ninvalid\n')});
 const bad=await upload;R.lutFailure={status:bad.status(),body:await bad.json()};
 const detail=page.locator('details.err-detail').first();await detail.waitFor();
 R.lutFailure.initialOpen=await detail.getAttribute('open');R.lutFailure.text=await detail.innerText();
 await snap('ui-error-details-closed-r2.png');await detail.locator('summary').click();
 R.lutFailure.open=await detail.evaluate(e=>e.open);await snap('ui-error-details-open-r2.png');
 // Exercise both disabled and enabled stamp settings and expanded crop controls.
 await api('PUT',`/api/photos/${jpg}/edit`,{stamp:{enabled:true,content:'date+text',text:'上海 GXR',font:'sans',show_time:true}});
 await open(jpg);await page.getByRole('tab',{name:'时间戳',exact:true}).click();await waitImage();
 await snap('ui-stamp-enabled-r2.png');
 await page.getByRole('tab',{name:'裁剪',exact:true}).click();await waitImage();await snap('ui-crop-r2.png');
 await page.setViewportSize({width:1024,height:768});await snap('ui-crop-1024-r2.png');
 R.overflow=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
 await context.close();
}catch(e){R.failure=String(e.stack||e);process.exitCode=1;}
finally{await browser.close();await writeFile(path.join(out,'ui-regression-r2.json'),JSON.stringify(R,null,2)+'\n');console.log(JSON.stringify(R,null,2));}
