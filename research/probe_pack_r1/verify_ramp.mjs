// Offline, serial layout verification. Run with nice -n 10 node verify_ramp.mjs.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {launchPinnedChromium, pinnedRuntime} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const scratch = '/Volumes/Workspace/Scratch/tmp/projectricoh/probe-ramp';
const output = path.join(here, 'local/ramp/browser');
const volume = execFileSync('/usr/sbin/diskutil', ['info','-plist','/Volumes/Workspace'], {encoding:'utf8'});
if (!volume.includes('<string>14BE04EB-AF49-497E-B36A-B078B2F7C5E8</string>') ||
    !/<key>FilesystemType<\/key>\s*<string>apfs<\/string>/.test(volume) ||
    !/<key>WritableVolume<\/key>\s*<true\/>/.test(volume)) throw new Error('Workspace volume guard failed');
await fs.mkdir(scratch, {recursive:true});
// An existing lock means another check is running. Never remove its files.
const lockPath = path.join(scratch, 'verify.lock');
const lock = await fs.open(lockPath, 'wx');
await lock.writeFile(String(process.pid));
const run = await fs.mkdtemp(path.join(scratch, 'browser-'));
process.env.TMPDIR = run;
await fs.mkdir(output, {recursive:true});
const html = await fs.readFile(path.join(here, 'ramp.html'));
const htmlSha256 = createHash('sha256').update(html).digest('hex');
let browser, closedNormally = false;
const failures = [], errors = [], requests = [], consoleErrors = [], checks = [];
const assert = (ok, message) => { if (!ok) throw new Error(message); };
try {
  assert(pinnedRuntime.playwrightVersion === '1.61.1' && pinnedRuntime.chromiumRevision === '1228', 'Global runtime pin mismatch');
  browser = await launchPinnedChromium({args:['--renderer-process-limit=1'], artifactsDir:run, downloadsPath:run});
  assert(browser.version() === pinnedRuntime.chromiumVersion, `Chromium version mismatch: ${browser.version()}`);
  const context = await browser.newContext({viewport:{width:864,height:900},deviceScaleFactor:1,
    offline:true, serviceWorkers:'block', acceptDownloads:false});
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('request', r => { if (!r.url().startsWith('file:')) requests.push(r.url()); });
  const response = await page.goto(pathToFileURL(path.join(here,'ramp.html')).href);
  assert(!response || response.ok(), 'Local page did not load');
  await page.evaluate(() => document.fonts.ready);
  const initial = await page.evaluate(() => window.rampLayout());
  assert(initial.grayLevels.length === 49 && new Set(initial.grayLevels).size === 49, 'Expected 49 distinct greys');
  assert(initial.patches.length === 52 && initial.markers.length === 4, 'Patch/marker count mismatch');
  assert(initial.patches.filter(p => p.id.startsWith('g')).length === 49, 'Grey patch IDs mismatch');
  // Each marker must remain distinguishable under rotations, including its own.
  const markerRotations = [];
  const rotate = rows => rows.map((_,y) => rows.map(row => row[y]).reverse().join(''));
  for (const marker of initial.markers) {
    let rows = marker.bits;
    for (let r=0;r<4;r++) { markerRotations.push(rows.join('')); rows=rotate(rows); }
  }
  assert(new Set(markerRotations).size === 16, 'Ambiguous corner marker rotation');
  const cases = [
    [864,900,false], [864,900,true],
    [900,650,false], [800,600,false], [800,600,true],
    [720,450,false], [720,450,true],
    [1440,900,true], [390,844,false]
  ];
  for (const [width,height,capture] of cases) {
    await page.setViewportSize({width,height});
    const active = await page.locator('#capture').getAttribute('aria-pressed') === 'true';
    if (active !== capture) await page.locator('#capture').click();
    // Wait two animation frames for ResizeObserver and flex layout, no timed polling.
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const result = await page.evaluate(() => {
      const b = el => { const r=el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height}; };
      const overlap = (a,b) => Math.min(a.x+a.w,b.x+b.w)>Math.max(a.x,b.x)+.1 &&
        Math.min(a.y+a.h,b.y+b.h)>Math.max(a.y,b.y)+.1;
      const inside = (a,b) => a.x >= b.x-.1 && a.y >= b.y-.1 && a.x+a.w <= b.x+b.w+.1 && a.y+a.h <= b.y+b.h+.1;
      const viewport = {x:0,y:0,w:innerWidth,h:innerHeight};
      const patches = [...document.querySelectorAll('.patch')].map(el => {
        const swatch = el.querySelector('.swatch'), sample = b(el.querySelector('.sample')),
          caption = b(el.querySelector('.caption'));
        return {id:el.dataset.patchId, swatch:b(swatch), sample, caption,
          rgb:el.dataset.rgb, css:getComputedStyle(swatch).backgroundColor,
          captionOverflow:el.querySelector('.caption').scrollWidth > el.querySelector('.caption').clientWidth+1,
          labelOverSample:overlap(caption,sample), sampleWithinSwatch:inside(sample,b(swatch)),
          fullyVisible:inside(b(el),viewport),
          border:getComputedStyle(swatch).borderWidth, filter:getComputedStyle(swatch).filter};
      });
      return {width:innerWidth,height:innerHeight,capture:document.body.classList.contains('capturing'),
        board:b(document.querySelector('#board')), overflow:document.documentElement.scrollWidth>innerWidth ||
          document.documentElement.scrollHeight>innerHeight+1,
        fullscreen:Boolean(document.fullscreenElement),
        markers:[...document.querySelectorAll('.marker')].map(el => ({corner:el.dataset.corner,box:b(el),visible:inside(b(el),viewport)})),
        patches, layout:window.rampLayout()};
    });
    const name = `${width}x${height}-${capture?'capture':'normal'}`;
    assert(result.capture === capture && !result.fullscreen, `${name}: capture mode/fullscreen mismatch`);
    assert(!result.overflow, `${name}: page scrolls`);
    assert(result.board.w <= 640.1, `${name}: board exceeds physical-size cap`);
    assert(result.markers.every(m => m.visible), `${name}: cropped marker`);
    assert(result.patches.every(p => p.fullyVisible && p.sampleWithinSwatch && !p.labelOverSample && !p.captionOverflow), `${name}: cropped patch/label overlap`);
    assert(result.patches.every(p => p.sample.w >= 8 && p.sample.h >= 8), `${name}: central sample too small`);
    assert(result.patches.every(p => p.css === `rgb(${p.rgb.split(',').join(', ')})` && p.filter === 'none' && p.border === '0px'), `${name}: swatch color changed`);
    const reference = JSON.stringify(initial.grayLevels);
    assert(JSON.stringify(result.layout.grayLevels) === reference, `${name}: levels changed`);
    await page.screenshot({path:path.join(output,`${name}.png`),fullPage:false});
    await fs.writeFile(path.join(output,`${name}.json`),JSON.stringify(result,null,2)+'\n');
    checks.push({name,status:'PASS',board:result.board,minSampleWidth:Math.min(...result.patches.map(p=>p.sample.w)),
      minSampleHeight:Math.min(...result.patches.map(p=>p.sample.h))});
  }
  // Keyboard paths must work without requiring fullscreen.
  await page.locator('main').click({position:{x:1,y:1}});
  await page.keyboard.press('Space');
  assert(await page.locator('#capture').getAttribute('aria-pressed') === 'true', 'Space did not enter capture');
  await page.keyboard.press('Escape');
  assert(await page.locator('#capture').getAttribute('aria-pressed') === 'false', 'Escape did not exit capture');
  // Optional fullscreen may succeed or be refused, but it must not affect the chart data.
  await page.locator('#fullscreen').click();
  await page.waitForFunction(() => Boolean(document.fullscreenElement) ||
    document.querySelector('#fullscreen').textContent.includes('不可用'), {timeout:5000});
  const fullscreenWorked = await page.evaluate(() => Boolean(document.fullscreenElement));
  if (fullscreenWorked) await page.evaluate(() => document.exitFullscreen());
  assert((await page.evaluate(() => window.rampLayout().patches.length)) === 52, 'Fullscreen changed the patches');
  assert(errors.length === 0 && consoleErrors.length === 0 && requests.length === 0, JSON.stringify({errors,consoleErrors,requests}));
  await fs.writeFile(path.join(output,'layout.json'),JSON.stringify(initial,null,2)+'\n');
  await context.close();
  await browser.close();
  closedNormally = true;
  const receipt = {status:'PASS',htmlSha256,playwright:pinnedRuntime.playwrightVersion,
    chromiumRevision:pinnedRuntime.chromiumRevision,chromiumVersion:pinnedRuntime.chromiumVersion,
    grayCount:49,colorCount:3,cornerMarkers:4,networkRequests:requests,errors,consoleErrors,
    cases:checks,keyboard:true,fullscreenOptional:fullscreenWorked,closedNormally,
    profileLocation:run,offline:true,rendererProcessLimit:1,
    processPolicy:'One serial test job at nice 10; Chromium uses its normal helper processes.'};
  await fs.writeFile(path.join(output,'check.json'),JSON.stringify(receipt,null,2)+'\n');
  console.log(JSON.stringify({status:'PASS',cases:checks.length,grayCount:49,colorCount:3,networkRequests:0,closedNormally}));
} catch (e) {
  failures.push(String(e.stack || e));
  await fs.writeFile(path.join(output,'failure.json'),JSON.stringify({htmlSha256,failures,errors,consoleErrors,requests},null,2)+'\n');
  throw e;
} finally {
  if (browser && !closedNormally) { await browser.close(); closedNormally = true; }
  await fs.rm(run,{recursive:true,force:true});
  await lock.close();
  await fs.unlink(lockPath);
  const remaining = await fs.readdir(scratch);
  if (remaining.length === 0) await fs.rmdir(scratch);
}
