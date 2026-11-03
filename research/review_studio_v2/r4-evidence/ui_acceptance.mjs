import {recordBrowser} from './record_browser_r4.mjs';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { launchPinnedChromium } from '/Users/wu/.codex/playwright-runtime/runtime.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const scratch = '/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r4';
process.env.TMPDIR = scratch;
const ready = JSON.parse(await readFile(path.join(scratch, 'server-ready.json'), 'utf8'));
const base = `http://127.0.0.1:${ready.port}`;
const browser = await launchPinnedChromium({ env: { ...process.env, TMPDIR: scratch } });
await recordBrowser('ui_acceptance.mjs');
const results = { browserVersion: browser.version(), errors: [], responses: [] };
try {
  const context = await browser.newContext({ viewport: { width: 1360, height: 860 } });
  const page = await context.newPage();
  page.on('pageerror', e => results.errors.push(String(e)));
  page.on('response', r => { if (r.status() >= 400) results.responses.push({ url: r.url(), status: r.status() }); });
  await page.goto(ready.url);
  const api = async (method, url, data) => {
    const response = await page.request.fetch(base + url, { method, data,
      headers: { 'X-GXR-Token': 'independent-review-browser' } });
    if (!response.ok()) throw new Error(`${url} ${response.status()} ${await response.text()}`);
    return response.json();
  };
  const photos = await api('GET', '/api/photos');
  const jpg = photos.find(p => p.name === 'REVIEW').id;
  const raw = photos.find(p => p.name === 'R8051219').id;
  const waitImage = async () => page.waitForFunction(() => {
    const i = document.querySelector('.pv-img');
    const status = document.querySelector('.status .right');
    return i && i.complete && i.naturalWidth > 0 && (!status || !status.textContent.includes('正在'));
  }, null, { timeout: 60000 });
  const open = async id => {
    await page.goto(base + `/#/photo/${id}`);
    await page.reload();
    await page.getByRole('tab', { name: '配方', exact: true }).waitFor();
    await waitImage();
  };
  const shot = name => page.screenshot({ path: path.join(here, name), fullPage: true });
  const geometry = async () => page.evaluate(() => {
    const panel = document.querySelector('.side-body');
    const r = panel.getBoundingClientRect();
    return { panel: { x: r.x, y: r.y, width: r.width, height: r.height },
      cards: [...document.querySelectorAll('.fcard')].map(e => {
        const b = e.getBoundingClientRect();
        return { name: e.innerText.trim(), x: b.x, right: b.right, y: b.y, width: b.width,
          outside: b.left < r.left || b.right > r.right };
      }), documentWidth: document.documentElement.scrollWidth, viewportWidth: innerWidth };
  });
  await api('DELETE', `/api/photos/${jpg}/edit`);
  await api('DELETE', `/api/photos/${jpg}/crop`);
  await api('PUT', '/api/defaults/finish', { frame: { style: 'none' }, stamp: { enabled: false } });
  await open(jpg);
  results.jpgRecipeDisabled = await page.locator('.base-grid button').evaluateAll(es => es.every(e => e.disabled || e.getAttribute('aria-disabled') === 'true'));
  results.jpgRecipeText = await page.locator('.side-body').innerText();
  await shot('ui-jpg-recipe.png');
  await page.getByRole('tab', { name: '边框', exact: true }).click();
  await page.waitForFunction(() => document.querySelectorAll('.fcard img').length === 7 &&
    [...document.querySelectorAll('.fcard img')].every(i => i.complete && i.naturalWidth > 0));
  results.frames1360 = await geometry();
  await shot('ui-frame-current.png');
  const savedFrame = page.waitForResponse(r => r.url().endsWith(`/api/photos/${jpg}/edit`) && r.request().method() === 'PUT');
  await page.getByRole('button', { name: '白边', exact: true }).click();
  await savedFrame;
  await waitImage();
  await shot('ui-frame-selected.png');
  await page.keyboard.down('Space');
  await waitImage();
  results.originalMode = await page.locator('.pv-img').evaluate(i => ({ src: i.src, width: i.naturalWidth, height: i.naturalHeight }));
  await shot('ui-space-original.png');
  await page.keyboard.up('Space');
  await page.getByRole('tab', { name: '调整', exact: true }).click();
  const curveRequests = [];
  const onRequest = r => {
    if (r.url().includes('/render?') && r.method() === 'POST') curveRequests.push(r.postDataJSON());
  };
  page.on('request', onRequest);
  await page.locator('svg.curve').scrollIntoViewIfNeeded();
  const box = await page.locator('svg.curve').boundingBox();
  await page.mouse.move(box.x + box.width * .5, box.y + box.height * .5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * .5, box.y + box.height * .2);
  await page.waitForResponse(r => r.url().includes('/render?') && r.request().method() === 'POST');
  await page.mouse.up();
  await waitImage();
  page.off('request', onRequest);
  results.curveDragBodies = curveRequests;
  await shot('ui-curve-current.png');

  // Real UI restore clears both the editing blocks and crop when factory defaults are active.
  await api('PUT', `/api/photos/${jpg}/edit`, { adjust: { exposure_ev: 1 }, curve: { master: [[0,0],[128,50],[255,255]] },
    geometry: { straighten: 4, rotate90: 1 }, frame: { style: 'gallery' },
    stamp: { enabled: true, content: 'text', text: 'GXR', font: 'sans' } });
  await api('PUT', `/api/photos/${jpg}/crop`, { preset: '1:1' });
  await open(jpg);
  const restored = page.waitForResponse(r => r.url().endsWith(`/api/photos/${jpg}/crop`) && r.request().method() === 'PUT');
  await page.getByRole('button', { name: '复原', exact: true }).click();
  await restored;
  await waitImage();
  results.restore = { edit: await api('GET', `/api/photos/${jpg}/edit`), crop: await api('GET', `/api/photos/${jpg}/crop`) };
  await shot('ui-restored.png');
  // A saved default is inherited again when restore persists null finishing blocks.
  await api('PUT', '/api/defaults/finish', { frame: { style: 'gallery' }, stamp: { enabled: false } });
  await open(jpg);
  const done = page.waitForResponse(r => r.url().endsWith(`/api/photos/${jpg}/crop`) && r.request().method() === 'PUT');
  await page.getByRole('button', { name: '复原', exact: true }).click();
  await done;
  await waitImage();
  results.restoreWithDefaultsBeforeReload = await page.locator('.pv-img').evaluate(i => ({ width: i.naturalWidth, height: i.naturalHeight }));
  await page.reload();
  await waitImage();
  results.restoreWithDefaultsAfterReload = await page.locator('.pv-img').evaluate(i => ({ width: i.naturalWidth, height: i.naturalHeight }));
  await shot('ui-restored-defaults-reload.png');
  await api('PUT', '/api/defaults/finish', { frame: { style: 'none' }, stamp: { enabled: false } });
  await page.getByRole('tab', { name: '裁剪', exact: true }).click();
  await waitImage();
  await shot('ui-crop-current.png');
  await page.getByRole('tab', { name: '时间戳', exact: true }).click();
  await waitImage();
  await shot('ui-stamp-current.png');
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.getByRole('tab', { name: '边框', exact: true }).click();
  await waitImage();
  results.frames1024 = await geometry();
  await shot('ui-frame-1024.png');
  results.finalText = await page.locator('body').innerText();
  await page.close();
  await context.close();
} catch (error) {
  results.failure = String(error.stack || error);
  process.exitCode = 1;
} finally {
  await browser.close();
  await writeFile(path.join(here, 'ui-acceptance.json'), JSON.stringify(results, null, 2) + '\n');
  console.log(JSON.stringify(results, null, 2));
}
