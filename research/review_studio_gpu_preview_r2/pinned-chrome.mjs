import { launchPinnedChromium, verifyPinnedRuntime } from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
import { appendFileSync } from 'node:fs';

const input = process.argv.slice(2);
const url = input.findLast((arg) => /^http:\/\/127\.0\.0\.1:\d+\//.test(arg));
if (!url) throw new Error('A review-owned loopback page is required');
const args = input.filter((arg) => arg !== url && !arg.startsWith('--headless') && !arg.startsWith('--user-data-dir='));
const log = new URL('./pinned-chrome-launches.jsonl', import.meta.url);
appendFileSync(log, JSON.stringify({ event: 'start', pid: process.pid, url, pin: verifyPinnedRuntime(), args }) + '\n');
const browser = await launchPinnedChromium({ args, timeout: 60000 });
let closing = false;
async function close(signal) {
  if (closing) return;
  closing = true;
  await browser.close();
  appendFileSync(log, JSON.stringify({ event: 'closed', pid: process.pid, signal }) + '\n');
  process.exit(0);
}
process.on('SIGTERM', () => void close('SIGTERM'));
process.on('SIGINT', () => void close('SIGINT'));
const page = await browser.newPage();
page.on('pageerror', (e) => appendFileSync(log, JSON.stringify({ event: 'pageerror', message: String(e) }) + '\n'));
await page.goto(url, { timeout: 60000 });
await new Promise(() => {});
