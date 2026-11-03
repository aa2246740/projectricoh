// 裁切：社交媒体比例 + 构图辅助线 的浏览器走查（手动运行，不属于 pytest，见 REPORT.md）。
// 由 run_walkthrough.sh 启动：工作室跑在临时目录里（假卡、图库、导出都在 _tmp 下），不碰真实的卡和图库。
// 用的是 macOS 的 Google Chrome（无头），经 DevTools 协议发真实的鼠标和键盘事件。
import { spawn } from 'node:child_process';
import { writeFileSync } from 'node:fs';

const BASE = process.env.WT_BASE;
const TOKEN = process.env.WT_TOKEN;
const CDP_PORT = Number(process.env.WT_CDP_PORT);
const PROFILE = process.env.WT_PROFILE;
const SHOTS = process.env.WT_SHOTS;
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
const errors = [];
const check = (name, ok, extra = '') => {
  const line = `${ok ? 'PASS' : 'FAIL'} ${name}${extra ? '  ' + extra : ''}`;
  results.push(line);
  console.log(line);
};

// 和 crop.js 的 PRESET_GROUPS 一致：[按钮文字, 比例 id, 默认方向(landscape/portrait/undefined)]
const GROUPS = {
  常用: [
    ['原比例', 'original'],
    ['自由', 'free'],
    ['1:1', '1:1'],
    ['3:2', '3:2'],
    ['4:3', '4:3'],
    ['16:9', '16:9'],
    ['XPan 65:24', 'xpan-65-24'],
  ],
  社交媒体与屏幕: [
    ['小红书 3:4', '4:3', 'portrait'],
    ['Instagram 4:5', '4:5', 'portrait'],
    ['Instagram 1:1', '1:1'],
    ['Instagram 横图 1.91:1', '1.91:1', 'landscape'],
    ['公众号封面 2.35:1', '2.35:1', 'landscape'],
    ['微博 16:9', '16:9', 'landscape'],
    ['抖音 / 视频号 9:16', '16:9', 'portrait'],
    ['电脑壁纸 16:10', '16:10', 'landscape'],
  ],
};
const RATIO = { '3:2': 1.5, '4:3': 4 / 3, '1:1': 1, '4:5': 1.25, '16:9': 16 / 9, '16:10': 1.6, '1.91:1': 1.91, '2.35:1': 2.35, 'xpan-65-24': 65 / 24 };
const GUIDE_LABELS = ['三分线', '黄金比例', '黄金螺旋', '对角线', '中心十字', '网格 4×4', '关'];

// ---- 启动 Chrome -----------------------------------------------------------------
const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', `--remote-debugging-port=${CDP_PORT}`,
  `--user-data-dir=${PROFILE}`, '--window-size=1400,900', 'about:blank',
], { stdio: 'ignore' });

let targets;
for (let i = 0; i < 80; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json`)).json();
    if (targets.some((t) => t.type === 'page')) break;
  } catch {}
  await sleep(200);
}
const page = targets.find((t) => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));
let msgId = 0;
const pending = new Map();
ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  }
  if (msg.method === 'Runtime.exceptionThrown') {
    const d = msg.params.exceptionDetails;
    errors.push('exception: ' + (d.exception?.description || d.text));
  }
  if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
    errors.push('console.error: ' + JSON.stringify(msg.params.args.map((a) => a.value || a.description)));
  }
  if (msg.method === 'Log.entryAdded' && msg.params.entry.level === 'error') {
    errors.push('log: ' + msg.params.entry.text + ' ' + (msg.params.entry.url || ''));
  }
});
const send = (method, params = {}) =>
  new Promise((resolve) => {
    const i = ++msgId;
    pending.set(i, resolve);
    ws.send(JSON.stringify({ id: i, method, params }));
  });
const evaluate = async (expr) => {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result.exceptionDetails) throw new Error('eval: ' + JSON.stringify(r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text));
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
const mouse = async (x, y, down = true) => {
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'none' });
  if (down) await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
  if (down) await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
};
// 在某个区域里按文字点按钮（先滚到可见，再发真实鼠标事件）
const clickIn = async (scopeSel, text, tag = 'button') => {
  const pos = await evaluate(`(() => {
    const scope = document.querySelector(${JSON.stringify(scopeSel)});
    const el = scope && [...scope.querySelectorAll(${JSON.stringify(tag)})].find((b) => b.textContent.trim() === ${JSON.stringify(text)});
    if (!el) return null;
    el.scrollIntoView({ block: 'center' });
    const r = el.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  })()`);
  if (!pos) throw new Error('找不到按钮：' + text);
  await mouse(pos.x, pos.y);
  await sleep(450);
};
// 每次点完面板都看一眼：面板文字里不能混进 "null"（以前有过）
const nullHits = [];
const clickPanel = async (text, tag = 'button') => {
  await clickIn('.crop-panel', text, tag);
  if (/null/.test(await evaluate(`document.querySelector('.crop-panel').textContent`))) nullHits.push(text);
};
const clickCheckbox = async () => {
  const pos = await evaluate(`(() => {
    const el = document.querySelector('.crop-panel input[type=checkbox]');
    el.scrollIntoView({ block: 'center' });
    const r = el.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  })()`);
  await mouse(pos.x, pos.y);
  await sleep(300);
};
const key = async (k, code, vk) => {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: k, code, windowsVirtualKeyCode: vk, text: k });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code, windowsVirtualKeyCode: vk });
  await sleep(350);
};
const screenshot = async (name) => {
  const r = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(`${SHOTS}/${name}`, Buffer.from(r.result.data, 'base64'));
  console.log(`  [截图] ${name}`);
};
const pressedInPanel = () => evaluate(`[...document.querySelectorAll('.crop-panel button[aria-pressed=true]')].map((b) => b.textContent.trim())`);
const svgInfo = () =>
  evaluate(`(() => {
    const s = document.querySelector('.crop-box svg.guides');
    if (!s) return null;
    const paths = [...s.querySelectorAll('path')];
    return {
      display: s.style.display || '',
      lines: s.querySelectorAll('line').length,
      paths: paths.length,
      d: paths[0] ? paths[0].getAttribute('d') : '',
      viewBox: s.getAttribute('viewBox'),
      opacity: getComputedStyle(s).opacity,
    };
  })()`);
const cropOf = (id) => evaluate(`(async () => (await fetch('/api/photos/${id}/crop')).json())()`);
// 保存后的框：比例和横竖是否对得上
function shapeOf(c) {
  const [, , rw, rh] = c.rect;
  const w = rw * c.frame.width;
  const h = rh * c.frame.height;
  return { w: Math.round(w), h: Math.round(h), landscape: w >= h, ratio: Math.max(w, h) / Math.min(w, h) };
}

// ---- 走查 -----------------------------------------------------------------------
await send('Page.enable');
await send('Runtime.enable');
await send('Log.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1400, height: 900, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url: `${BASE}/?token=${TOKEN}` });
await sleep(1500);

// 0. 首次打开：引导卡可能出现，跳过
if (await waitFor(`!!document.querySelector('.modal-overlay')`, 3000)) {
  await clickIn('.modal-overlay', '跳过');
}
// 导入（和插卡后自动导入是同一个接口）
const jobId = await evaluate(`(async () => {
  const cards = await (await fetch('/api/cards')).json();
  const job = await (await fetch('/api/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ card_id: cards[0].id }) })).json();
  return job.id;
})()`);
check('导入假卡完成', await waitFor(`(async () => !(await (await fetch('/api/jobs/${jobId}')).json()).running)()`, 60000));
const photos = await evaluate(`(async () => (await (await fetch('/api/photos?limit=5000')).json()))()`);
const pair = photos.find((p) => p.has_raw && p.has_jpg);
check('有一张 DNG+JPG 照片可以走查', !!pair);
const photoId = pair.id;
const sixteenNine = photos.find((p) => Math.abs(p.width / p.height - 16 / 9) < 0.03);

// 1. 打开大图，默认：没有裁切、三分线、没有 XPan 推荐
await evaluate(`location.hash = '#/photo/${photoId}'`);
check('大图裁切面板打开', await waitFor(`!!document.querySelector('.crop-panel')`));
await sleep(500);
const pressed0 = await pressedInPanel();
check('默认辅助线是三分线', pressed0.includes('三分线'), JSON.stringify(pressed0));
check('默认没有自动推荐 XPan', !(await evaluate(`!!document.querySelector('.crop-panel .suggest') || /要裁成 XPan/.test(document.body.textContent)`)));
check('默认三分线：四条线', (await svgInfo())?.lines === 4, JSON.stringify(await svgInfo()));
if (sixteenNine) {
  await evaluate(`location.hash = '#/photo/${sixteenNine.id}'`);
  await waitFor(`!!document.querySelector('.crop-panel')`);
  await sleep(500);
  check('16:9 照片不弹 XPan 建议', !(await evaluate(`!!document.querySelector('.crop-panel .suggest') || !!document.querySelector('.hint-xpan-suggest') || /要裁成 XPan/.test(document.body.textContent)`)));
  await evaluate(`location.hash = '#/photo/${photoId}'`);
  await waitFor(`!!document.querySelector('.crop-panel')`);
  await sleep(500);
} else {
  console.log('  [注意] 假卡里没有 16:9 照片，XPan 建议这一项由静态测试覆盖');
}

// 2. 每个分组、每个比例都点一遍：保存下来的框要符合所选比例，横竖也要对
for (const [group, items] of Object.entries(GROUPS)) {
  for (const [text, id, orient] of items) {
    await clickPanel(text);
    const c = await cropOf(photoId);
    const s = shapeOf(c);
    const want = orient ? orient === 'landscape' : s.landscape; // 没写方向的跟着照片
    let ok = c.preset === id;
    if (!['original', 'free'].includes(id)) {
      ok = ok && Math.abs(s.ratio - RATIO[id]) / RATIO[id] < 0.02;
      if (id !== '1:1') ok = ok && s.landscape === want;
    }
    check(`[${group}] ${text} 保存为 ${id}${orient ? '，默认' + (orient === 'portrait' ? '竖' : '横') : ''}`, ok, `框 ${s.w}×${s.h} 比例 ${s.ratio.toFixed(3)}`);
  }
}

// 3. 小红书 3:4 竖图：按钮状态、导出尺寸
await clickPanel('小红书 3:4');
const pressedXhs = await pressedInPanel();
check('小红书 3:4 按下后只亮它（竖）', pressedXhs.includes('小红书 3:4') && !pressedXhs.includes('4:3'), JSON.stringify(pressedXhs));
const exp = await evaluate(`(async () => (await (await fetch('/api/photos/${photoId}/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ long_edge: 1200, quality: 90 }) })).json()))()`);
check('导出的小红书 3:4 是竖图、比例约 0.75', exp.height > exp.width && Math.abs(exp.width / exp.height - 0.75) < 0.02, `${exp.width}×${exp.height}`);

// 4. 横竖切换：3:2 横 → 竖 → 横
await clickPanel('3:2');
await clickPanel('竖');
let s1 = shapeOf(await cropOf(photoId));
check('3:2 切到竖', !s1.landscape && Math.abs(s1.ratio - 1.5) / 1.5 < 0.02, `${s1.w}×${s1.h}`);
await clickPanel('横');
let s2 = shapeOf(await cropOf(photoId));
check('3:2 切回横', s2.landscape && Math.abs(s2.ratio - 1.5) / 1.5 < 0.02, `${s2.w}×${s2.h}`);

// 5. 每一种辅助线都画出来（G 键换线 + 面板按钮都试）
await clickPanel('三分线');
let info = await svgInfo();
check('三分线：4 条线', info.lines === 4 && info.paths === 0, JSON.stringify(info));
await clickPanel('黄金比例');
info = await svgInfo();
check('黄金比例：4 条线', info.lines === 4 && info.paths === 0, JSON.stringify(info));
await clickPanel('对角线');
info = await svgInfo();
check('对角线：2 条线', info.lines === 2 && info.paths === 0, JSON.stringify(info));
await clickPanel('中心十字');
info = await svgInfo();
check('中心十字：2 条线', info.lines === 2 && info.paths === 0, JSON.stringify(info));
await clickPanel('网格 4×4');
info = await svgInfo();
check('网格 4×4：6 条线', info.lines === 6 && info.paths === 0, JSON.stringify(info));
await clickPanel('黄金螺旋');
info = await svgInfo();
check('黄金螺旋：一条路径、没有直线', info.paths === 1 && info.lines === 0 && info.d.length > 500, `路径长 ${info.d.length}`);
// 螺旋四个方向：O 键循环，中心点各不相同
const spiralStarts = [];
const spiralLabel = () => evaluate(`[...document.querySelectorAll('.crop-panel button')].map((b) => b.textContent.trim()).find((t) => t.startsWith('螺旋方向')) || ''`);
spiralStarts.push({ label: await spiralLabel(), start: ((await svgInfo()).d.match(/^M[^L]*/) || [''])[0] });
for (let i = 0; i < 3; i++) {
  await key('o', 'KeyO', 79);
  spiralStarts.push({ label: await spiralLabel(), start: ((await svgInfo()).d.match(/^M[^L]*/) || [''])[0] });
}
const distinct = new Set(spiralStarts.map((s) => s.start)).size;
check('螺旋 O 键：四个方向各不相同', distinct === 4, JSON.stringify(spiralStarts.map((s) => s.label)));
await key('o', 'KeyO', 79);
check('螺旋 O 键第 5 次回到 1/4', (await spiralLabel()).startsWith('螺旋方向 1/4'), await spiralLabel());
await clickPanel('网格 4×4');
await clickPanel('黄金螺旋'); // 回到螺旋，留着给截图

// 6. G 键循环辅助线（包括"关"）
await clickPanel('三分线');
await key('g', 'KeyG', 71);
let pressedG = await pressedInPanel();
check('G 键：三分线 → 黄金比例', pressedG.includes('黄金比例'), JSON.stringify(pressedG));
for (let i = 0; i < 6; i++) await key('g', 'KeyG', 71); // 黄金比例 → 螺旋 → 对角 → 十字 → 网格 → 关 → 三分线
pressedG = await pressedInPanel();
check('G 键循环一圈回到三分线', pressedG.includes('三分线'), JSON.stringify(pressedG));
await clickPanel('关');
info = await svgInfo();
check('关闭辅助线：整层隐藏', info.display === 'none', JSON.stringify(info));
await clickPanel('三分线');

// 7. 拖动：拖的时候完整显示，松手后变淡（默认设置）
await clickPanel('3:2');
const boxRect = await evaluate(`(() => { const r = document.querySelector('.crop-box').getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; })()`);
await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: boxRect.x, y: boxRect.y, button: 'none' });
await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: boxRect.x, y: boxRect.y, button: 'left', clickCount: 1 });
await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: boxRect.x + 25, y: boxRect.y + 10, button: 'left' });
await sleep(450); // 变淡有 0.25 秒的过渡，等它过去再读
const during = await evaluate(`({ moving: document.querySelector('.crop-box').dataset.moving, opacity: getComputedStyle(document.querySelector('.crop-box svg.guides')).opacity })`);
check('拖动中：辅助线完整显示', during.moving === 'true' && during.opacity === '1', JSON.stringify(during));
await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: boxRect.x + 25, y: boxRect.y + 10, button: 'left', clickCount: 1 });
await sleep(500);
const after = await evaluate(`({ moving: document.querySelector('.crop-box').dataset.moving, fade: document.querySelector('.crop-box').dataset.fade, opacity: getComputedStyle(document.querySelector('.crop-box svg.guides')).opacity })`);
check('松手后辅助线变淡（默认）', after.moving === 'false' && after.fade === 'true' && Number(after.opacity) < 0.5, JSON.stringify(after));
const movedCrop = await cropOf(photoId);
check('拖动松手后位置保存', movedCrop.active === true, JSON.stringify(movedCrop.rect));

// 8. 设置：关掉"松手后变淡"，松手后保持清楚
await clickCheckbox();
await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: boxRect.x, y: boxRect.y, button: 'none' });
await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: boxRect.x, y: boxRect.y, button: 'left', clickCount: 1 });
await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: boxRect.x, y: boxRect.y, button: 'left', clickCount: 1 });
await sleep(500);
const clear = await evaluate(`getComputedStyle(document.querySelector('.crop-box svg.guides')).opacity`);
check('关掉变淡后：松手仍清楚', clear === '1', `opacity=${clear}`);
await clickCheckbox(); // 改回默认

// 9. 截图：辅助线（黄金螺旋 + 竖的小红书）、社交比例（小红书 3:4 + 三分线）
await clickPanel('小红书 3:4');
await clickPanel('黄金螺旋');
await sleep(300);
await screenshot('01-guides-golden-spiral.png');
await clickPanel('三分线');
await sleep(300);
await screenshot('02-social-xiaohongshu-3x4.png');

// 10. 刷新页面：偏好记住（辅助线和螺旋方向）
await clickPanel('黄金螺旋');
await key('o', 'KeyO', 79); // 螺旋 → 2/4
const want = await spiralLabel();
await send('Page.reload', { ignoreCache: true });
await waitFor(`!!document.querySelector('.crop-panel')`, 15000);
await sleep(800);
const afterReload = await spiralLabel();
check('刷新后记住黄金螺旋和方向', (await pressedInPanel()).includes('黄金螺旋') && afterReload === want, `${afterReload} / 之前 ${want}`);
// 恢复成默认，不把本次设置留在这台浏览器里
await evaluate(`localStorage.removeItem('gxr-studio.crop-guides')`);

check('每次点完面板，文字里都没有多余的 "null"', nullHits.length === 0, nullHits.join(' '));
check('全程没有页面错误', errors.length === 0, errors.slice(0, 5).join(' | '));

// ---- 收尾 ------------------------------------------------------------------------
const passed = results.filter((r) => r.startsWith('PASS')).length;
console.log(`\n合计 ${results.length} 项，通过 ${passed}，失败 ${results.length - passed}`);
writeFileSync(`${SHOTS}/../walkthrough-results.txt`, results.join('\n') + `\n\n页面错误：${errors.length}\n${errors.join('\n')}\n`);
try {
  await send('Browser.close');
} catch {}
await sleep(800);
if (!chrome.killed && chrome.exitCode === null) chrome.kill('SIGTERM');
process.exit(results.every((r) => r.startsWith('PASS')) ? 0 : 1);
