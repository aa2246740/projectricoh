import fs from 'node:fs/promises';
import path from 'node:path';
import { homedir } from 'node:os';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';

const here=path.dirname(new URL(import.meta.url).pathname),local=path.join(here,'local');
const {launchPinnedChromium,pinnedRuntime}=await import(pathToFileURL(path.join(homedir(),'.codex/playwright-runtime/runtime.mjs')).href);
process.env.TMPDIR=path.join(local,'tmp');
const frames=JSON.parse(await fs.readFile(path.join(local,'frames.json'),'utf8'));
assert.equal(frames.length,2550);
for(const f of frames)assert.ok((await fs.stat(path.join(local,f.image))).size>0);
const seen=new Set(frames.map(f=>[f.scene,f.slot,f.parameter,f.level].join('/')));
assert.equal(seen.size,2550);
const browser=await launchPinnedChromium(),errors=[],states=[];
try{
 const page=await browser.newPage({viewport:{width:1280,height:1000}});
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
 await page.goto(pathToFileURL(path.join(local,'preview.html')).href,{waitUntil:'load'});
 assert.match(await page.title(),/模型模拟，非实拍/);
 assert.equal(await page.locator('#levels button').count(),9);
 assert.equal(await page.locator('#alllevels option').count(),17);
 assert.equal(await page.locator('#adjacent tr').count(),16);
 const recipes=['01','02','03','05','06'],params=['contrast','saturation','highlight','shadow','warmth','tint'];
 for(const slot of recipes){
  await page.locator('#recipe').selectOption(slot);
  for(const parameter of params){
   await page.locator('#parameter').selectOption(parameter);
   for(const level of ['-8','-5','-3','-1','0','1','3','5','8']){
    await page.locator('#alllevels').selectOption(level);
    await page.evaluate(()=>Promise.all([...document.images].map(im=>im.decode())));
    const state=await page.evaluate(()=>({caption:document.querySelector('#caption').textContent,
     base:document.querySelector('#base').src,chosen:document.querySelector('#chosen').src,
     broken:[...document.images].filter(im=>!im.complete||!im.naturalWidth).length,
     overflow:document.documentElement.scrollWidth>innerWidth,
     note:document.querySelector('#stepnote').textContent}));
    assert.equal(state.broken,0);assert.equal(state.overflow,false);assert.match(state.caption,/模型模拟，非实拍/);
    if(slot==='03'&&parameter==='saturation'){assert.equal(state.base,state.chosen);assert.match(state.note,/停用/)}
    if(parameter==='warmth'||parameter==='tint')assert.match(state.note,/近似/);
    states.push({slot,parameter,level,passed:true});
   }
  }
 }
 await page.locator('#scene').selectOption('redblue');await page.locator('#recipe').selectOption('06');
 await page.locator('#parameter').selectOption('saturation');await page.locator('#alllevels').selectOption('5');
 await page.evaluate(()=>Promise.all([...document.images].map(im=>im.decode())));
 await page.screenshot({path:path.join(local,'preview-desktop.png'),fullPage:true});
 const widths=[320,390,768,1280],responsive=[];
 for(const width of widths){
  await page.setViewportSize({width,height:900});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  assert.equal(overflow,false);responsive.push({width,overflow});
  if(width===390)await page.screenshot({path:path.join(local,'preview-mobile.png'),fullPage:true});
 }
 assert.deepEqual(errors,[]);
 const result={passed:true,records:frames.length,interactiveStates:states.length,states,responsive,consoleErrors:errors,pinnedRuntime};
 await fs.writeFile(path.join(local,'preview-check.json'),JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify({passed:true,records:frames.length,interactiveStates:states.length,responsive,consoleErrors:errors}));
}finally{await browser.close()}
