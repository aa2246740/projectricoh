// Code-driven offline fixtures, pinned runtime only. No interactive browser.
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { launchPinnedChromium, pinnedRuntime } from '/Users/wu/.codex/playwright-runtime/runtime.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const out = path.join(here, 'local/synthetic-pages');
await mkdir(out, { recursive: true });
const templates = path.join(here, 'local/header-templates');
await mkdir(templates, { recursive: true });
const browser = await launchPinnedChromium();
try {
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 }, offline: true });
  await context.route('**/*', route => route.abort());
  const page = await context.newPage();
  await page.setContent(await readFile(path.join(root, 'research/color_references/screen_chart.html'), 'utf8'));
  await page.keyboard.press('h');
  const pages = [];
  for (let i = 0; i < 8; i++) {
    await page.keyboard.press(String(i + 1));
    const record = await page.evaluate(() => {
      const title = document.getElementById('title');
      const range = document.createRange();
      range.setStart(title.firstChild, 0);
      range.setEnd(title.firstChild, 2);
      return {
        id: window.gxrChart.data.pages[window.gxrChart.getPage()].id,
        rois: window.gxrChart.getROIs(),
        header: range.getBoundingClientRect().toJSON(),
      };
    });
    const filename = `${String(i + 1).padStart(2, '0')}_${record.id}.png`;
    await page.screenshot({ path: path.join(out, filename) });
    const b = record.header;
    await page.screenshot({ path: path.join(templates, `${record.id}.png`),
      clip: { x: Math.floor(b.x) - 1, y: Math.max(0, Math.floor(b.y) - 1), width: Math.ceil(b.width) + 2, height: Math.ceil(b.height) + 2 } });
    pages.push({ ...record, filename });
  }
  await writeFile(path.join(out, 'render.json'), JSON.stringify({
    synthetic: true, runtime: pinnedRuntime, viewport: { width: 1600, height: 1000 }, pages,
  }, null, 2));
  console.log(`Rendered ${pages.length} offline pages to ${out}`);
} finally {
  await browser.close();
}
