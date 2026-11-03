// 用实际 DAT 目录响应运行产品面板，检查四包的名称、顺序和选择。
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve, join, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { launchPinnedChromium, verifyPinnedRuntime } from '/Users/wu/.codex/playwright-runtime/runtime.mjs';

const here = fileURLToPath(new URL('.', import.meta.url));
const assets = resolve(here, '../../studio/web/assets');
const scratch = '/Volumes/Workspace/Scratch/tmp/projectricoh/studio-g154-g155-r1';
assert.equal(process.env.TMPDIR, scratch);
const runtime = verifyPinnedRuntime();
const browser = await launchPinnedChromium({ args: ['--single-process', '--in-process-gpu', '--no-zygote'] });
const context = await browser.newContext({ viewport: { width: 1200, height: 1400 } });
const page = await context.newPage();
const errors = [];
const results = [];
let catalog;
let generation;
let variant;
let saved;
let revision = 0;
let lastSaved;
page.on('pageerror', (error) => errors.push(String(error)));
try {
  await page.route('**/*', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
    if (path === '/') return route.fulfill({ contentType: 'text/html', body: '<!doctype html><link rel="stylesheet" href="/assets/app.css"><main id="panel"></main><div id="toast-root"></div><div id="modal-root"></div>' });
    if (path.startsWith('/assets/') && basename(path) === path.slice(8)) {
      return route.fulfill({ contentType: path.endsWith('.css') ? 'text/css' : 'text/javascript', body: await readFile(join(assets, basename(path))) });
    }
    if (path === '/api/luts') return json({ luts: [], groups: [] });
    if (path === '/api/recipes') return json(catalog);
    if (path === '/api/camdata/status') return json({ ready: true, data_version: `${generation}-${variant}`,
      camera_data: { state: 'ready', generation }, calibration: { state: 'ready' } });
    if (path.endsWith('/capabilities')) return json({ raw: true, recipe: 'full' });
    if (path.endsWith('/edit')) {
      if (request.method() === 'PUT') { lastSaved = request.postDataJSON().recipe; saved = lastSaved; revision++; }
      return json({ rev: revision, recipe: saved, render: { available: true } });
    }
    if (path.includes('/render')) return route.fulfill({ contentType: 'image/jpeg', body: Buffer.from([255, 216, 255, 217]) });
    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: 'not_found' }) });
  });
  for (generation of [154, 155]) {
    for (variant of [0, 1]) {
      catalog = JSON.parse(await readFile(join(scratch, `catalog-${generation}-${variant}.json`), 'utf8'));
      await page.goto('http://studio.test/');
      await page.evaluate(async () => {
        const recipes = await import('/assets/recipes.js');
        const preview = await import('/assets/preview.js');
        const camera = await import('/assets/camdata.js');
        const shared = await import('/assets/state.js');
        window.scene = { recipes, preview, camera, shared };
      });
      for (const unit of catalog.units) {
        saved = null;
        const id = `${generation}-${variant}-${unit.id}`;
        await page.evaluate(async ({ id, unit }) => {
          const { recipes, preview, camera } = window.scene;
          await camera.loadCamdata();
          const lens = { jlaunch: '50mm', qlaunch: '28mm', l08firm: 'MOUNT' }[unit];
          const view = { photo: { id, has_raw: true, lens } };
          await preview.ensureEdit(view);
          view.redrawSide = () => document.getElementById('panel').replaceChildren(recipes.recipePanel(view));
          view.redrawSide();
          window.view = view;
        }, { id, unit: unit.id });
        const buttons = page.locator('.base-grid button');
        const names = await buttons.allTextContents();
        assert.equal(names.length, 8 + unit.looks.length + unit.users.length);
        assert.deepEqual(names.slice(8), [...unit.looks, ...unit.users].map((item) => item.name));
        assert.equal(await page.locator('.base-grid button[aria-disabled=true]').count(), 0);
        assert.equal(await page.getByText('未校准', { exact: true }).count(), unit.id === 'jlaunch' ? 0 : 1);
        for (const item of [...unit.looks, ...unit.users]) {
          await page.getByRole('button', { name: item.name, exact: true }).click();
          await page.evaluate(() => window.scene.preview.flushEdits(window.view));
          assert.equal(lastSaved.kind, item.kind);
          assert.equal(lastSaved.id, item.id);
          assert.equal(lastSaved.unit, unit.id);
        }
        results.push({ generation, test: Boolean(variant), unit: unit.id, looks: unit.looks.length, users: unit.users.length,
          order: names, selections: unit.looks.length + unit.users.length });
      }
    }
  }
  assert.deepEqual(errors, []);
  const result = { status: 'PASS', runtime: { playwright: runtime.playwrightVersion, chromium: runtime.chromiumRevision },
    panels: results.length, selections: results.reduce((n, r) => n + r.selections, 0), page_errors: errors, results };
  await writeFile(join(here, 'ui.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result));
} finally {
  await context.close();
  await browser.close();
}
