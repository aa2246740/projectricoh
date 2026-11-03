import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { launchPinnedChromium } from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
const here = path.dirname(fileURLToPath(import.meta.url));
const scratch = '/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2';
process.env.TMPDIR = scratch;
const ready = JSON.parse(await readFile(path.join(scratch, 'server-ready.json'), 'utf8'));
const base = `http://127.0.0.1:${ready.port}`;
const browser = await launchPinnedChromium({ env: { ...process.env, TMPDIR: scratch } });
const results = [];
try {
  const context = await browser.newContext({ viewport: { width: 1360, height: 860 }, colorScheme: 'dark' });
  const page = await context.newPage();
  await page.goto(ready.url);
  const request = async (method, url, data) => {
    const response = await page.request.fetch(base + url, { method, data,
      headers: { 'X-GXR-Token': 'independent-review-browser' } });
    if (!response.ok()) throw Error(`${url}: ${response.status()}`);
    return response.json();
  };
  const photos = await request('GET', '/api/photos');
  const id = photos.find(p => p.name === 'REVIEW').id;
  await request('DELETE', `/api/photos/${id}/edit`);
  await request('DELETE', `/api/photos/${id}/crop`);
  await request('PUT', '/api/defaults/finish', { frame: { style: 'none' }, stamp: { enabled: false } });
  await page.goto(base + `/#/photo/${id}`);
  await page.getByRole('tab', { name: '边框', exact: true }).click();
  for (const size of [{ width: 1360, height: 860 }, { width: 1024, height: 768 }]) {
    await page.setViewportSize(size);
    await page.waitForFunction(() => document.querySelectorAll('.fcard img').length === 7 &&
      [...document.querySelectorAll('.fcard img')].every(i => i.complete && i.naturalWidth > 0) &&
      document.querySelector('.pv-img')?.complete && !document.querySelector('.status .right')?.textContent);
    results.push({ viewport: size, cards: await page.locator('.fcard').evaluateAll(es => es.map(e => {
      const i = e.querySelector('img'); const box = i.getBoundingClientRect();
      return { name: e.innerText, natural: [i.naturalWidth, i.naturalHeight],
        display: [box.width, box.height], fit: getComputedStyle(i).objectFit };
    })) });
    await page.screenshot({ path: path.join(here, `ui-frame-settled-${size.width}.png`), fullPage: true });
  }
  await page.close();
  await context.close();
} finally {
  await browser.close();
  await writeFile(path.join(here, 'visual-check.json'), JSON.stringify(results, null, 2) + '\n');
}
