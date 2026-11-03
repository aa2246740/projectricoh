import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {launchPinnedChromium,pinnedRuntime} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
const here='/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/probe_pack_r3';
const review='/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_probe3_r1';
const scratch=path.join(review,'local/tmp/page'),output=path.join(review,'local/page');
const mount=execFileSync('/usr/sbin/diskutil',['info','-plist','/Volumes/Workspace'],{encoding:'utf8'});
if(!mount.includes('14BE04EB-AF49-497E-B36A-B078B2F7C5E8')||!/<key>FilesystemType<\/key>\s*<string>apfs<\/string>/.test(mount))throw new Error('Workspace identity failed');
await fs.mkdir(scratch,{recursive:true});await fs.mkdir(output,{recursive:true});
const lock=await fs.open(path.join(scratch,'verify.lock'),'wx');
const run=await fs.mkdtemp(path.join(scratch,'browser-'));process.env.TMPDIR=run;
const html=await fs.readFile(path.join(here,'ramp3.html'));
const hash=createHash('sha256').update(html).digest('hex');
const prior=JSON.parse(await fs.readFile(path.join(here,'../probe_pack_r2/local/page/layout-p1.json'),'utf8'));
const wanted=['M26 A','P1 R+2','P1 R-2','P1 G+2','P1 G-2','P1 B+2','P1 B-2','M26 A'];
let browser,closed=false;const checks=[],errors=[],requests=[];
const assert=(ok,message)=>{if(!ok)throw new Error(message);};
try {
  assert(pinnedRuntime.playwrightVersion==='1.61.1'&&pinnedRuntime.chromiumRevision==='1228','Pinned runtime mismatch');
  const launch=async()=>{
    browser=await launchPinnedChromium({args:['--single-process','--no-zygote','--in-process-gpu','--disable-gpu','--disable-background-networking','--disable-breakpad'],downloadsPath:run,artifactsDir:run});
    assert(browser.version()===pinnedRuntime.chromiumVersion,'Chromium mismatch');
  };
  await launch();
  for(const dpr of [1,2]) {
    const context=await browser.newContext({offline:true,serviceWorkers:'block',deviceScaleFactor:dpr,viewport:{width:864,height:900}});
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
    page.on('request',r=>{if(!r.url().startsWith('file:'))requests.push(r.url());});
    await page.goto(pathToFileURL(path.join(here,'ramp3.html')).href);await page.evaluate(()=>document.fonts.ready);
    const cases=dpr===1?[[864,900,false],[864,900,true],[900,650,false],[800,600,false],[720,450,false],[720,450,true],[390,844,false],[1440,900,true]]:[[864,900,true],[900,650,false]];
    for(const [width,height,capture] of cases) {
      await page.setViewportSize({width,height});
      await page.evaluate(capture=>{window.probe3.capture(capture);window.probe3.go(1);document.activeElement?.blur();},capture);
      for(let shot=1;shot<=8;shot++) {
        if(shot>1)await page.keyboard.press(shot%2===0?'ArrowRight':'Space');
        await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
        const result=await page.evaluate(()=>{
          const b=el=>{const r=el.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height};};
          const inside=(a,c)=>a.x>=c.x-.1&&a.y>=c.y-.1&&a.x+a.w<=c.x+c.w+.1&&a.y+a.h<=c.y+c.h+.1;
          const overlap=(a,c)=>Math.min(a.x+a.w,c.x+c.w)>Math.max(a.x,c.x)+.1&&Math.min(a.y+a.h,c.y+c.h)>Math.max(a.y,c.y)+.1;
          const viewport={x:0,y:0,w:innerWidth,h:innerHeight},frame=b(document.querySelector('#frame')),label=b(document.querySelector('#step-label'));
          const canvas=document.querySelector('#step-label'),pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
          let badPairs=0,badPalette=0;const sum=[0,0,0],counts={32:0,208:0};
          for(let y=0;y<canvas.height;y++)for(let x=0;x<canvas.width/2;x++) {
            const a=(y*canvas.width+x)*4,z=(y*canvas.width+x+canvas.width/2)*4;
            for(let c=0;c<3;c++) {if(pixels[a+c]+pixels[z+c]!==240)badPairs++;sum[c]+=pixels[a+c]+pixels[z+c];}
            for(const at of [a,z]) {
              if(![32,208].includes(pixels[at])||pixels[at]!==pixels[at+1]||pixels[at]!==pixels[at+2]||pixels[at+3]!==255)badPalette++;
              else counts[pixels[at]]++;
            }
          }
          return{...window.probe3.readout(),width:innerWidth,height:innerHeight,dpr:devicePixelRatio,capture:document.body.classList.contains('capturing'),
            frame,label,board:b(document.querySelector('#board')),frameVisible:inside(frame,viewport),layout:window.rampLayout(),
            overflow:document.documentElement.scrollWidth>innerWidth||document.documentElement.scrollHeight>innerHeight+1,
            labelPixels:{width:canvas.width,height:canvas.height,badPairs,badPalette,sum,counts,text:window.probe3.labelGeometry().text},
            markers:[...document.querySelectorAll('.marker')].map(el=>({corner:el.dataset.corner,box:b(el),visible:inside(b(el),frame)&&inside(b(el),viewport),overLabel:overlap(b(el),label)})),
            patches:[...document.querySelectorAll('.patch')].map(el=>{
              const sample=b(el.querySelector('.sample')),sw=b(el.querySelector('.swatch')),caption=b(el.querySelector('.caption'));
              return{id:el.dataset.patchId,rgb:el.dataset.rgb,css:getComputedStyle(el.querySelector('.swatch')).backgroundColor,
                sample,swatch:sw,caption,visible:inside(b(el),frame)&&inside(b(el),viewport),overLabel:overlap(sw,label),
                sampleInSwatch:inside(sample,sw),labelOverSample:overlap(sample,caption)};
            })};
        });
        const caseName=`dpr${dpr}-${width}x${height}-${capture?'capture':'normal'}`;
        const name=`${caseName}-s${shot}`;
        assert(result.shot===shot&&result.entry===wanted[shot-1],`${name}: wrong step/name`);
        assert(result.phaseCount===1&&result.labelIsHint&&result.capture===capture,`${name}: protocol/mode`);
        assert(result.frameVisible&&!result.overflow,`${name}: frame cropped`);
        assert(result.markers.length===4&&result.markers.every(m=>m.visible&&!m.overLabel),`${name}: markers`);
        assert(result.patches.length===52&&result.patches.every(p=>p.visible&&!p.overLabel&&p.sampleInSwatch&&!p.labelOverSample),`${name}: patches/label overlap`);
        assert(result.patches.every(p=>p.sample.w>=7&&p.sample.h>=7&&p.css===`rgb(${p.rgb.split(',').join(', ')})`),`${name}: sample dimensions/colors`);
        assert(JSON.stringify(result.layout.grayLevels)===JSON.stringify(prior.grayLevels),`${name}: P1 codes changed`);
        for(let p=0;p<52;p++) {
          assert(JSON.stringify(result.layout.patches[p].rgb)===JSON.stringify(prior.patches[p].rgb),`${name}: colour ${p}`);
          for(const part of ['swatch','sample','caption'])for(const k of ['x','y','w','h'])
            assert(Math.abs(result.layout.patches[p][part][k]-prior.patches[p][part][k])<.0001,`${name}: old board geometry ${p}/${part}/${k}`);
        }
        const lp=result.labelPixels;
        assert(lp.badPairs===0&&lp.badPalette===0&&lp.counts[32]===lp.counts[208],`${name}: label palette/paired light`);
        assert(lp.sum.every(x=>x===120*lp.width*lp.height),`${name}: label total light changed`);
        await page.screenshot({path:path.join(output,name+'.png'),fullPage:false});
        await fs.writeFile(path.join(output,name+'.json'),JSON.stringify(result,null,2)+'\n');
        if(dpr===1&&width===864&&height===900&&capture&&shot===1)await fs.writeFile(path.join(output,'layout.json'),JSON.stringify(result.layout,null,2)+'\n');
        checks.push({name,caseName,shot,status:'PASS',dpr});
      }
      await page.keyboard.press('ArrowRight');assert((await page.evaluate(()=>window.probe3.readout())).shot===8,'End must clamp');
      await page.keyboard.press('ArrowLeft');assert((await page.evaluate(()=>window.probe3.readout())).shot===7,'Back failed');
      await page.locator('#next').click();assert((await page.evaluate(()=>window.probe3.readout())).shot===8,'Next button failed');
      await page.locator('#reset').click();await page.keyboard.press('ArrowLeft');assert((await page.evaluate(()=>window.probe3.readout())).shot===1,'Start must clamp');
      await page.keyboard.down('ArrowRight');await page.keyboard.down('ArrowRight');await page.keyboard.up('ArrowRight');
      assert((await page.evaluate(()=>window.probe3.readout())).shot===2,'Held key must not skip');
      await page.keyboard.press('Escape');assert(!await page.evaluate(()=>document.body.classList.contains('capturing')),'Escape failed');
    }
    await context.close();
    if(dpr===1){await browser.close();await launch();}
  }
  assert(!errors.length&&!requests.length,JSON.stringify({errors,requests}));
  await browser.close();closed=true;
  await fs.writeFile(path.join(output,'check.json'),JSON.stringify({status:'PASS',htmlSha256:hash,
    playwright:pinnedRuntime.playwrightVersion,chromiumRevision:pinnedRuntime.chromiumRevision,cases:checks,
    steps:8,phaseCount:1,networkRequests:requests,errors,closedNormally:true,frameGeometryUnchanged:true,
    P1_stimulus_byte_values_unchanged:true,label_pair_sum_RGB:240,label_mean_RGB:[120,120,120],
    labelPalette:[[32,32,32],[208,208,208]],responseOnlySupported:true},null,2)+'\n');
  console.log(JSON.stringify({status:'PASS',screenshots:checks.length,steps:8,phases:1,networkRequests:0,closedNormally:true}));
} catch(error) {
  await fs.writeFile(path.join(output,'failure.json'),JSON.stringify({status:'FAIL',error:String(error),errors,requests},null,2)+'\n');throw error;
} finally {
  if(browser&&!closed)await browser.close();
  await fs.rm(run,{recursive:true,force:true});await lock.close();await fs.unlink(path.join(scratch,'verify.lock'));
}
