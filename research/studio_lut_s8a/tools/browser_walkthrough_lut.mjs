// 浏览器走查（手动运行，不属于 pytest）：「配方」页的导入 LUT 流程。
//
//   运行：node research/studio_lut_s8a/tools/browser_walkthrough_lut.mjs     （截图写到 research/studio_lut_s8a/screenshots/）
//
// 脚本自己做的事：
//   1. 建临时目录（HOME、应用数据、图库、导出目录、卷根目录、Chrome 配置、上传用文件）；
//   2. 用 Python 把本机固件包里的 GXRCE.DAT 和研究目录里的标定文件现场导入临时应用数据目录（理光字节只在临时目录里）；
//   3. 造假卡（真实样本照片，只扫描临时卷根目录，不碰 /Volumes 下的真卡），启动 gxr-studio 和无头 Chrome，经 DevTools 协议发真实鼠标/键盘事件；
//   4. 走完流程；最后（无论成败）杀掉两个进程并删除整个临时目录。
// 同一时间进程数：本脚本（node）、gxr-studio、Chrome，加上拟合时 gxr-studio 的一个子进程。
import { spawn, execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '../../..');
const STUDIO = join(REPO, 'studio');
const SHOTS = join(HERE, '../screenshots');
mkdirSync(SHOTS, { recursive: true });

const DAT_127 = join(REPO, 'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT');
const SHA_127 = '9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6';
const SAMPLE_LUT = join(REPO, 'artifacts/downloads/huzi-panasonic-std-luts-20261024/original/Leica Chrome.cube');
const SERVER_PORT = 8798;
const CHROME_PORT = 9336;
const BASE = `http://127.0.0.1:${SERVER_PORT}`;
const TOKEN = 'toklut';
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const sha = (buf) => createHash('sha256').update(buf).digest('hex');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
const errors = [];
const badResponses = [];
const check = (name, ok, extra = '') => {
  const line = `${ok ? 'PASS' : 'FAIL'} ${name}${extra ? '  ' + extra : ''}`;
  results.push(line);
  console.log(line);
  return ok;
};
const phase = (name) => console.log(`\n== ${name}`);

const TMP = mkdtempSync(join(tmpdir(), 'gxrlut-'));
const P = { home: join(TMP, 'home'), app: join(TMP, 'home/app-data'), lib: join(TMP, 'lib'), exp: join(TMP, 'exp'), vol: join(TMP, 'vol'),
  stage: join(TMP, 'stage'), upload: join(TMP, 'upload'), profile: join(TMP, 'chrome-profile') };
for (const d of Object.values(P)) mkdirSync(d, { recursive: true });
let server = null;
let chrome = null;
let cleaned = false;

const waitExit = (child, ms) => new Promise((r) => {
  if (!child || child.exitCode !== null || child.signalCode) return r();
  const t = setTimeout(r, ms);
  child.once('exit', () => { clearTimeout(t); r(); });
});
async function cleanup() {
  if (cleaned) return;
  cleaned = true;
  for (const c of [chrome, server]) if (c && c.exitCode === null) c.kill('SIGTERM');
  await Promise.all([waitExit(chrome, 5000), waitExit(server, 8000)]);
  for (const c of [chrome, server]) if (c && c.exitCode === null) c.kill('SIGKILL');
  await Promise.all([waitExit(chrome, 2000), waitExit(server, 2000)]);
  for (let i = 0; i < 5 && existsSync(TMP); i++) {
    try { rmSync(TMP, { recursive: true, force: true }); } catch {}
    if (existsSync(TMP)) await sleep(500);
  }
  console.log(existsSync(TMP) ? `!! 临时目录没删掉：${TMP}` : `临时目录已删除：${TMP}`);
}
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, async () => { await cleanup(); process.exit(130); });

const api = (path, opts = {}) => fetch(BASE + path, { ...opts, headers: { 'X-GXR-Token': TOKEN, 'Content-Type': 'application/json', ...(opts.headers || {}) } });
const getJson = async (path) => (await api(path)).json();

let id = 0;
const pending = new Map();
let ws = null;
const send = (method, params = {}) => new Promise((resolveSend) => {
  const i = ++id;
  pending.set(i, resolveSend);
  ws.send(JSON.stringify({ id: i, method, params }));
});
const evaluate = async (expr) => {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result.exceptionDetails) throw new Error('eval: ' + JSON.stringify(r.result.exceptionDetails.exception?.description));
  return r.result.result.value;
};
const waitFor = async (expr, ms = 15000) => {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try { if (await evaluate(expr)) return true; } catch {}
    await sleep(150);
  }
  return false;
};
const mouse = async (x, y) => {
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
  await sleep(250);
};
const clickButton = async (text, root = '.lut-page') => {
  const box = await evaluate(`(() => {
    const el = [...document.querySelectorAll(${JSON.stringify(root + ' button, ' + root + ' a, ' + root + ' summary')})].find(b => b.textContent.trim().startsWith(${JSON.stringify(text)}) && !b.disabled);
    if (!el) return null;
    el.scrollIntoView({ block: 'center' });
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  })()`);
  if (!box) return false;
  await mouse(box.x, box.y);
  return true;
};
const clickSelector = async (sel) => {
  const box = await evaluate(`(() => {
    const el = document.querySelector(${JSON.stringify(sel)});
    if (!el) return null;
    el.scrollIntoView({ block: 'center' });
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  })()`);
  if (!box) return false;
  await mouse(box.x, box.y);
  return true;
};
const typeInto = async (selector, value) => {
  await evaluate(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); e.focus(); e.select(); })()`);
  await send('Input.insertText', { text: value });
  await sleep(100);
};
const chooseFile = async (selector, path) => {
  const r = await send('Runtime.evaluate', { expression: `document.querySelector(${JSON.stringify(selector)})` });
  await send('DOM.setFileInputFiles', { files: [path], objectId: r.result.result.objectId });
};
const text = (sel) => evaluate(`(document.querySelector(${JSON.stringify(sel)})||{}).textContent || ''`);
const shot = async (name) => {
  const r = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(join(SHOTS, name), Buffer.from(r.result.data, 'base64'));
};
const selectOption = (label, value) => evaluate(`(() => {
  const s = [...document.querySelectorAll('.lut-page select')].find(i => i.getAttribute('aria-label') === ${JSON.stringify(label)});
  if (!s) return false;
  s.value = ${JSON.stringify(value)};
  s.dispatchEvent(new Event('change', { bubbles: true }));
  return true;
})()`);
const imgPixels = () => evaluate(`(async () => {
  const img = document.querySelector('.lut-img');
  if (!img || !img.naturalWidth) return null;
  const c = document.createElement('canvas'); c.width = 64; c.height = 48;
  const g = c.getContext('2d'); g.drawImage(img, 0, 0, 64, 48);
  const d = g.getImageData(0, 0, 64, 48).data;
  let r = 0, gg = 0, b = 0;
  for (let i = 0; i < d.length; i += 4) { r += d[i]; gg += d[i + 1]; b += d[i + 2]; }
  return [r, gg, b].map((v) => Math.round(v / (d.length / 4)));
})()`);
const imgReady = () => waitFor(`(() => { const i = document.querySelector('.lut-img'); return !!i && i.tagName === 'IMG' && i.complete && i.naturalWidth > 0; })()`, 15000);

let exitCode = 1;
try {
  phase('0 准备（相机数据现场导入临时目录，假卡里放真实样本照片）');
  const dat = existsSync(DAT_127) ? readFileSync(DAT_127) : null;
  if (!check('本机固件包里有 g127 的 GXRCE.DAT（哈希对得上）', !!dat && sha(dat) === SHA_127)) throw new Error('缺少固件包里的 DAT');
  if (!check('本机有示例调色文件（胡子 Leica Chrome）', existsSync(SAMPLE_LUT))) throw new Error('缺少示例 LUT');
  const py = join(STUDIO, '.venv/bin/python');
  execFileSync(py, ['-B', '-c', `
import sys
from pathlib import Path
sys.path.insert(0, ${JSON.stringify(join(STUDIO, 'tests'))})
import e0_support as t
from gxr_studio.camdata import calib, store
h = Path(${JSON.stringify(P.app)})
store.import_from_dat(t.fixture_dat(127), h)
calib.import_calibration(h, calib.dev_sources(t.REPO))
`], { cwd: STUDIO, stdio: 'inherit' });
  execFileSync(py, ['-m', 'gxr_studio.devtools.synthetic_card', P.stage, '--label', 'FAKECARD'], { cwd: STUDIO, stdio: 'ignore' });
  copyFileSync(SAMPLE_LUT, join(P.upload, 'Leica Chrome 样例.cube'));
  writeFileSync(join(P.upload, 'notes.cube'), 'this is not a LUT file\n');

  server = spawn(join(STUDIO, '.venv/bin/gxr-studio'), ['--no-browser', '--port', String(SERVER_PORT)], {
    cwd: STUDIO, stdio: 'ignore',
    env: { ...process.env, HOME: P.home, GXR_STUDIO_HOME: P.app, GXR_STUDIO_LIBRARY: P.lib, GXR_STUDIO_EXPORT: P.exp, GXR_STUDIO_VOLUMES: P.vol, GXR_STUDIO_TOKEN: TOKEN },
  });
  let up = false;
  for (let i = 0; i < 80 && !up; i++) {
    try { up = (await fetch(BASE + '/')).status > 0; } catch { await sleep(250); }
  }
  check('服务器启动', up);
  chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run', `--remote-debugging-port=${CHROME_PORT}`,
    `--user-data-dir=${P.profile}`, '--window-size=1400,1000', 'about:blank'], { stdio: 'ignore' });
  let targets;
  for (let i = 0; i < 60; i++) {
    try { targets = await (await fetch(`http://127.0.0.1:${CHROME_PORT}/json`)).json(); if (targets.some((t) => t.type === 'page')) break; } catch {}
    await sleep(250);
  }
  ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener('open', r));
  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    if (msg.method === 'Runtime.exceptionThrown') {
      const d = msg.params.exceptionDetails;
      errors.push('exception: ' + (d.exception?.description || d.text) + ' @' + d.lineNumber);
    }
    if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') errors.push('console: ' + JSON.stringify(msg.params.args.map((a) => a.value || a.description)));
    if (msg.method === 'Network.responseReceived' && msg.params.response.status >= 400) badResponses.push(`${msg.params.response.status} ${new URL(msg.params.response.url).pathname}`);
  });
  for (const d of ['Page', 'Runtime', 'DOM', 'Network']) await send(`${d}.enable`);

  // 1. 插卡导入照片（预览要用）
  phase('1 导入照片');
  await send('Page.navigate', { url: `${BASE}/?token=${TOKEN}` });
  check('页面加载', await waitFor(`!!document.querySelector('#tabs a[data-tab=photos]')`));
  if (await waitFor(`!!document.querySelector('.modal-overlay')`, 4000)) await clickButton('跳过', '.modal');
  renameSync(join(P.stage, 'FAKECARD'), join(P.vol, 'FAKECARD'));
  check('导入完成', await waitFor(`/导入完成/.test(document.querySelector('#banner').textContent)`, 90000));
  const photos = await getJson('/api/photos?limit=5000');
  const sample = photos.find((p) => p.name.startsWith('R8051144'));
  check('图库里有 R8051144（真实样本，DNG+JPG）', !!sample);
  const st = await getJson('/api/camdata/status');
  check('相机数据和标定都已就绪', st.ready === true);

  // 2. 配方页
  phase('2 配方页：空状态');
  await send('Page.navigate', { url: `${BASE}/?token=${TOKEN}#/recipes` });
  check('配方标签不再写“即将推出”', await waitFor(`!!document.querySelector('#tabs a[data-tab=recipes]')`) && !/即将推出/.test(await text('#tabs a[data-tab=recipes]')));
  check('出现“导入调色文件（.cube）”和拖放区', await waitFor(`!!document.querySelector('.dropzone') && /导入调色文件/.test(document.querySelector('.lut-page').textContent)`));
  check('“我的配方”写着还没有', await waitFor(`/还没有/.test(document.querySelector('.lut-page').textContent)`));
  await shot('01-recipes-empty.png');

  // 3. 坏文件
  phase('3 不是 .cube 的文件');
  await chooseFile('.dropzone input[type=file]', join(P.upload, 'notes.cube'));
  check('大白话提示“这个文件看不懂。请选 .cube 格式的调色文件。”', await waitFor(`/这个文件看不懂/.test(document.querySelector('.lut-page').textContent)`, 8000));
  await shot('02-bad-file.png');

  // 4. 好文件
  phase('4 导入 Leica Chrome 样例（中文文件名）');
  await chooseFile('.dropzone input[type=file]', join(P.upload, 'Leica Chrome 样例.cube'));
  check('显示文件信息（3D · 33×33×33）', await waitFor(`/3D · 33×33×33/.test(document.querySelector('.lut-page').textContent)`, 10000));
  check('错误提示已清掉', !/这个文件看不懂/.test(await text('.lut-page')));
  check('问“这个调色文件是做什么用的？”并列出色彩空间', await evaluate(`(() => { const s = document.querySelector('.lut-page select[aria-label="这个调色文件是做什么用的"]'); return !!s && s.options.length >= 10 && /这个调色文件是做什么用的/.test(document.querySelector('.lut-page').textContent); })()`));
  check('文件里没写空间时提示要用户选，并标出输入空间是猜的', /输入空间是猜的/.test(await text('.lut-page')));
  check('预览图出来了（示意图）', await imgReady());
  check('预览说明写着“电脑预测”', /电脑预测/.test(await text('.lut-preview')));
  const pLut = await imgPixels();
  await clickButton('原图');
  await sleep(600);
  check('切到原图', await imgReady());
  const pOrig = await imgPixels();
  check('“原图”和“加 LUT 后”的图不一样', JSON.stringify(pLut) !== JSON.stringify(pOrig), `${JSON.stringify(pOrig)} vs ${JSON.stringify(pLut)}`);
  await shot('03-cube-loaded-chart.png');
  await clickButton('加 LUT 后');
  check('选一张自己的照片来预览', await selectOption('用哪张照片看效果', sample.id));
  check('预览改用 04 电脑模拟', await waitFor(`/04 电脑模拟/.test(document.querySelector('.lut-preview').textContent)`, 20000));
  await imgReady();
  await shot('04-cube-loaded-photo.png');
  await selectOption('这个调色文件是做什么用的', 'srgb');
  check('手动选了输入空间后，“猜的”提示消失', await waitFor(`!/输入空间是猜的：选错/.test(document.querySelector('.lut-page').textContent)`, 5000));

  // 5. 取消
  phase('5 做成相机配方：进度和取消');
  check('点“做成相机配方”', await clickButton('做成相机配方'));
  check('出现进度条和“取消”', await waitFor(`!!document.querySelector('.lut-page .progress') && [...document.querySelectorAll('.lut-page button')].some(b => b.textContent.trim() === '取消')`, 10000));
  check('进度在走（已试组合数 > 0）', await waitFor(`/已试 [1-9]\\d* 种组合/.test(document.querySelector('.lut-page').textContent)`, 30000));
  await shot('05-fitting.png');
  await clickButton('取消');
  check('取消后写着“已取消”，按钮回来', await waitFor(`/已取消/.test(document.querySelector('.lut-page').textContent) && [...document.querySelectorAll('.lut-page button')].some(b => b.textContent.trim() === '做成相机配方')`, 10000));

  // 6. 完整跑一次
  phase('6 完整拟合');
  const t0 = Date.now();
  check('再点“做成相机配方”', await clickButton('做成相机配方'));
  check('拟合完成，出现结果', await waitFor(`!!document.querySelector('.lut-result')`, 180000), `${Math.round((Date.now() - t0) / 1000)} 秒`);
  await sleep(500);
  const picks = await evaluate(`[...document.querySelectorAll('.lut-result .seg button')].map(b => b.textContent.trim())`);
  check('列出最接近的底子，每个带百分数', picks.length === 3 && picks.every((p) => /\d+%|N\/A/.test(p)), JSON.stringify(picks));
  const lutText = await text('.lut-result');
  check('写着“电脑预测相似度”和“相机实拍通常会低一些”', /电脑预测相似度/.test(lutText) && /相机实拍通常会低一些/.test(lutText));
  check('有“与原 LUT 的差别”说明', await evaluate(`document.querySelectorAll('.lut-result .diffs li').length >= 1`));
  const jobList = await getJson('/api/my-recipes');
  check('还没存之前我的配方是空的', jobList.recipes.length === 0);
  await shot('06-result.png');
  // 数字与结果文件一致：从服务器取最近一次拟合的结果，对比界面
  const shown = await evaluate(`document.querySelector('.lut-result .sim').textContent`);
  const dirs = execFileSync('ls', ['-t', join(P.app, 'lut_jobs')]).toString().trim().split('\n');
  let res = null;
  for (const d of dirs) {
    const r = JSON.parse(readFileSync(join(P.app, 'lut_jobs', d, 'result.json'), 'utf8'));
    if (r.state === 'done') { res = r.result; break; }
  }
  const best = res.candidates[0];
  check('界面上的相似度 = 结果文件里的数字（四舍五入）', best.similarity !== null && shown === `${Math.round(best.similarity)}%`, `${shown} vs ${best.similarity}`);
  check('底子按钮的顺序和结果文件一致', picks[0].startsWith(best.number));

  // 7. 换候选、三张图
  phase('7 换候选、看配方预测');
  await clickSelector('.lut-result .seg button:nth-child(2)');
  await sleep(300);
  check('换到第二个候选后数字跟着变', (await text('.lut-result .sim')) === `${Math.round(res.candidates[1].similarity)}%`);
  await clickButton('我们的配方预测', '.lut-preview');
  check('“我们的配方预测”能出图', await waitFor(`/配方预测（我们算的）/.test(document.querySelector('.lut-preview').textContent)`, 20000) && await imgReady());
  await shot('07-recipe-preview.png');
  await clickSelector('.lut-result .seg button:nth-child(1)');
  await sleep(300);

  // 8. 存下来
  phase('8 存为我的配方');
  await typeInto('.lut-result input[type=text]', '我的 Chrome 样例');
  await clickButton('存为我的配方', '.lut-result');
  check('存好后提示“只存在电脑里”', await waitFor(`/已存为「我的 Chrome 样例」/.test(document.querySelector('.lut-result').textContent)`, 8000));
  check('“我的配方”里出现这一条', await waitFor(`!!document.querySelector('.recipe-card') && /我的 Chrome 样例/.test(document.querySelector('.recipe-card').textContent)`, 5000));
  const saved = (await getJson('/api/my-recipes')).recipes;
  check('服务器上有这条，来源和相似度与结果一致', saved.length === 1 && saved[0].fit.similarity === best.similarity && saved[0].recipe.slot === best.slot, JSON.stringify(saved[0]?.recipe));
  await shot('08-saved.png');
  await send('Page.reload');
  check('刷新页面后“我的配方”还在', await waitFor(`!!document.querySelector('.recipe-card') && /我的 Chrome 样例/.test(document.querySelector('.lut-page').textContent)`, 10000));
  check('卡片上有“电脑预测相似度”和“相机短名”', /电脑预测相似度/.test(await text('.recipe-card')) && /相机短名 U01-/.test(await text('.recipe-card')));
  await shot('09-after-reload.png');

  // 9. 删除（两步确认）
  phase('9 删除');
  await clickButton('删除', '.recipe-card');
  check('第一次点：变成“再点一次”，没有删', /再点一次：删除/.test(await text('.recipe-card')) && (await getJson('/api/my-recipes')).recipes.length === 1);
  await clickButton('再点一次', '.recipe-card');
  check('第二次点：删掉了', await waitFor(`!document.querySelector('.recipe-card')`, 5000) && (await getJson('/api/my-recipes')).recipes.length === 0);

  // 10. 布局
  phase('10 布局和异常');
  check('页面没有横向溢出', await evaluate(`document.documentElement.scrollWidth <= window.innerWidth`));
  check('没有 JS 异常或控制台错误', errors.length === 0, errors.slice(0, 3).join(' | '));
  const unexpected = badResponses.filter((r) => !/^422 \/api\/lut\/upload$/.test(r));
  check('没有意外的 4xx/5xx（唯一预期的是坏文件的 422）', unexpected.length === 0, JSON.stringify(badResponses));
  exitCode = results.some((r) => r.startsWith('FAIL')) ? 1 : 0;
} catch (e) {
  console.log('!! 走查中断：' + e.stack);
  results.push('FAIL 走查中断 ' + e.message);
} finally {
  writeFileSync(join(HERE, '../walkthrough_result.txt'), results.join('\n') + '\n');
  await cleanup();
  const failed = results.filter((r) => r.startsWith('FAIL')).length;
  console.log(`\n${results.length - failed}/${results.length} 项通过`);
  process.exit(exitCode);
}
