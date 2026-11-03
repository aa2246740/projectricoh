import { appendFileSync } from 'node:fs';
process.env.HOME = '/Users/wu';
const { launchPinnedChromium, verifyPinnedRuntime } = await import('/Users/wu/.codex/playwright-runtime/runtime.mjs');
process.env.HOME = '/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r4/home';
const input = process.argv.slice(2);
const url = input.findLast(arg => /^http:\/\/127\.0\.0\.1:\d+\//.test(arg));
if (!url || new URL(url).port === '49667') throw new Error('Expected a review-owned port');
const args = input.filter(arg => arg !== url && !arg.startsWith('--headless') && !arg.startsWith('--user-data-dir='));
const log = new URL('file:///Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_gpu_preview_r4/browser-lifecycle.jsonl');
appendFileSync(log, JSON.stringify({event:'start',pid:process.pid,url,pin:verifyPinnedRuntime(),args})+'\n');
const browser = await launchPinnedChromium({args, timeout:60000});
let closing = false;
async function close(signal) {
  if (closing) return;
  closing = true;
  await browser.close();
  appendFileSync(log, JSON.stringify({event:'closed',pid:process.pid,signal})+'\n');
  process.exit(0);
}
process.on('SIGTERM', () => void close('SIGTERM'));
process.on('SIGINT', () => void close('SIGINT'));
const page = await browser.newPage();
page.on('request', request => {
  if (request.url() === new URL('/done', url).href) {
    appendFileSync(log, JSON.stringify({event:'engine-summary',pid:process.pid,data:JSON.parse(request.postData() || '{}')})+'\n');
  }
});
page.on('pageerror', error => appendFileSync(log, JSON.stringify({event:'pageerror',message:String(error)})+'\n'));
await page.goto(url, {timeout:60000});
await new Promise(() => {});
