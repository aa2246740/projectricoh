import {launchPinnedChromium, verifyPinnedRuntime} from '/Users/wu/.codex/playwright-runtime/runtime.mjs';
import {readFile, writeFile} from 'node:fs/promises';
import {createServer} from 'node:http';
import {createHash} from 'node:crypto';
import {getPriority} from 'node:os';

const root = '/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r5';
const output = process.env.REVIEW_R5_OUTPUT || '/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_studio_gpu_preview_r5';
const label = process.argv[2];
if (!['r2-colour','r4-colour','current-colour'].includes(label)) throw new Error('Unknown case');
const temporary = `${root}/fixtures/${label}/browser`;
const runtime = verifyPinnedRuntime();
process.env.TMPDIR = `${root}/tmp`;
const paths = JSON.parse(await readFile(`${temporary}/files.json`, 'utf8'));
const files = new Map(Object.entries(paths).map(([key, value]) => [key, value]));
files.set('/cases.json', `${temporary}/cases.json`);
files.set('/harness.mjs', `${root}/source/tests/support/gpu_harness.mjs`);
files.set('/engine.js', `${root}/source/web/assets/gpu/engine.js`);
const images = {};
const requests = [];
const pageErrors = [];
let summary;
let resolveDone;
const done = new Promise(resolve => {resolveDone = resolve;});
const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://127.0.0.1');
    requests.push({method:req.method, path:url.pathname, at:new Date().toISOString()});
    if (req.method === 'POST') {
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      const body = Buffer.concat(chunks);
      if (url.pathname.startsWith('/result/')) {
        const cid = url.pathname.slice('/result/'.length);
        if (!/^[a-z0-9_]+$/.test(cid)) throw new Error('Invalid case id');
        const file = `${temporary}/result-${cid}.rgba`;
        await writeFile(file, body);
        images[cid] = {w:Number(url.searchParams.get('w')), h:Number(url.searchParams.get('h')), file, sha256:createHash('sha256').update(body).digest('hex')};
      } else if (url.pathname === '/done') {
        summary = JSON.parse(body.toString());
        resolveDone();
      }
      res.writeHead(204).end();
    } else if (url.pathname === '/') {
      res.writeHead(200, {'content-type':'text/html'}).end('<!doctype html><meta charset="utf-8"><script type="module" src="/harness.mjs"></script>');
    } else if (files.has(url.pathname)) {
      const body = await readFile(files.get(url.pathname));
      const type = /\.(mjs|js)$/.test(url.pathname) ? 'text/javascript' : 'application/octet-stream';
      res.writeHead(200, {'content-type':type, 'content-length':body.length}).end(body);
    } else res.writeHead(404).end();
  } catch (error) {
    pageErrors.push(String(error));
    res.writeHead(500).end();
  }
});
let browser;
let timer;
let browserClosed = false;
const started = new Date().toISOString();
const chromeArgs = ['--single-process','--no-zygote','--disable-crash-reporter','--disable-breakpad','--disable-background-networking','--enable-unsafe-webgpu','--enable-unsafe-swiftshader','--use-webgpu-adapter=swiftshader'];
try {
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  const port = server.address().port;
  if (port === 49667) throw new Error('Reserved port selected');
  browser = await launchPinnedChromium({args:chromeArgs, env:{...process.env, HOME:`${root}/home`, TMPDIR:`${root}/tmp`, TMP:`${root}/tmp`, TEMP:`${root}/tmp`}});
  const context = await browser.newContext();
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.hostname === '127.0.0.1' && Number(url.port) === port) await route.continue();
    else {pageErrors.push(`Rejected request ${url.origin}`);await route.abort();}
  });
  const page = await context.newPage();
  page.on('pageerror', error => pageErrors.push(String(error)));
  const deadline = new Promise((_,reject) => {timer=setTimeout(()=>reject(new Error('GPU deadline exceeded')),180000);});
  await page.goto(`http://127.0.0.1:${port}/`);
  await Promise.race([done,deadline]);
  if (summary.error || pageErrors.length) throw new Error(JSON.stringify({summary,pageErrors}));
  await writeFile(`${temporary}/gpu-result.json`,JSON.stringify({images,summary},null,2)+'\n');
  console.log(JSON.stringify({label,images:Object.keys(images).length,summary}));
} finally {
  clearTimeout(timer);
  if (browser) {await browser.close();browserClosed=!browser.isConnected();}
  await new Promise(resolve=>server.close(resolve));
  await writeFile(`${output}/cases/${label}/browser-receipt.json`,JSON.stringify({label,started,finished:new Date().toISOString(),nice:getPriority(),runtime,chromeArgs,browserClosed,pageErrors,requests,summary},null,2)+'\n');
}
