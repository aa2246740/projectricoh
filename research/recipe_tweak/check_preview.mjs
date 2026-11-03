import fs from 'node:fs/promises';
import path from 'node:path';
import { homedir } from 'node:os';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';

const here = path.dirname(new URL(import.meta.url).pathname);
const local = path.join(here, 'local');
const { launchPinnedChromium, pinnedRuntime } = await import(pathToFileURL(
  path.join(homedir(), '.codex/playwright-runtime/runtime.mjs')).href);
const frames = JSON.parse(await fs.readFile(path.join(local, 'frames.json'), 'utf8'));
assert.equal(frames.length, 300);
for (const frame of frames) assert.ok((await fs.stat(path.join(local, frame.image))).size > 0);
const errors = [];
const browser = await launchPinnedChromium();
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 1100 } });
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.goto(pathToFileURL(path.join(local, 'preview.html')).href, { waitUntil: 'load' });
  assert.match(await page.title(), /模型模拟/);
  assert.equal(await page.locator('#levels button').count(), 5);
  assert.equal(await page.locator('#summary tr').count(), 20);
  await page.locator('#recipe').selectOption('03');
  await page.locator('#parameter').selectOption('saturation');
  await page.locator('#levels button').last().click();
  const bw = await page.evaluate(() => ({ text: document.querySelector('#stepnote').textContent,
    base: document.querySelector('#base').src, chosen: document.querySelector('#chosen').src }));
  assert.match(bw.text, /停用/);
  assert.equal(bw.base, bw.chosen);
  await page.locator('#scene').selectOption('apple');
  await page.locator('#recipe').selectOption('06');
  await page.locator('#parameter').selectOption('shadow');
  await page.locator('#levels button').last().click();
  await page.evaluate(() => Promise.all([...document.images].map(image => image.decode())));
  const selected = await page.evaluate(() => ({ caption: document.querySelector('#caption').textContent,
    metrics: document.querySelector('#metrics').textContent,
    base: document.querySelector('#base').src, chosen: document.querySelector('#chosen').src,
    overflow: document.documentElement.scrollWidth > innerWidth,
    broken: [...document.images].filter(image => !image.complete || !image.naturalWidth).length }));
  assert.match(selected.caption, /06.*阴影.*2/);
  assert.notEqual(selected.base, selected.chosen);
  assert.equal(selected.overflow, false);
  assert.equal(selected.broken, 0);
  await page.screenshot({ path: path.join(local, 'preview-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 900 });
  const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  assert.equal(mobileOverflow, false);
  await page.screenshot({ path: path.join(local, 'preview-mobile.png'), fullPage: true });
  assert.deepEqual(errors, []);
  await fs.writeFile(path.join(local, 'preview-check.json'), JSON.stringify({
    passed: true, previewRecords: frames.length, summaryRows: 20,
    BWSaturationDisabledAndIdentical: true, T1ShadowImageChanges: true,
    desktopOverflow: selected.overflow, mobileOverflow, brokenImages: selected.broken,
    consoleErrors: errors, selection: selected, pinnedRuntime,
  }, null, 2) + '\n');
  console.log(JSON.stringify({ passed: true, previewRecords: frames.length, desktopOverflow: false,
    mobileOverflow: false, consoleErrors: errors }));
} finally {
  await browser.close();
}
