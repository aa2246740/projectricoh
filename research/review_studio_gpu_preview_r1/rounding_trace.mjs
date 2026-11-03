import {readFileSync,writeFileSync} from 'node:fs';
import {launchPinnedChromium} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
const temp='/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r1/';
const original=JSON.parse(readFileSync(temp+'real-cases.json','utf8')).find(c=>c.id==='c_recipe04_curve_extra');
const variants=[{}, {black_point:20},{black_point:20,saturation:30},{black_point:20,saturation:30,vibrance:25},original.adjust].map((adjust,i)=>({...original,id:'trace_c_'+i,adjust}));
writeFileSync(temp+'trace-cases.json',JSON.stringify(variants,null,2)+'\n');
const browser=await launchPinnedChromium({args:['--enable-unsafe-webgpu','--use-angle=metal'],ignoreDefaultArgs:['--use-angle=swiftshader-webgl']});
try {
 const page=await browser.newPage();await page.goto('http://127.0.0.1:49741/?token=review-isolated-local-only');
 await page.evaluate(c=>{window.__reviewCases=c;},variants);
 const result=await page.evaluate(readFileSync(new URL('real_route_cases.js',import.meta.url),'utf8'));
 writeFileSync(new URL('rounding-trace-route.json',import.meta.url),JSON.stringify(result,null,2)+'\n');
 console.log(JSON.stringify(result));
} finally {await browser.close();}
