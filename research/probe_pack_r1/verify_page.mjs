import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {launchPinnedChromium, pinnedRuntime} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';

const here=path.dirname(fileURLToPath(import.meta.url));
const mount=execFileSync('/usr/sbin/diskutil',['info','-plist','/Volumes/Workspace'],{encoding:'utf8'});
if(!mount.includes('<string>14BE04EB-AF49-497E-B36A-B078B2F7C5E8</string>') ||
   !/<key>FilesystemType<\/key>\s*<string>apfs<\/string>/.test(mount) ||
   !/<key>WritableVolume<\/key>\s*<true\/>/.test(mount)) throw new Error('Workspace volume guard failed');
const output=path.join(here,'local/page');
await fs.mkdir(output,{recursive:true});
const scratch='/Volumes/Workspace/Scratch/tmp/projectricoh/probe-pack-r1/page';
await fs.mkdir(scratch,{recursive:true});
process.env.TMPDIR=scratch;
const browser=await launchPinnedChromium();
const errors=[],external=[];
try {
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
  page.on('pageerror',error=>errors.push(error.message));
  page.on('request',request=>{if(!request.url().startsWith('file:'))external.push(request.url());});
  await page.goto(pathToFileURL(path.join(here,'patches.html')).href);
  const count=await page.locator('#curves .patch').count();
  if(count!==6) throw new Error('expected six type26 patches');
  if(errors.length) throw new Error(errors.join('; '));
  await page.screenshot({path:path.join(output,'curves.png'),fullPage:true});
  await page.getByRole('button',{name:'C120 色块 · 2',exact:true}).click();
  if(await page.locator('#axis .patch:visible').count()!==18) throw new Error('expected eighteen C120 patches');
  const patches=await page.locator('#axis .patch').evaluateAll(elements=>elements.map(el=>({
    rgb:el.dataset.rgb.split(',').map(Number),L:Number(el.dataset.l),C:Number(el.dataset.c),h:Number(el.dataset.h),
    css:getComputedStyle(el).backgroundColor
  })));
  if(patches.some(p=>p.rgb.some(n=>n<=0||n>=255))) throw new Error('clipped patch');
  for(const hue of [40,140])for(const L of [30,50,70]) {
    const row=patches.filter(p=>p.h===hue&&p.L===L);
    if(row.length!==3||row.map(p=>p.C).join(',')!=='8,24,40') throw new Error('nonorthogonal patch grid');
  }
  await page.screenshot({path:path.join(output,'c120.png'),fullPage:true});
  await page.locator('#axis .patch').first().click();
  await page.keyboard.press('Space');
  const target=await page.evaluate(()=>({target:document.body.classList.contains('target'),
    header:getComputedStyle(document.querySelector('header')).display,
    overflow:document.documentElement.scrollWidth>innerWidth,
    boxes:[...document.querySelectorAll('#axis .patch')].map(p=>{
      const r=p.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};
    })}));
  if(!target.target||target.header!=='none'||target.overflow) throw new Error('target mode failed');
  if(target.boxes.some(r=>r.x<0||r.y<0||r.x+r.w>1440||r.y+r.h>1000)) throw new Error('target extends outside viewport');
  await page.screenshot({path:path.join(output,'c120-target.png'),fullPage:true});
  await page.keyboard.press('1');
  if(await page.locator('#curves .patch:visible').count()!==6) throw new Error('keyboard selection failed');
  await page.screenshot({path:path.join(output,'curves-target.png'),fullPage:true});
  if(errors.length||external.length) throw new Error(JSON.stringify({errors,external}));
  const result={status:'PASS',playwright:pinnedRuntime.playwrightVersion,chromiumRevision:pinnedRuntime.chromiumRevision,
    htmlSha256:createHash('sha256').update(await fs.readFile(path.join(here,'patches.html'))).digest('hex'),
    type26Patches:6,c120Patches:18,keyboard:true,targetMode:true,networkRequests:0,errors,patches};
  await fs.writeFile(path.join(here,'evidence/page.json'),JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify({status:'PASS',type26Patches:6,c120Patches:18}));
} finally {await browser.close();}
