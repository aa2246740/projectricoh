import { appendFileSync } from 'node:fs';
import { launchPinnedChromium, verifyPinnedRuntime } from '/Users/wu/.codex/playwright-runtime/runtime.mjs';

const scratch = '/Volumes/Workspace/Scratch/tmp/projectricoh/studio-gpu-fix-r3/';
if (!process.env.TMPDIR?.startsWith(scratch)) throw new Error('Expected the task temporary directory');
const input = process.argv.slice(2);
const url = input.findLast(arg => /^http:\/\/127\.0\.0\.1:\d+\//.test(arg));
if (!url || new URL(url).port === '49667') throw new Error('Expected a test-owned port');
const args = input.filter(arg => arg !== url && !arg.startsWith('--headless') && !arg.startsWith('--user-data-dir='));
const log = new URL('./browser-lifecycle.jsonl', import.meta.url);
const record = row => appendFileSync(log, JSON.stringify({ pid: process.pid, ...row }) + '\n');
record({ event: 'start', url, pin: verifyPinnedRuntime(), args, temporaryRoot: process.env.TMPDIR });
const browser = await launchPinnedChromium({ args, timeout: 60000 });
let end;
const ended = new Promise(resolve => { end = resolve; });
process.once('SIGTERM', () => end('SIGTERM'));
process.once('SIGINT', () => end('SIGINT'));
try {
  const page = await browser.newPage();
  page.on('request', request => {
    if (request.url() === new URL('/done', url).href) {
      record({ event: 'engine-summary', data: JSON.parse(request.postData() || '{}') });
    }
  });
  page.on('pageerror', error => record({ event: 'pageerror', message: String(error) }));
  await page.goto(url, { timeout: 60000 });
  record({ event: 'test-end', signal: await ended });
} finally {
  await browser.close();
  record({ event: 'closed' });
}
