import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const out = path.dirname(fileURLToPath(import.meta.url));
const label = process.env.LUT_CHECK_LABEL || 'ui';
const studio = path.resolve(out, '../../studio');
const originalHome = process.env.HOME;
process.env.HOME = '/Users/wu';
const { launchPinnedChromium, pinnedRuntime } = await import('/Users/wu/.codex/playwright-runtime/runtime.mjs');
process.env.HOME = originalHome;
const bridge = spawn(path.join(studio, '.venv/bin/python'), ['-B', path.join(out, 'ui_bridge.py')], {
  cwd: studio, env: { ...process.env, PYTHONUNBUFFERED: '1' }, stdio: ['pipe', 'pipe', 'inherit'],
});
let next = 1;
const pending = new Map();
let readyResolve;
const ready = new Promise((resolve) => { readyResolve = resolve; });
createInterface({ input: bridge.stdout }).on('line', (line) => {
  const result = JSON.parse(line);
  if (result.ready) readyResolve(result);
  else {
    const promise = pending.get(result.id);
    pending.delete(result.id);
    if (result.error) promise.reject(new Error(result.error));
    else promise.resolve(result);
  }
});
bridge.on('exit', (code) => {
  if (code) {
    for (const entry of pending.values()) entry.reject(new Error(`ASGI bridge exited ${code}`));
  }
});
function request(method, url, body, headers = {}) {
  return new Promise((resolve, reject) => {
    const id = next++;
    pending.set(id, { resolve, reject });
    bridge.stdin.write(JSON.stringify({ id, method, url, body: body.toString('base64'), headers }) + '\n');
  });
}

const evidence = { runtime: pinnedRuntime, checks: [], screenshots: [], console_errors: [], network: 'All requests fulfilled by ASGI TestClient' };
let browser;
try {
  let setupTimer;
  const fixture = await Promise.race([ready, new Promise((_, reject) => { setupTimer = setTimeout(() => reject(new Error('ASGI setup timed out')), 30000); })]);
  clearTimeout(setupTimer);
  browser = await launchPinnedChromium();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1 });
  page.on('pageerror', (e) => evidence.console_errors.push(e.message));
  await page.route('**/*', async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    assert.equal(url.origin, 'http://127.0.0.1:8765');
    const res = await request(req.method(), url.pathname + url.search, req.postDataBuffer() || Buffer.alloc(0), req.headers());
    const headers = { ...res.headers };
    delete headers['content-length'];
    await route.fulfill({ status: res.status, headers, body: Buffer.from(res.body, 'base64') });
  });
  async function save(name) {
    const filename = `${label}_${name}.png`;
    await page.screenshot({ path: path.join(out, filename), fullPage: true });
    evidence.screenshots.push(filename);
    evidence.checks.push({ name, overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth) });
  }
  async function snapshot(selector, name) {
    const html = await page.evaluate(async ({ selector }) => {
      const source = document.querySelector(selector);
      const clone = source.cloneNode(true);
      for (const [index, el] of [...source.querySelectorAll('textarea')].entries()) clone.querySelectorAll('textarea')[index].textContent = el.value;
      const css = await (await fetch('/assets/app.css')).text();
      return '<!doctype html><html lang="zh-CN" data-theme="light"><meta charset="utf-8"><style>' + css +
        '</style><body><main class="lut-page" style="padding:24px">' + clone.outerHTML + '</main></body></html>';
    }, { selector });
    await fs.writeFile(path.join(out, `${label}_${name}.html`), html);
  }
  async function list() {
    return page.evaluate(async () => (await fetch('/api/luts')).json());
  }
  await page.goto('http://127.0.0.1:8765/#/recipes');
  await page.getByText('还没有 LUT', { exact: true }).waitFor();
  await save('ui_empty');
  await page.locator('input[aria-label="导入 LUT"]').setInputFiles([
    path.join(fixture.fixtures, 'demo_srgb.cube'), path.join(fixture.fixtures, 'other.cube'),
    path.join(fixture.fixtures, 'other.3dl'), path.join(fixture.fixtures, 'broken.cube'),
  ]);
  await page.getByText('other.3dl · 不支持这种 LUT 格式', { exact: true }).waitFor();
  await page.getByRole('button', { name: '<b>合成 LUT</b>', exact: true }).waitFor();
  assert.equal(await page.locator('.lut-library-name b').count(), 0);
  assert.equal((await list()).luts.length, 2);
  await save('ui_imported');
  await snapshot('[data-ud-check="lut-library"]', 'library_snapshot');
  const selected = (await list()).luts.find((l) => l.name === '<b>合成 LUT</b>');
  const row = page.locator('.lut-library-row').filter({ has: page.getByRole('button', { name: selected.name, exact: true }) });
  await row.getByRole('button', { name: '标星', exact: true }).click();
  await row.getByRole('button', { name: '取消标星', exact: true }).waitFor();
  await page.getByLabel('已标星', { exact: true }).check();
  assert.equal(await page.locator('.lut-library-row').count(), 1);
  await page.getByLabel('已标星', { exact: true }).uncheck();
  page.once('dialog', (dialog) => dialog.accept('测试分组'));
  await page.getByRole('button', { name: '新建分组', exact: true }).click();
  await page.getByLabel('分组', { exact: true }).selectOption('');
  const group = (await list()).groups.find((g) => g.name === '测试分组');
  await page.getByLabel('LUT 分组', { exact: true }).selectOption(group.id);
  await page.getByLabel('来源', { exact: true }).fill('合成来源');
  await page.getByLabel('作者', { exact: true }).fill('合成作者');
  await page.getByLabel('许可', { exact: true }).fill('CC BY-SA 4.0\n保留署名');
  await page.getByRole('button', { name: '存储', exact: true }).click();
  await page.getByText('已存储', { exact: true }).waitFor();
  assert.equal((await list()).luts.find((l) => l.cube_id === selected.cube_id).author, '合成作者');
  const oldPreview = await page.locator('.lut-img').getAttribute('src');
  await page.getByLabel('输入色彩空间', { exact: true }).selectOption('gamma24');
  await page.waitForFunction(async () => (await (await fetch('/api/luts')).json()).luts.some((l) => l.input_space === 'gamma24'));
  await page.waitForFunction((old) => document.querySelector('.lut-img')?.getAttribute('src') !== old, oldPreview);
  await page.getByLabel('许可', { exact: true }).scrollIntoViewIfNeeded();
  await save('ui_attribution');
  await snapshot('[data-ud-check="lut-attribution"]', 'attribution_snapshot');
  await page.getByLabel('分组', { exact: true }).selectOption(group.id);
  await page.getByRole('button', { name: '导出分组', exact: true }).click();
  await page.getByRole('dialog', { name: '已导出 1 个 LUT' }).waitFor();
  await save('ui_export');
  await page.getByRole('dialog').locator('button[title="关闭"]').click();
  await page.getByLabel('分组', { exact: true }).selectOption('');
  await page.getByRole('button', { name: '导入 LUT', exact: true }).click();
  await page.locator('input[aria-label="导入文件夹"]').setInputFiles(path.join(fixture.fixtures, 'Folder'));
  await page.getByRole('button', { name: '文件夹 LUT', exact: true }).waitFor();
  const afterFolder = await list();
  assert.equal(afterFolder.luts.length, 3);
  assert.ok(afterFolder.groups.some((g) => g.name === 'Folder'));
  assert.ok(afterFolder.luts.every((l) => !l.name.startsWith('不会导入')));
  await save('ui_folder');
  const folderRow = page.locator('.lut-library-row').filter({ has: page.getByRole('button', { name: '文件夹 LUT', exact: true }) });
  await folderRow.getByRole('button', { name: '删除', exact: true }).click();
  await page.getByRole('dialog', { name: '删除「文件夹 LUT」？' }).waitFor();
  assert.equal(await page.evaluate(() => document.activeElement?.textContent), '取消');
  await save('ui_delete_confirmation');
  await page.keyboard.press('Enter');
  await page.getByRole('dialog').waitFor({ state: 'hidden' });
  assert.equal((await list()).luts.length, 3);
  await folderRow.getByRole('button', { name: '删除', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: '删除', exact: true }).focus();
  await page.keyboard.press('Enter');
  assert.equal(await page.getByRole('dialog').isVisible(), true);
  assert.equal((await list()).luts.length, 3);
  await page.getByRole('dialog').getByRole('button', { name: '删除', exact: true }).click();
  await page.getByRole('dialog').waitFor({ state: 'hidden' });
  assert.equal((await list()).luts.length, 2);
  await page.getByLabel('分组', { exact: true }).selectOption(group.id);
  await page.getByRole('button', { name: '删除分组', exact: true }).click();
  assert.equal(await page.evaluate(() => document.activeElement?.textContent), '取消');
  await page.keyboard.press('Enter');
  await page.getByRole('dialog').waitFor({ state: 'hidden' });
  assert.ok((await list()).groups.some((g) => g.id === group.id));
  await page.getByRole('button', { name: '删除分组', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: '删除', exact: true }).focus();
  await page.keyboard.press('Enter');
  assert.ok((await list()).groups.some((g) => g.id === group.id));
  await page.getByRole('dialog').getByRole('button', { name: '删除', exact: true }).click();
  await page.getByRole('dialog').waitFor({ state: 'hidden' });
  assert.ok(!(await list()).groups.some((g) => g.id === group.id));
  assert.equal((await list()).luts.length, 2);
  const recipeRow = page.locator('.recipe-card').filter({ has: page.getByText('确认测试配方', { exact: true }) });
  await recipeRow.getByRole('button', { name: '删除', exact: true }).click();
  assert.equal(await page.evaluate(() => document.activeElement?.textContent), '取消');
  await page.keyboard.press('Enter');
  await page.getByRole('dialog').waitFor({ state: 'hidden' });
  assert.equal(await page.evaluate(async () => (await (await fetch('/api/my-recipes')).json()).recipes.length), 1);
  await recipeRow.getByRole('button', { name: '删除', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: '删除', exact: true }).focus();
  await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(async () => (await (await fetch('/api/my-recipes')).json()).recipes.length), 1);
  await page.getByRole('dialog').getByRole('button', { name: '删除', exact: true }).click();
  await page.getByRole('dialog').waitFor({ state: 'hidden' });
  assert.equal(await page.evaluate(async () => (await (await fetch('/api/my-recipes')).json()).recipes.length), 0);
  evidence.confirmations = { lut: 'passed', group: 'passed', recipe: 'passed', default_focus: '取消', enter_confirms: false };
  await page.goto(`http://127.0.0.1:8765/#/photo/${fixture.photo_id}`);
  await page.getByLabel('LUT', { exact: true }).selectOption(selected.cube_id);
  await page.waitForFunction(async (id) => (await (await fetch('/api/photos/' + id + '/edit')).json()).lut !== null, fixture.photo_id);
  await page.locator('.pv-img').waitFor();
  await save('ui_photo_lut');
  await snapshot('[data-ud-check="photo-lut"]', 'photo_lut_snapshot');
  await page.goto('http://127.0.0.1:8765/#/recipes');
  await page.getByRole('button', { name: '导入 LUT', exact: true }).click();
  await page.locator('.dropzone').waitFor();
  await page.evaluate(() => {
    const text = 'TITLE "拖入 LUT"\nLUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 1\n1 0 1\n0 1 1\n1 1 1\n';
    const file = new File([text], 'drop_srgb.cube');
    const entry = {name:'drop_srgb.cube',isFile:true,file:(resolve)=>resolve(file)};
    const folder = {name:'DropFolder',isDirectory:true,createReader:()=>{let read=false;return {readEntries:(resolve)=>{resolve(read?[]:[entry]);read=true;}};}};
    const transfer = new DataTransfer();
    Object.defineProperty(transfer,'items',{value:[{webkitGetAsEntry:()=>folder}]});
    document.querySelector('.dropzone').dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
  });
  await page.getByRole('button', { name: '拖入 LUT', exact: true }).waitFor();
  assert.ok((await list()).groups.some((g) => g.name === 'DropFolder'));
  await save('ui_drop_folder');
  await page.getByRole('button', { name: '导入 LUT', exact: true }).click();
  await page.locator('input[aria-label="导入 LUT"]').setInputFiles(path.join(fixture.fixtures, 'conflict_vlog.cube'));
  await page.getByRole('button', { name: '空间冲突', exact: true }).waitFor();
  await page.waitForFunction(() => document.querySelector('.empty-img')?.textContent === '请选择输入色彩空间');
  assert.equal(await page.getByLabel('输入色彩空间', { exact: true }).inputValue(), '');
  assert.equal(await page.getByLabel('输入色彩空间', { exact: true }).locator('option').count(), 13);
  assert.equal(await page.getByRole('button', { name: '生成配方', exact: true }).isDisabled(), true);
  await save('ui_unknown_space');
  await page.getByLabel('输入色彩空间', { exact: true }).selectOption('srgb');
  await page.waitForFunction(() => !document.querySelector('select[aria-label="输入色彩空间"]').disabled && !!document.querySelector('img.lut-img'));
  await page.getByRole('button', { name: selected.name, exact: true }).click();
  await page.getByLabel('输入色彩空间', { exact: true }).waitFor();
  await page.setViewportSize({ width: 375, height: 900 });
  await page.locator('[data-ud-check="lut-library"]').scrollIntoViewIfNeeded();
  await save('ui_narrow');
  assert.ok(evidence.checks.every((c) => !c.overflow));
  assert.deepEqual(evidence.console_errors, []);
  evidence.status = 'passed';
} catch (error) {
  evidence.status = 'failed';
  evidence.error = error.stack;
  throw error;
} finally {
  await fs.writeFile(path.join(out, `${label}_ui_check.json`), JSON.stringify(evidence, null, 2) + '\n');
  if (browser) await browser.close();
  bridge.stdin.end(JSON.stringify({ stop: true }) + '\n');
  await new Promise((resolve) => bridge.on('close', resolve));
}
console.log(JSON.stringify({ status: evidence.status, screenshots: evidence.screenshots.length, checks: evidence.checks.length }));
