// M2 浏览器走查（手动运行，不属于 pytest）。
// 前提：studio 已用假卡启动在 127.0.0.1:8798，token=tokm2；卡、图库、导出目录都是临时目录（/tmp/gxrm2/...），
//   假卡由 gxr_studio.devtools.synthetic_card 生成，不接触真实卡，没有相机数据（GXRCE.DAT）。
// 用 macOS 的 Google Chrome（无头），经 DevTools 协议发送真实的点击和按键；滑块的数值用 input/change 事件设置。
// 运行：node browser_walkthrough_m2.mjs   （截图写到 ./screenshots/）
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SHOTS = join(HERE, 'screenshots');
mkdirSync(SHOTS, { recursive: true });

const PORT = 9334;
const BASE = 'http://127.0.0.1:8798';
const TOKEN = 'tokm2';
// GXR_CAMDATA=1：服务器的应用数据目录里已经有相机数据和标定包（临时目录，由测试夹具生成），走"能预览"的路径
const READY = process.env.GXR_CAMDATA === '1';
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const results = [];
const errors = [];
const check = (name, ok, extra = '') => {
  const line = `${ok ? 'PASS' : 'FAIL'} ${name}${extra ? '  ' + extra : ''}`;
  results.push(line);
  console.log(line);
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', `--remote-debugging-port=${PORT}`,
  '--user-data-dir=/tmp/gxrm2/e2e/profile', '--window-size=1400,900', 'about:blank',
], { stdio: 'ignore' });

let targets;
for (let i = 0; i < 50; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
    if (targets.some((t) => t.type === 'page')) break;
  } catch {}
  await sleep(200);
}
const page = targets.find((t) => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));
let id = 0;
const pending = new Map();
ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  }
  if (msg.method === 'Runtime.exceptionThrown') {
    const d = msg.params.exceptionDetails;
    const line = 'exception: ' + (d.exception?.description || d.text) + ' @' + d.lineNumber;
    errors.push(line);
    console.log('  [browser] ' + line);
  }
  if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
    errors.push('console: ' + JSON.stringify(msg.params.args.map((a) => a.value || a.description)));
  }
});
const send = (method, params = {}) => new Promise((resolve) => {
  const i = ++id;
  pending.set(i, resolve);
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
    try {
      if (await evaluate(expr)) return true;
    } catch {}
    await sleep(150);
  }
  return false;
};
// 真实鼠标点击：先取元素中心，再发 mousePressed / mouseReleased
// 默认只在右侧面板（.viewer）里找，避免点到顶栏同名的「配方」「导出」
const clickButton = async (text, root = '.viewer') => {
  const box = await evaluate(`(() => {
    const el = [...document.querySelectorAll(${JSON.stringify(root + ' button, ' + root + ' a, ' + root + ' [role=tab]')})].find(b => b.textContent.trim().startsWith(${JSON.stringify(text)}));
    if (!el) return null;
    el.scrollIntoView({ block: 'center' });
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  })()`);
  if (!box) return false;
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: box.x, y: box.y });
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: box.x, y: box.y, button: 'left', clickCount: 1 });
  await sleep(250);
  return true;
};
const pressKey = async (key, code, keyCode, { down = true, up = true } = {}) => {
  if (down) await send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: keyCode, text: key === ' ' ? ' ' : undefined });
  if (up) await send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: keyCode });
  await sleep(200);
};
const text = (sel) => evaluate(`(document.querySelector(${JSON.stringify(sel)})||{}).textContent || ''`);
const shot = async (name) => {
  const r = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(join(SHOTS, name), Buffer.from(r.result.data, 'base64'));
};

// 走查只用接口读数据做对照；界面上的一切都是页面自己发出的请求
const api = (path, opts = {}) => fetch(BASE + path, { ...opts, headers: { 'X-GXR-Token': TOKEN, 'Content-Type': 'application/json', ...(opts.headers || {}) } });

await send('Page.enable');
await send('Runtime.enable');
await send('Log.enable');

// ---- 1. 进入界面、导入假卡（接口导入，界面导入在 M1 走查里已覆盖） ----------
await send('Page.navigate', { url: `${BASE}/?token=${TOKEN}` });
check('页面加载，顶栏有「照片」', await waitFor(`!!document.querySelector('#tabs a[data-tab=photos]')`));
const cards = await (await api('/api/cards')).json();
const job = await (await api('/api/import', { method: 'POST', body: JSON.stringify({ card_id: cards[0].id }) })).json();
for (let i = 0; i < 300; i++) {
  const j = await (await api(`/api/jobs/${job.id}`)).json();
  if (!j.running) break;
  await sleep(100);
}
const photos = await (await api('/api/photos?limit=5000')).json();
// 优先用真实样本（R805xxxx，DNG 可以解码）；假卡的占位 DNG 解不出来，预览会如实说"RAW 读不出来"
const pairs = photos.filter((p) => p.has_raw && p.has_jpg);
const pair = pairs.find((p) => /^R805/.test(p.name)) || pairs[0];
check('假卡上有一对 DNG+JPG', !!pair, pair ? pair.name : '');
// 从干净的编辑开始（上一次走查留下的配方和曲线会影响"起始两个点"等检查）
await api(`/api/photos/${pair.id}/edit`, { method: 'DELETE' });

// ---- 2. 打开大图，切到「配方」 ---------------------------------------------
await evaluate(`location.hash = '#/photo/${pair.id}'`);
check('大图打开', await waitFor(`!!document.querySelector('.viewer')`));
await waitFor(`!!document.querySelector('.side-tabs')`);
await clickButton('配方', '.side-tabs');
check('配方标签：8 个底子', await waitFor(`document.querySelectorAll('.base-grid button').length === 8`, 8000));
if (!READY) {
  check('没有相机数据：显示「从卡导入」引导', await waitFor(`[...document.querySelectorAll('.camdata-guide button')].some(b => b.textContent.includes('从卡导入'))`, 8000));
} else {
  check('有相机数据：不再显示引导', await waitFor(`!document.querySelector('.camdata-guide')`, 8000));
  check('有相机数据：预览是图片（blob），不是照片本身', await waitFor(`(document.querySelector('.stage img.photo')||{}).src?.startsWith('blob:')`, 15000));
}
check('滑块：对比、高光、阴影、饱和度等（每个底子不同）', await waitFor(`document.querySelectorAll('.knob-row input[type=range]').length >= 5`, 5000));
const noteAfterOpen = await text('.stage-note');
check('预览说明里有「电脑预测」', noteAfterOpen.includes('电脑预测'), noteAfterOpen.slice(0, 60));
if (!READY) {
  check('没有相机数据：预览说明写出原因（GXRCE.DAT）', await waitFor(`(document.querySelector('.stage-note')||{}).textContent.includes('GXRCE.DAT')`, 8000));
} else {
  check('有相机数据：预览标签是「电脑预测」，并标明未标定原因（ISO 或单元）', await waitFor(`(document.querySelector('.stage-note')||{}).textContent.includes('电脑预测')`, 8000), noteAfterOpen.slice(0, 80));
  check('有相机数据：旋钮标签区分「相机 ±5」与「仅电脑」（旧版相机）', await waitFor(`[...document.querySelectorAll('.knob-tag')].some(t => t.textContent === '相机 ±5') && [...document.querySelectorAll('.knob-tag')].some(t => t.textContent === '仅电脑')`, 4000));
}
await shot(READY ? '05-recipes-camdata.png' : '01-recipes-no-camdata.png');

// ---- 3. 拖动一根滑块（设数值 + input/change）：界面应发预览请求，并保存 --------
await evaluate(`(() => {
  const s = [...document.querySelectorAll('.knob-row input[type=range]')].find(i => i.getAttribute('aria-label') === '对比');
  s.value = Number(s.max) - 3;
  s.dispatchEvent(new Event('input', { bubbles: true }));
  s.dispatchEvent(new Event('change', { bubbles: true }));
})()`);
await sleep(900);
const saved = await (await api(`/api/photos/${pair.id}/edit`)).json();
check('改对比后保存到 sidecar（配方里有 contrast）', saved.recipe && saved.recipe.levels && saved.recipe.levels.contrast !== undefined, JSON.stringify(saved.recipe && saved.recipe.levels));
if (!READY) {
  check('保存后仍提示没有相机数据', await waitFor(`(document.querySelector('.stage-note')||{}).textContent.includes('GXRCE.DAT')`, 4000));
} else {
  check('改对比后预览重新渲染（blob 地址变了）', await waitFor(`(document.querySelector('.stage img.photo')||{}).src?.startsWith('blob:')`, 8000));
}

// ---- 4. 换底子：05 富士 CC，并且记住 04 上的设置 ------------------------------
await clickButton('05 富士 CC');
const after = await (await api(`/api/photos/${pair.id}/edit`)).json();
check('换到 05 底子并保存', after.recipe && after.recipe.slot === 5, `slot=${after.recipe && after.recipe.slot}`);
check('05 底子的 memory 里记住了原来的设置', after.memory && Object.keys(after.memory).length > 0, JSON.stringify(after.memory));

// ---- 5. 按住 Space 看照片本身，松开恢复 -------------------------------------
await pressKey(' ', 'Space', 32, { up: false });
check('按住 Space：说明切换为看照片本身', await waitFor(`(document.querySelector('.stage-note')||{}).textContent.includes('正在看照片本身')`, 3000));
await pressKey(' ', 'Space', 32, { down: false });
check('松开 Space：恢复预览说明', await waitFor(`!(document.querySelector('.stage-note')||{}).textContent.includes('正在看照片本身')`, 3000));

// ---- 6. 全部归零：两步确认 --------------------------------------------------
await clickButton('全部归零');
check('全部归零：第一次点变成「再点一次」', await waitFor(`[...document.querySelectorAll('button')].some(b => b.textContent === '再点一次：全部归零')`, 2000));
await shot('02-recipes-reset-armed.png');

// ---- 7. 调整（仅电脑）：标签、曲线加点 -------------------------------------
await clickButton('调整', '.side-tabs');
check('调整标签：每一行都标「仅电脑」', await waitFor(`document.querySelectorAll('.knob-tag').length >= 6 && [...document.querySelectorAll('.knob-tag')].every(t => t.textContent === '仅电脑')`, 4000));
check('曲线：起始两个点', await waitFor(`document.querySelectorAll('.curve .curve-point').length === 2`, 4000));
await evaluate(`(() => {
  const svg = document.querySelector('.curve');
  const r = svg.getBoundingClientRect();
  window.__curveBox = { x: r.left, y: r.top, w: r.width, h: r.height };
})()`);
const cb = await evaluate('window.__curveBox');
const px = cb.x + cb.w * 0.5;
const py = cb.y + cb.h * 0.5;
await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: px, y: py, button: 'left', clickCount: 1 });
await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: px, y: py - 20, button: 'left' });
await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: px, y: py - 20, button: 'left', clickCount: 1 });
await sleep(600);
check('曲线：点空白处加了一个点（3 / 16）', await waitFor(`(document.querySelector('.curve-wrap span')||{}).textContent.startsWith('3 / 16')`, 3000));
await shot('03-adjust-curve.png');

// ---- 8. 导出：不再拦截 RAW，写明电脑预测 -----------------------------------
await clickButton('导出', '.side-tabs');
check('导出标签：不再有「暂时不能导出」的拦截', await waitFor(`!document.querySelector('.side-body').textContent.includes('暂时不能导出')`, 3000));
check(READY ? '导出标签：有相机数据时写明「电脑预测的配方效果」' : '导出标签：没有相机数据时写明「电脑预测」或中性预览',
  await waitFor(READY ? `document.querySelector('.side-body').textContent.includes('电脑预测的配方效果')` : `/电脑预测|中性预览/.test(document.querySelector('.side-body').textContent)`, 3000));
check('导出标签：有「精确（更慢）」', await waitFor(`document.querySelector('.side-body').textContent.includes('精确（更慢）')`, 3000));
await shot('04-export.png');

// ---- 9. 错误记录 ----------------------------------------------------------------
check('浏览器没有未捕获的异常或控制台错误', errors.length === 0, errors.slice(0, 3).join(' | '));

console.log('\n' + results.join('\n'));
const failed = results.filter((r) => r.startsWith('FAIL')).length;
console.log(`\nPASS: ${results.length - failed}   FAIL: ${failed}   浏览器错误记录: ${errors.length}`);
ws.close();
chrome.kill();
process.exit(failed ? 1 : 0);
