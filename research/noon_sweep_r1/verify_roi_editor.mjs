import { readFile, mkdir, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { launchPinnedChromium } from '/Users/wu/.codex/playwright-runtime/runtime.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(here, 'local/verify-roi-editor');
await mkdir(out, { recursive: true });
const browser = await launchPinnedChromium({ downloadsPath: out });
try {
  const context = await browser.newContext({ viewport: { width: 1480, height: 1800 }, offline: true });
  await context.route('**/*', route => route.abort());
  const page = await context.newPage();
  await page.setContent(await readFile(path.join(here, 'roi_editor.html'), 'utf8'));
  await page.locator('#files').setInputFiles([
    path.join(here, 'local/intake-fixture/F072.JPG'),
    path.join(here, 'local/intake-fixture/F073.JPG'),
  ]);
  await page.waitForFunction(() => document.getElementById('status').textContent.includes('F072.JPG'));
  const box = await page.locator('canvas').boundingBox();
  const point = ([x, y]) => ({ x: box.x+x*box.width, y: box.y+y*box.height });
  const corners = [[75/1600,95/1000],[1071/1600,95/1000],[1071/1600,695/1000],[75/1600,695/1000]];
  await page.locator('#corners').click();
  for (const xy of corners) {
    const p = point(xy);
    await page.mouse.click(p.x, p.y);
  }
  await page.locator('#skin').click();
  let p = point([1180/1600,100/1000]);
  await page.mouse.move(p.x,p.y);
  await page.mouse.down();
  p = point([1480/1600,350/1000]);
  await page.mouse.move(p.x,p.y,{steps:4});
  await page.mouse.up();
  await page.locator('#track').check();
  await page.locator('#template').click();
  await page.locator('#next').click();
  await page.locator('#setting').selectOption('05 F-CC');
  const data = JSON.parse(await page.locator('#json').inputValue());
  assert.equal(data.frames.F072.chart.corners.length,4);
  assert.equal(data.frames.F072.rois[0].group,'memory_skin');
  assert.equal(data.frames.F073.setting,'05 F-CC');
  assert.equal(data.physical_template.reference_frame,'F072');
  assert.equal(data.physical_template.track_with_card,true);
  for (let i=0;i<4;i++) for(let k=0;k<2;k++) {
    assert.ok(Math.abs(data.frames.F072.chart.corners[i][k]-corners[i][k])<.0001);
  }
  const download = page.waitForEvent('download');
  await page.locator('#save').click();
  await (await download).saveAs(path.join(out,'noon-manifest.json'));
  const saved = JSON.parse(await readFile(path.join(out,'noon-manifest.json'),'utf8'));
  assert.equal(saved.frames.F072.rois[0].id,'skin_1');
  await page.screenshot({path:path.join(out,'editor.png')});
  await writeFile(path.join(out,'receipt.json'),JSON.stringify({status:'PASS',
    tests:['four corners','drag skin ROI','frame navigation','recipe setting','shared template','card tracking','JSON download'],
    nativeNetworkRequests:0},null,2));
  console.log('PASS offline ROI editor: four corners, skin box, next frame, recipe, template, JSON export');
} finally {
  await browser.close();
}
