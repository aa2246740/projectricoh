import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {launchPinnedChromium,pinnedRuntime} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
const scratch='/Volumes/Workspace/Scratch/tmp/projectricoh/probe-pack-r2/page';
const output=path.join(here,'local/page');
const mount=execFileSync('/usr/sbin/diskutil',['info','-plist','/Volumes/Workspace'],{encoding:'utf8'});
if (!mount.includes('14BE04EB-AF49-497E-B36A-B078B2F7C5E8') ||
    !/<key>FilesystemType<\/key>\s*<string>apfs<\/string>/.test(mount) ||
    !/<key>WritableVolume<\/key>\s*<true\/>/.test(mount)) throw new Error('Workspace volume guard failed');
await fs.mkdir(scratch,{recursive:true});await fs.mkdir(output,{recursive:true});
const lock=await fs.open(path.join(scratch,'verify.lock'),'wx');
const run=await fs.mkdtemp(path.join(scratch,'browser-'));process.env.TMPDIR=run;
const plan=JSON.parse(await fs.readFile(path.join(here,'local/page-plan.json'),'utf8'));
const html=await fs.readFile(path.join(here,'ramp2.html'));
const digest=createHash('sha256').update(html).digest('hex');
let browser,closed=false;const checks=[],errors=[],requests=[];
const assert=(ok,message)=>{if(!ok)throw new Error(message);};
try {
  assert(pinnedRuntime.playwrightVersion==='1.61.1'&&pinnedRuntime.chromiumRevision==='1228','Pinned runtime mismatch');
  browser=await launchPinnedChromium({args:['--renderer-process-limit=1'],downloadsPath:run,artifactsDir:run});
  assert(browser.version()===pinnedRuntime.chromiumVersion,'Chromium version mismatch');
  const context=await browser.newContext({offline:true,serviceWorkers:'block',deviceScaleFactor:1,viewport:{width:864,height:900}});
  const page=await context.newPage();
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  page.on('request',r=>{if(!r.url().startsWith('file:'))requests.push(r.url());});
  await page.goto(pathToFileURL(path.join(here,'ramp2.html')).href);
  await page.evaluate(()=>document.fonts.ready);
  const cases=[[864,900,false],[864,900,true],[900,650,false],[800,600,false],[800,600,true],
    [720,450,false],[720,450,true],[1440,900,true],[390,844,false]];
  for(const phase of ['p1','p2']) {
    await page.keyboard.press(phase==='p1'?'1':'2');
    for(const [width,height,capture] of cases) {
      await page.setViewportSize({width,height});
      const active=await page.locator('#capture').getAttribute('aria-pressed')==='true';
      if(active!==capture)await page.locator('#capture').click();
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      const result=await page.evaluate(()=>{
        const b=el=>{const r=el.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};};
        const inside=(a,c)=>a.x>=c.x-.1&&a.y>=c.y-.1&&a.x+a.w<=c.x+c.w+.1&&a.y+a.h<=c.y+c.h+.1;
        const overlap=(a,c)=>Math.min(a.x+a.w,c.x+c.w)>Math.max(a.x,c.x)+.1&&Math.min(a.y+a.h,c.y+c.h)>Math.max(a.y,c.y)+.1;
        const v={x:0,y:0,w:innerWidth,h:innerHeight};
        return {phase:document.querySelector('#board').dataset.phase,width:innerWidth,height:innerHeight,
          capture:document.body.classList.contains('capturing'),board:b(document.querySelector('#board')),
          overflow:document.documentElement.scrollWidth>innerWidth||document.documentElement.scrollHeight>innerHeight+1,
          fullscreen:Boolean(document.fullscreenElement),layout:window.rampLayout(),
          markers:[...document.querySelectorAll('.marker')].map(el=>({corner:el.dataset.corner,box:b(el),visible:inside(b(el),v)})),
          patches:[...document.querySelectorAll('.patch')].map(el=>{
            const sw=el.querySelector('.swatch'),sample=b(el.querySelector('.sample')),caption=b(el.querySelector('.caption'));
            return {id:el.dataset.patchId,rgb:el.dataset.rgb,css:getComputedStyle(sw).backgroundColor,
              swatch:b(sw),sample,caption,fullyVisible:inside(b(el),v),sampleWithinSwatch:inside(sample,b(sw)),
              labelOverSample:overlap(caption,sample),captionOverflow:el.querySelector('.caption').scrollWidth>el.querySelector('.caption').clientWidth+1};
          })};
      });
      const name=`${phase}-${width}x${height}-${capture?'capture':'normal'}`;
      assert(result.phase===phase&&result.capture===capture&&!result.fullscreen,`${name}: mode mismatch`);
      assert(result.layout.grayLevels.length===49&&result.patches.length===52&&result.markers.length===4,`${name}: count mismatch`);
      assert(JSON.stringify(result.layout.grayLevels)===JSON.stringify(plan.pages[phase].codes),`${name}: grey codes differ from plan`);
      assert(!result.overflow&&result.board.w<=640.1,`${name}: overflow/board cap`);
      assert(result.markers.every(m=>m.visible),`${name}: marker cropped`);
      assert(result.patches.every(p=>p.fullyVisible&&p.sampleWithinSwatch&&!p.labelOverSample&&!p.captionOverflow),`${name}: sampling or labels`);
      assert(result.patches.every(p=>p.sample.w>=8&&p.sample.h>=8&&p.css===`rgb(${p.rgb.split(',').join(', ')})`),`${name}: sample/color mismatch`);
      for(const color of plan.pages[phase].colors)assert(result.patches.find(p=>p.id===color.id).rgb===color.rgb.join(','),`${name}: chromatic patch mismatch`);
      await page.screenshot({path:path.join(output,name+'.png'),fullPage:false});
      await fs.writeFile(path.join(output,name+'.json'),JSON.stringify(result,null,2)+'\n');
      if(width===864&&height===900&&!capture)await fs.writeFile(path.join(output,'layout-'+phase+'.json'),JSON.stringify(result.layout,null,2)+'\n');
      checks.push({name,phase,status:'PASS',board:result.board});
    }
  }
  // Changing only chart phase while capturing must not move its geometry.
  await page.locator('main').click({position:{x:1,y:1}});await page.keyboard.press('Space');
  assert(await page.locator('#capture').getAttribute('aria-pressed')==='true','Space capture failed');
  const before=await page.locator('#board').boundingBox();await page.keyboard.press('1');
  assert(await page.evaluate(()=>window.rampLayout().phase)==='p1','P1 shortcut failed');
  await page.keyboard.press('2');const after=await page.locator('#board').boundingBox();
  assert(JSON.stringify(before)===JSON.stringify(after),'Phase change moved the chart');
  await page.keyboard.press('Escape');
  assert(await page.locator('#capture').getAttribute('aria-pressed')==='false','Escape failed');
  await page.locator('#fullscreen').click();
  await page.waitForFunction(()=>Boolean(document.fullscreenElement)||document.querySelector('#fullscreen').textContent.includes('不可用'),null,{timeout:5000});
  const fullscreenWorked=await page.evaluate(()=>Boolean(document.fullscreenElement));
  if(fullscreenWorked)await page.evaluate(()=>document.exitFullscreen());
  assert(!errors.length&&!requests.length,JSON.stringify({errors,requests}));
  await fs.copyFile(path.join(output,'layout-p1.json'),path.join(output,'layout.json'));
  await context.close();await browser.close();closed=true;
  await fs.writeFile(path.join(output,'check.json'),JSON.stringify({status:'PASS',htmlSha256:digest,
    playwright:pinnedRuntime.playwrightVersion,chromiumRevision:pinnedRuntime.chromiumRevision,
    cases:checks,grayCount:49,colorCount:3,phaseCount:2,networkRequests:requests,errors,closedNormally:true,
    phaseGeometryUnchanged:true,fullscreenOptional:fullscreenWorked,profileRoot:scratch},null,2)+'\n');
  console.log(JSON.stringify({status:'PASS',cases:checks.length,phases:2,networkRequests:0,closedNormally:true}));
} catch(error) {
  await fs.writeFile(path.join(output,'failure.json'),JSON.stringify({status:'FAIL',error:String(error),errors,requests},null,2)+'\n');throw error;
} finally {
  if(browser&&!closed)await browser.close();
  await fs.rm(run,{recursive:true,force:true});await lock.close();await fs.unlink(path.join(scratch,'verify.lock'));
  if((await fs.readdir(scratch)).length===0)await fs.rmdir(scratch);
}
