import { readFileSync, writeFileSync } from 'node:fs';
import { launchPinnedChromium, pinnedRuntime } from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
const report=new URL('./',import.meta.url);
const temp='/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r1/';
const cases=JSON.parse(readFileSync(temp+'real-cases.json','utf8'));
const shader=process.argv.includes('--swiftshader');
const metal=process.argv.includes('--metal');
const args=['--enable-unsafe-webgpu'];
if(shader)args.push('--enable-unsafe-swiftshader','--use-webgpu-adapter=swiftshader');
if(metal)args.push('--use-angle=metal');
const browser=await launchPinnedChromium({args,ignoreDefaultArgs:metal?['--use-angle=swiftshader-webgl']:[],timeout:60000});
const errors=[];
try {
  const page=await browser.newPage();
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:49741/?token=review-isolated-local-only');
  await page.evaluate(c=>{window.__reviewCases=c;},cases);
  const result=await page.evaluate(readFileSync(new URL('real_route_cases.js',report),'utf8'));
  const receipt={pin:pinnedRuntime,requestedMode:shader?'swiftshader':metal?'metal':'default',actualAdapters:[...new Set(result.map(r=>r.adapter?.architecture))],errors,result};
  writeFileSync(new URL(shader?'real-route-swiftshader.json':metal?'real-route-metal.json':'real-route-hardware.json',report),JSON.stringify(receipt,null,2)+'\n');
  console.log(JSON.stringify(receipt));
} finally {await browser.close();}
