// 直接加载产品组件，核对原因、顺序、点击、档位记忆和导入后的缓存刷新。
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, join, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { launchPinnedChromium, verifyPinnedRuntime } from '/Users/wu/.codex/playwright-runtime/runtime.mjs';

const here = fileURLToPath(new URL('.', import.meta.url));
const assets = resolve(here, '../../studio/web/assets');
const scratch = '/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g152-r1';
const catalog = JSON.parse(await readFile(join(scratch, 'ui_catalog.json'), 'utf8'));
const supported = '这个相机配方文件需要更新版本的 GXR 工作室。';
const runtime = verifyPinnedRuntime();
let scenario = 'missing';
let importResult = 'ready';
let saved = null;
let revision = 0;
const requests = [];
const errors = [];
let holdNextCatalog = false;
let releaseCatalog;
let catalogHeld;
let notifyCatalogHeld;
function status() {
  const imported = ['ready', 'no_raw', 'calibration_missing'].includes(scenario);
  return { ready: imported && scenario !== 'calibration_missing', data_version: imported ? 'file-152' : 'none-none',
    camera_data: { state: imported ? 'ready' : scenario === 'unsupported' ? 'unsupported' : 'missing',
      generation: imported ? 152 : scenario === 'unsupported' ? 154 : null,
      message: scenario === 'unsupported' ? supported : '还没有导入相机配方文件' },
    calibration: { state: imported && scenario !== 'calibration_missing' ? 'ready' : 'missing' } };
}
function caps() { return { raw: scenario !== 'no_raw', recipe: scenario === 'ready' ? 'full' : 'none' }; }
function listing() {
  if (status().camera_data.state === 'ready') return catalog;
  return { units: catalog.units.map((u) => ({ ...u, looks: [], users: [] })) };
}

await mkdir(join(scratch, 'browser-home'), { recursive: true });
const browser = await launchPinnedChromium({
  args: ['--single-process', '--in-process-gpu', '--no-zygote'],
  env: { ...process.env, GXR_STUDIO_HOME: join(scratch, 'browser-home'), GXR_STUDIO_LIBRARY: join(scratch, 'browser-library'),
    GXR_STUDIO_EXPORT: join(scratch, 'browser-export'), GXR_STUDIO_VOLUMES: join(scratch, 'browser-volumes') },
});
const context = await browser.newContext({ viewport: { width: 1200, height: 1400 } });
const page = await context.newPage();
page.on('pageerror', (error) => errors.push(String(error)));
const deadline = setTimeout(() => { process.exitCode = 124; browser.close(); }, 60000);
try {
  await page.route('**/*', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body, code = 200) => route.fulfill({ status: code, contentType: 'application/json', body: JSON.stringify(body) });
    if (path === '/') return route.fulfill({ contentType: 'text/html', body: '<!doctype html><link rel="stylesheet" href="/assets/app.css"><main id="panel"></main><div id="toast-root"></div><div id="modal-root"></div>' });
    if (path.startsWith('/assets/') && basename(path) === path.slice(8)) {
      const body = await readFile(join(assets, basename(path)));
      return route.fulfill({ contentType: path.endsWith('.css') ? 'text/css' : 'text/javascript', body });
    }
    if (path === '/api/luts') return json({ luts: [], groups: [] });
    if (path === '/api/recipes') {
      if (holdNextCatalog) {
        holdNextCatalog = false;
        const previous = { units: catalog.units.map((u) => ({ ...u, looks: [], users: [] })) };
        return new Promise((done) => {
          releaseCatalog = async () => { await json(previous); done(); };
          notifyCatalogHeld();
        });
      }
      return json(listing());
    }
    if (path === '/api/camdata/status') return json(status());
    if (path.endsWith('/capabilities')) return json(caps());
    if (path.endsWith('/edit')) {
      if (request.method() === 'PUT') {
        const body = request.postDataJSON(); requests.push(body); saved = body.recipe; revision++;
      }
      return json({ rev: revision, recipe: saved, render: { available: scenario === 'ready' } });
    }
    if (path.includes('/render')) return route.fulfill({ contentType: 'image/jpeg', body: Buffer.from([255, 216, 255, 217]),
      headers: { 'X-GXR-Label': 'prediction', 'X-GXR-Calibrated': '0' } });
    if (path === '/api/camdata/import-upload') {
      scenario = importResult;
      return scenario === 'unsupported' ? json({ error: 'generation_unsupported', message: supported }, 422) : json({ message: '已导入相机配方文件' });
    }
    if (path === '/api/camdata/import-card') {
      if (!request.postDataJSON()?.card_id) return json({ error: 'multiple_cards', message: '插着不止一张带 GXRCE.DAT 的存储卡。请选一张。',
        cards: [{ id: 'card-one', label: '第一张' }, { id: 'card-two', label: '第二张' }] }, 409);
      scenario = 'ready';
      return json({ message: '已导入相机配方文件' });
    }
    return json({ error: 'not_found' }, 404);
  });
  await page.goto('http://studio.test/');
  await page.evaluate(async () => {
    const recipes = await import('/assets/recipes.js');
    const preview = await import('/assets/preview.js');
    const camera = await import('/assets/camdata.js');
    const shared = await import('/assets/state.js');
    window.scene = { recipes, preview, camera, shared };
    window.showPanel = async (name, photoId = name) => {
      const { state } = shared;
      state.catalog = null;
      state.cards = [{ id: 'fixture-card', has_dat: true }];
      await camera.loadCamdata();
      const view = { photo: { id: photoId, has_raw: name !== 'no_raw', lens: 'GXR MOUNT A12' } };
      await preview.ensureEdit(view);
      view.redrawSide = () => document.getElementById('panel').replaceChildren(recipes.recipePanel(view));
      view.redrawSide();
      window.view = view;
    };
  });
  const states = [];
  for (const name of ['missing', 'unsupported', 'no_raw', 'calibration_missing', 'ready']) {
    scenario = name; saved = null;
    await page.evaluate((value) => window.showPanel(value), name);
    const text = await page.locator('#panel').innerText();
    assert.equal(text.includes('存储卡上没有相机配方文件'), false);
    assert.equal(text.includes('配方需要 RAW 文件'), name === 'no_raw');
    assert.equal(text.includes('拍摄时将画质设为 RAW+JPEG'), name === 'no_raw');
    const reason = name === 'missing' ? '未导入相机配方文件' : name === 'unsupported' ? supported : name === 'calibration_missing' ? '未导入校准数据' : null;
    assert.equal(await page.locator('.camdata-guide h3').count(), reason ? 1 : 0);
    if (reason) assert.equal(await page.locator('.camdata-guide h3').innerText(), reason);
    const buttons = page.locator('.base-grid button');
    const count = status().camera_data.state === 'ready' ? 21 : 8;
    assert.equal(await buttons.count(), count);
    const disabled = await buttons.evaluateAll((list) => list.every((b) => b.getAttribute('aria-disabled') === 'true'));
    assert.equal(disabled, name !== 'ready');
    states.push({ state: name, reason, buttons: count, enabled: !disabled });
  }
  const names = await page.locator('.base-grid button').allTextContents();
  assert.deepEqual(names.slice(8, 18), catalog.units[2].looks.map((r) => r.name));
  assert.deepEqual(names.slice(18), ['FCC-001', 'FCC*002', 'GRN*001']);
  assert.equal(await page.getByText('未校准', { exact: true }).count(), 1);
  await page.getByRole('button', { name: 'M9 STD', exact: true }).click();
  await page.evaluate(() => window.scene.preview.flushEdits(window.view));
  assert.equal(requests.at(-1).recipe.kind, 'look');
  assert.equal(requests.at(-1).recipe.id, catalog.units[2].looks[0].id);
  await page.getByRole('slider', { name: '对比度', exact: true }).press('ArrowRight');
  await page.evaluate(() => window.scene.preview.flushEdits(window.view));
  assert.equal(requests.at(-1).recipe.levels.contrast, 1);
  await page.getByRole('button', { name: 'HNCS HiCon', exact: true }).click();
  await page.evaluate(() => window.scene.preview.flushEdits(window.view));
  await page.getByRole('button', { name: 'M9 STD', exact: true }).click();
  await page.evaluate(() => window.scene.preview.flushEdits(window.view));
  assert.equal(requests.at(-1).recipe.levels.contrast, 1);
  await page.getByRole('button', { name: 'FCC*002', exact: true }).click();
  await page.evaluate(() => window.scene.preview.flushEdits(window.view));
  assert.equal(requests.at(-1).recipe.kind, 'camera_user');
  assert.equal(requests.at(-1).recipe.id, catalog.units[2].users[1].id);
  await page.evaluate(() => {
    window.view.ed.recipe.id = '0'.repeat(64);
    window.view.redrawSide();
  });
  assert.equal(await page.getByText('找不到这个配方。请重新选择。', { exact: true }).count(), 1);
  await page.getByRole('button', { name: '04 标准', exact: true }).click();
  await page.evaluate(() => window.scene.preview.flushEdits(window.view));
  assert.equal(requests.at(-1).recipe.kind, 'builtin');
  assert.equal(requests.at(-1).recipe.id, undefined);
  holdNextCatalog = true;
  catalogHeld = new Promise((done) => { notifyCatalogHeld = done; });
  await page.evaluate(() => {
    window.scene.shared.state.catalog = null;
    window.oldCatalog = window.scene.preview.loadCatalog();
  });
  await catalogHeld;
  await page.evaluate(() => window.scene.preview.loadCatalog({ refresh: true }));
  await releaseCatalog();
  const afterPending = await page.evaluate(async () => {
    await window.oldCatalog;
    return window.scene.shared.state.catalog.units[2].looks.length;
  });
  assert.equal(afterPending, 10);
  const transitions = [];
  for (const result of ['unsupported', 'ready']) {
    scenario = 'missing'; importResult = result; saved = null;
    await page.evaluate((id) => window.showPanel('missing', id), `transition-${result}`);
    const file = page.locator('input[type=file]');
    await file.setInputFiles({ name: 'GXRCE.DAT', mimeType: 'application/octet-stream', buffer: Buffer.alloc(256) });
    if (result === 'ready') {
      await page.locator('.base-grid button').nth(20).waitFor();
      assert.equal(await page.locator('.base-grid button[aria-disabled=true]').count(), 0);
    } else {
      await page.getByRole('heading', { name: supported, exact: true }).waitFor();
      assert.equal((await page.locator('#panel').innerText()).includes('配方需要 RAW 文件'), false);
    }
    transitions.push(result);
  }
  scenario = 'missing'; saved = null;
  await page.evaluate(() => window.showPanel('missing', 'multiple-cards'));
  await page.getByRole('button', { name: '从存储卡导入配方', exact: true }).click();
  await page.getByRole('button', { name: '从「第一张」导入', exact: true }).waitFor({ timeout: 1500 });
  assert.equal(await page.getByRole('button', { name: '从「第二张」导入', exact: true }).count(), 1);
  await page.getByRole('button', { name: '从「第一张」导入', exact: true }).click();
  await page.locator('.base-grid button').nth(20).waitFor();
  assert.deepEqual(errors, []);
  const report = { status: 'PASS', runtime: { playwright: runtime.playwrightVersion, chromium: runtime.chromiumRevision },
    states, transitions, recipe_order: names, saved_changes: requests.length, mount_label: '未校准',
    missing_selection_reselectable: true, catalog_inflight_refresh: true, multiple_card_choices: 2, page_errors: errors };
  await writeFile(join(here, 'ui.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
} finally {
  clearTimeout(deadline);
  await context.close();
  await browser.close();
}
