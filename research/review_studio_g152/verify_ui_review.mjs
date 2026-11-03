// Product modules in pinned headless Chromium, with isolated API responses.
import assert from 'node:assert/strict';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {join, basename, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {tmpdir} from 'node:os';
import {launchPinnedChromium, verifyPinnedRuntime} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';

const here=fileURLToPath(new URL('.',import.meta.url));
const assets=resolve(here,'../../studio/web/assets');
const scratch='/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-g152-r1';
const variant=process.env.REVIEW_UI_VARIANT||'original';
const reportStem=variant==='original'?'ui-review':'ui-review-'+variant;
assert.equal(tmpdir(),scratch);
const catalog=JSON.parse(await readFile(join(scratch,'ui_catalog.json'),'utf8'));
const frames=JSON.parse(await readFile(join(scratch,'ui_frames.json'),'utf8'));
const runtime=verifyPinnedRuntime();
const results=[], errors=[], requests=[], capsRequests=new Map();
let scenario='missing', saved=null, rev=0, holdCatalog=false, releaseCatalog=null, heldResolve=null, imported='ready';
let holdCaps=false,releaseCaps=null,heldCapsResolve=null;
const hasRaw=(id)=>!id.startsWith('jpg-');
function status(){
  const loaded=['ready','calibration_missing'].includes(scenario);
  return {ready:scenario==='ready',data_version:scenario==='ready'?'152-cal':loaded?'152-none':'none-none',
    camera_data:{state:loaded?'ready':scenario,generation:loaded?152:scenario==='unsupported'?154:null,
      message:scenario==='unsupported'?'不支持第 154 代相机配方文件。':'还没有导入相机配方文件'},
    calibration:{state:scenario==='ready'?'ready':'missing'}};
}
function listing(){return status().camera_data.state==='ready'?catalog:{units:catalog.units.map(u=>({...u,looks:[],users:[]}))};}
function check(name,actual,expected){
  let passed=true;try{assert.deepEqual(actual,expected);}catch{passed=false;}
  results.push({name,passed,actual,expected});
}
const browser=await launchPinnedChromium({args:['--single-process','--in-process-gpu','--no-zygote']});
const context=await browser.newContext({viewport:{width:1280,height:1600}});
const page=await context.newPage();
page.setDefaultTimeout(8000);
page.on('pageerror',e=>errors.push(String(e)));
const deadline=setTimeout(()=>{process.exitCode=124;void browser.close();},90000);
try{
  await page.route('**/*',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    const json=(value,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(value)});
    if(path==='/')return route.fulfill({contentType:'text/html',body:'<!doctype html><link rel="stylesheet" href="/assets/app.css"><main id="panel"></main><div id="toast-root"></div><div id="modal-root"></div>'});
    if(path.startsWith('/assets/')&&basename(path)===path.slice(8)){
      const location=variant==='fixed-scratch'&&['caps.js','preview.js'].includes(basename(path))?join(scratch,'patch-proof',basename(path)):join(assets,basename(path));
      return route.fulfill({contentType:path.endsWith('.css')?'text/css':'text/javascript',body:await readFile(location)});
    }
    if(path==='/api/camdata/status')return json(status());
    if(path==='/api/recipes'){
      const body=listing();
      if(holdCatalog){holdCatalog=false;return new Promise(done=>{releaseCatalog=async()=>{await json(body);done();};heldResolve();});}
      return json(body);
    }
    if(path==='/api/luts')return json({luts:[],groups:[]});
    if(path==='/api/frames')return json(frames);
    if(path==='/api/defaults/finish')return json({frame:null,stamp:null});
    if(path.endsWith('/capabilities')){
      const id=path.split('/')[3];capsRequests.set(id,(capsRequests.get(id)||0)+1);
      const body={raw:hasRaw(id),recipe:hasRaw(id)&&scenario==='ready'?'full':'none',reason:hasRaw(id)?scenario==='ready'?'':'还没有导入相机配方文件':'配方需要 RAW 文件'};
      if(holdCaps){holdCaps=false;return new Promise(done=>{releaseCaps=async()=>{await json(body);done();};heldCapsResolve();});}
      return json(body);
    }
    if(path.endsWith('/edit')){
      if(req.method()==='PUT'){requests.push(req.postDataJSON());saved=req.postDataJSON().recipe;rev++;}
      return json({rev,recipe:saved,render:{available:scenario==='ready'}});
    }
    if(path.includes('/render'))return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><rect width="16" height="16" fill="#888"/></svg>',headers:{'X-GXR-Label':'prediction','X-GXR-Calibrated':'0'}});
    if(path==='/api/camdata/import-upload'){
      scenario=imported;
      return scenario==='unsupported'?json({error:'generation_unsupported',message:'不支持第 154 代相机配方文件。'},422):json({message:'已导入相机配方文件'});
    }
    if(path==='/api/calibration/import'){
      scenario='ready';return json({message:'已导入校准数据'});
    }
    if(path==='/api/camdata/import-card'){
      const id=req.postDataJSON()?.card_id;
      if(!id)return json({error:'multiple_cards',message:'请选择存储卡',cards:[{id:'first',label:'第一张'},{id:'second',label:'第二张'}]},409);
      if(id==='first')return json({error:'dat_invalid',message:'无法导入相机配方文件。请从存储卡重新复制。'},422);
      scenario='ready';return json({message:'已导入相机配方文件'});
    }
    return json({error:'not_found'},404);
  });
  await page.goto('http://studio.review/');
  await page.evaluate(async()=>{
    const recipe=await import('/assets/recipes.js');
    const preview=await import('/assets/preview.js');
    const camera=await import('/assets/camdata.js');
    const caps=await import('/assets/caps.js');
    const shared=await import('/assets/state.js');
    window.r={recipe,preview,camera,caps,shared};
    window.show=async(id,raw=true)=>{
      if(window.view){document.getElementById('panel').replaceChildren();preview.disposeEdit(window.view);}
      await camera.loadCamdata();
      const view={photo:{id,has_raw:raw,lens:'GXR MOUNT A12'}};
      await preview.ensureEdit(view);
      view.redrawSide=()=>document.getElementById('panel').replaceChildren(recipe.recipePanel(view));
      window.view=view;view.redrawSide();
    };
    window.panel=()=>({text:document.getElementById('panel').innerText,
      guides:[...document.querySelectorAll('.camdata-guide h3')].map(e=>e.textContent),
      buttons:[...document.querySelectorAll('.base-grid button')].map(e=>({text:e.textContent,disabled:e.getAttribute('aria-disabled')==='true'}))});
  });
  for(const [state,id] of [['missing','state-missing'],['unsupported','state-unsupported'],['ready','jpg-state'],['calibration_missing','state-calibration'],['ready','state-ready']]){
    scenario=state;saved=null;
    await page.evaluate(async ({id})=>{await window.r.preview.loadCatalog({refresh:true});await window.show(id,!id.startsWith('jpg-'));},{id});
    const p=await page.evaluate(()=>window.panel());
    const isJpg=id.startsWith('jpg-');
    const expectedGuide=isJpg||state==='ready'?[]:[state==='missing'?'未导入相机配方文件':state==='unsupported'?'不支持第 154 代相机配方文件。':'未导入校准数据'];
    check('state/'+id,{guide:p.guides,rawReason:p.text.includes('配方需要 RAW 文件'),falseCardReason:p.text.includes('存储卡上没有相机配方文件'),
      count:p.buttons.length,enabled:p.buttons.some(b=>!b.disabled)},
      {guide:expectedGuide,rawReason:isJpg,falseCardReason:false,count:['ready','calibration_missing'].includes(state)?21:8,enabled:state==='ready'&&!isJpg});
  }
  let p=await page.evaluate(()=>window.panel());
  check('entry-order',p.buttons.slice(8).map(x=>x.text),[...catalog.units[2].looks,...catalog.units[2].users].map(x=>x.name));
  await page.getByRole('button',{name:'M9 STD',exact:true}).click();
  await page.evaluate(()=>window.r.preview.flushEdits(window.view));
  check('look-save-kind',requests.at(-1)?.recipe.kind,'look');
  await page.getByRole('slider',{name:'对比度',exact:true}).press('ArrowRight');
  await page.evaluate(()=>window.r.preview.flushEdits(window.view));
  await page.getByRole('button',{name:'HNCS HiCon',exact:true}).click();
  await page.evaluate(()=>window.r.preview.flushEdits(window.view));
  await page.getByRole('button',{name:'M9 STD',exact:true}).click();
  await page.evaluate(()=>window.r.preview.flushEdits(window.view));
  check('look-separate-memory',requests.at(-1)?.recipe.levels.contrast,1);
  await page.getByRole('button',{name:'FCC*002',exact:true}).click();
  await page.evaluate(()=>window.r.preview.flushEdits(window.view));
  check('user-save-kind',requests.at(-1)?.recipe.kind,'camera_user');
  await page.evaluate(()=>{window.view.ed.recipe.id='0'.repeat(64);window.view.redrawSide();});
  check('invalid-item-reselect-message',await page.getByText('找不到这个配方。请重新选择。',{exact:true}).count(),1);
  await page.getByRole('button',{name:'04 标准',exact:true}).click();
  await page.evaluate(()=>window.r.preview.flushEdits(window.view));
  check('invalid-item-can-reselect',requests.at(-1)?.recipe.kind,'builtin');
  for(const outcome of ['unsupported','ready']){
    scenario='missing';saved=null;imported=outcome;
    await page.evaluate(async id=>{await window.r.preview.loadCatalog({refresh:true});await window.show(id);},'import-'+outcome);
    await page.locator('input[type=file]').setInputFiles({name:'GXRCE.DAT',mimeType:'application/octet-stream',buffer:Buffer.from('review fixture')});
    await page.waitForFunction(outcome=>window.r.shared.state.camdata.state===(outcome==='ready'?'ready':'unsupported'),outcome);
    await page.waitForFunction(outcome=>outcome==='ready'?document.querySelectorAll('.base-grid button').length===21:document.querySelector('.camdata-guide h3')?.textContent.startsWith('不支持'),outcome);
    p=await page.evaluate(()=>window.panel());
    check('import-refresh/'+outcome,{count:p.buttons.length,enabled:p.buttons.some(b=>!b.disabled)},{count:outcome==='ready'?21:8,enabled:outcome==='ready'});
  }
  scenario='missing';saved=null;
  await page.evaluate(async()=>{await window.r.preview.loadCatalog({refresh:true});await window.show('multi');});
  await page.getByRole('button',{name:'从存储卡导入配方',exact:true}).click();
  await page.getByRole('button',{name:'从「第二张」导入',exact:true}).waitFor();
  check('multi-card-choices',await page.locator('.camdata-import .guide-actions button').allTextContents(),['从存储卡导入配方','选择文件…','从「第一张」导入','从「第二张」导入']);
  await page.getByRole('button',{name:'从「第二张」导入',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.base-grid button').length===21);
  check('multi-card-selected-import',(await page.evaluate(()=>window.panel())).buttons.some(b=>!b.disabled),true);

  // Earlier viewed photos must become usable after a successful import elsewhere.
  scenario='calibration_missing';saved=null;
  await page.evaluate(async()=>{await window.r.preview.loadCatalog({refresh:true});await window.show('earlier-raw');await window.show('current-raw');});
  await page.evaluate(()=>document.getElementById('panel').append(window.r.camera.calibrationImportForm({onDone:()=>window.r.preview.reloadEdit(window.view)})));
  await page.getByRole('textbox',{name:'校准数据文件夹',exact:true}).fill(scratch+'/calibration-fixture');
  await page.locator('[data-section="calibration"]').getByRole('button',{name:'导入校准数据',exact:true}).click();
  await page.waitForFunction(()=>window.r.shared.state.camdata.ready&&[...document.querySelectorAll('.base-grid button')].some(b=>b.getAttribute('aria-disabled')!=='true'));
  await page.evaluate(()=>window.show('earlier-raw'));
  p=await page.evaluate(()=>window.panel());
  const cachedPhoto={ready:await page.evaluate(()=>window.r.shared.state.camdata.ready),enabled:p.buttons.some(b=>!b.disabled),
    guides:p.guides,rawReason:p.text.includes('配方需要 RAW 文件'),capsRequests:capsRequests.get('earlier-raw')};
  check('previous-photo-after-import',cachedPhoto,{ready:true,enabled:true,guides:[],rawReason:false,capsRequests:2});
  if(!results.at(-1).passed)await page.screenshot({path:join(here,'previous-photo-after-import'+(variant==='original'?'':'-'+variant)+'.png'),fullPage:true});
  await page.evaluate(async()=>{await window.r.caps.loadPhotoCaps('earlier-raw',{refresh:true});await window.show('earlier-raw');});
  check('fresh-photo-caps-control',(await page.evaluate(()=>window.panel())).buttons.some(b=>!b.disabled),true);

  scenario='calibration_missing';
  await page.evaluate(()=>window.r.camera.loadCamdata());
  holdCaps=true;
  const heldCaps=new Promise(done=>{heldCapsResolve=done;});
  await page.evaluate(()=>{window.oldCaps=window.r.caps.loadPhotoCaps('pending-cap',{refresh:true});});
  await heldCaps;
  scenario='ready';
  await page.evaluate(()=>window.r.camera.loadCamdata());
  await releaseCaps();
  check('data-change-pending-caps',await page.evaluate(async()=>(await window.oldCaps).data.recipe),'full');

  // A data change while the old catalog is pending must invalidate that promise.
  scenario='missing';saved=null;
  await page.evaluate(()=>window.r.camera.loadCamdata());
  holdCatalog=true;
  const held=new Promise(done=>{heldResolve=done;});
  await page.evaluate(()=>{window.oldCatalog=window.r.preview.loadCatalog({refresh:true});});
  await held;
  scenario='ready';
  await page.evaluate(()=>window.r.camera.loadCamdata());
  await releaseCatalog();
  const stale=await page.evaluate(async()=>{await window.oldCatalog;return window.r.shared.state.catalog?.units[2].looks.length??null;});
  check('data-change-pending-catalog',stale,10);
  await page.evaluate(()=>window.r.preview.loadCatalog({refresh:true}));
  check('explicit-catalog-refresh-control',await page.evaluate(()=>window.r.shared.state.catalog.units[2].looks.length),10);
  check('page-errors',errors,[]);
}finally{
  clearTimeout(deadline);
  const visibleToasts=await page.locator('#toast-root .toast').allTextContents().catch(()=>[]);
  await context.close();await browser.close();
  const report={variant,runtime,profile_parent:tmpdir(),api_responses:'isolated fixtures, real product modules',results,errors,visible_toasts:visibleToasts,
    passed:results.filter(r=>r.passed).length,failed:results.filter(r=>!r.passed).length};
  await writeFile(join(here,reportStem+'.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({passed:report.passed,failed:report.failed,failures:results.filter(r=>!r.passed)}));
  if(report.failed)process.exitCode=1;
}
