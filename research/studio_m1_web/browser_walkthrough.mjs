// 浏览器走查（手动运行，不属于 pytest，见 REPORT.md）。
// 前提：studio 已用假卡启动在 127.0.0.1:8799，token=tok2；卡、图库、导出目录都是临时目录
//   （/tmp/gxrw/vol2、/tmp/gxrw/lib2、/tmp/gxrw/exp2，假卡用 synthetic_card 生成，不接触真实卡）。
// 用的是 macOS 的 Google Chrome，经 DevTools 协议发送真实鼠标和键盘事件。运行：node browser_walkthrough.mjs
// 注意：需要一个全新的图库（导入步骤要求有新照片）。
// 临时的浏览器走查（不在仓库里）：真实鼠标和键盘事件，通过 Chrome DevTools 协议驱动。
import { spawn } from 'node:child_process';

const PORT = 9333;
const BASE = 'http://127.0.0.1:8799';
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
  '--user-data-dir=/tmp/gxrw/e2e/profile', '--window-size=1400,900', 'about:blank',
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
  if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') errors.push('console: ' + JSON.stringify(msg.params.args.map((a) => a.value || a.description)));
  if (msg.method === 'Log.entryAdded' && msg.params.entry.level === 'error') errors.push('log: ' + msg.params.entry.text + ' ' + (msg.params.entry.url || ''));
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
const click = async (selectorOrText) => {
  const box = await evaluate(`(() => {
    const s = ${JSON.stringify(selectorOrText)};
    let el = null;
    try { el = document.querySelector(s); } catch (e) {}
    if (!el) el = [...document.querySelectorAll('button,a')].find(b => b.textContent.trim().startsWith(s));
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  })()`);
  if (!box) throw new Error('找不到：' + selectorOrText);
  for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) {
    await send('Input.dispatchMouseEvent', { type, x: box.x, y: box.y, button: 'left', clickCount: 1 });
  }
};
const key = async (k, code, vk) => {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: k, code, windowsVirtualKeyCode: vk, text: k.length === 1 ? k : undefined });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code, windowsVirtualKeyCode: vk });
};

await send('Page.enable');
await send('Runtime.enable');
await send('Log.enable');
await send('Page.navigate', { url: `${BASE}/?token=tok2` });
await sleep(1500);

// 1. 首次打开：引导卡出现，跳过
check('首次打开显示新手引导', await waitFor(`!!document.querySelector('.modal-overlay')`));
await click('跳过');
await sleep(300);

// 2. 插卡自动导入：横幅出现，然后完成
// 导入很快，轮询来不及看到"导入中"，所以只要求横幅出现过（完成或导入中都算）
check('插卡后出现导入横幅', await waitFor(`document.querySelector('#banner').textContent.trim().length > 0`, 8000));
check('导入完成横幅', await waitFor(`/导入完成/.test(document.querySelector('#banner').textContent)`, 20000),
  await evaluate(`document.querySelector('#banner').textContent.trim()`));
check('状态栏提示可以安全弹出', await evaluate(`/可以安全弹出/.test(document.querySelector('#card-status').textContent)`));
await click('知道了');
await sleep(200);

// 3. 图库：角标与数量
const thumbs = await evaluate(`document.querySelectorAll('.thumb').length`);
check('图库显示缩略图', thumbs === 15, `数量 ${thumbs}`);
const tags = await evaluate(`[...document.querySelectorAll('.thumb .tag')].map(t => t.textContent)`);
check('角标三种都有', ['DNG+JPG', '只有 JPG', '只有 DNG'].every((t) => tags.includes(t)), JSON.stringify([...new Set(tags)]));
check('日期列表存在', (await evaluate(`document.querySelectorAll('#dates button').length`)) >= 5);

// 4. 日期筛选
await click('2026-10-16');
await sleep(400);
check('按日期筛选', (await evaluate(`document.querySelectorAll('.thumb').length`)) === 2);
await click('全部');
await sleep(400);

// 5. 多选 + 导出选中（弹窗）
await evaluate(`document.querySelectorAll('.thumb .check')[0].click(), document.querySelectorAll('.thumb .check')[1].click()`);
await sleep(200);
check('多选显示已选 2 张', await evaluate(`/已选 2 张/.test(document.querySelector('#selbar').textContent)`));
await click('导出选中的');
const opened = await waitFor(`!!document.querySelector('.modal')`, 3000);
check('导出弹窗打开', opened, opened ? '' : JSON.stringify(await evaluate(`({ root: document.querySelector('#modal-root').innerHTML.length, selbar: document.querySelector('#selbar').textContent, btns: [...document.querySelectorAll('#selbar button')].map(b => b.textContent) })`)));
await click('开始导出');
check('批量导出完成', await waitFor(`/导出完成/.test(document.querySelector('.modal .result')?.textContent || '')`, 20000),
  await evaluate(`document.querySelector('.modal .result')?.textContent || 'none'`));
await key('Escape', 'Escape', 27);
await sleep(200);

// 6. 大图：点第一张（DNG+JPG），左右键切换
await evaluate(`document.querySelector('.thumb').click()`);
check('进入大图', await waitFor(`!!document.querySelector('.stage img.photo')`));
await waitFor(`document.querySelector('.stage img.photo').complete && document.querySelector('.stage img.photo').naturalWidth > 0`, 5000);
const before = await evaluate(`location.hash`);
await key('ArrowRight', 'ArrowRight', 39);
await sleep(500);
check('右键切到下一张', (await evaluate(`location.hash`)) !== before, await evaluate(`location.hash`));
await key('ArrowLeft', 'ArrowLeft', 37);
await sleep(500);
check('左键切回上一张', (await evaluate(`location.hash`)) === before);

// 7. 裁切：比例 3:2 → 框出现在画面上，并保存到服务器
await click('3:2');
await sleep(600);
check('选 3:2 后框显示', await evaluate(`document.querySelector('.crop-box').style.width !== ''`));
const cropId = (await evaluate(`location.hash`)).split('/').pop();
const crop1 = await (await fetch(`${BASE}/api/photos/${cropId}/crop`, { headers: { 'X-GXR-Token': 'tok2' } })).json();
check('3:2 已写进 sidecar', crop1.active === true && crop1.preset === '3:2', JSON.stringify(crop1.pixels));

// 7b. 拖动框（真实鼠标）：先读框中心，拖 40px 向下，松手后服务器上的 y 要变
const boxRect = await evaluate(`(() => { const r = document.querySelector('.crop-box').getBoundingClientRect(); return { x: r.x + r.width/2, y: r.y + r.height/2 }; })()`);
const y0 = crop1.rect[1];
await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: boxRect.x, y: boxRect.y, button: 'left', clickCount: 1 });
for (let s = 1; s <= 8; s++) await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: boxRect.x, y: boxRect.y + s * 5, button: 'left' });
await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: boxRect.x, y: boxRect.y + 40, button: 'left', clickCount: 1 });
await sleep(800);
const crop2 = await (await fetch(`${BASE}/api/photos/${cropId}/crop`, { headers: { 'X-GXR-Token': 'tok2' } })).json();
check('拖动框后位置保存', crop2.rect[1] > y0 + 0.01, `y ${y0.toFixed(3)} → ${crop2.rect[1].toFixed(3)}`);

// 7c. 拉直：键盘 ↑ 两次（0.5° 一档）
await key('ArrowUp', 'ArrowUp', 38);
await key('ArrowUp', 'ArrowUp', 38);
await sleep(700);
const crop3 = await (await fetch(`${BASE}/api/photos/${cropId}/crop`, { headers: { 'X-GXR-Token': 'tok2' } })).json();
check('↑ 键拉直保存', Math.abs(crop3.angle_deg - 1.0) < 0.01, `angle ${crop3.angle_deg}`);

// 7d. 空格按住看原图：框隐藏，松开恢复
await send('Input.dispatchKeyEvent', { type: 'keyDown', key: ' ', code: 'Space', windowsVirtualKeyCode: 32, text: ' ' });
await sleep(150);
check('按住 Space 隐藏裁切框', await evaluate(`document.querySelector('.crop-box').style.display === 'none'`));
await send('Input.dispatchKeyEvent', { type: 'keyUp', key: ' ', code: 'Space', windowsVirtualKeyCode: 32 });
await sleep(150);
check('松开 Space 恢复裁切框', await evaluate(`document.querySelector('.crop-box').style.display !== 'none'`));

// 7e. 还原原图
await click('还原原图');
await sleep(700);
const crop4 = await (await fetch(`${BASE}/api/photos/${cropId}/crop`, { headers: { 'X-GXR-Token': 'tok2' } })).json();
check('还原原图后没有裁切', crop4.active === false);

// 8. 导出标签（E 键）+ 单张导出
await key('e', 'KeyE', 69);
await sleep(300);
check('E 键切到导出标签', await evaluate(`document.querySelector('[data-tab=export]')?.getAttribute('aria-selected') === 'true'`));
await click('开始导出');
check('单张导出完成', await waitFor(`/导出完成/.test(document.querySelector('.side .result')?.textContent || '')`, 15000),
  await evaluate(`document.querySelector('.side .result')?.textContent || 'none'`));

// 9. 只有 RAW 的照片：说明原因，按钮禁用
await key('Escape', 'Escape', 27);
await sleep(400);
const rawHash = await evaluate(`(() => { const t = [...document.querySelectorAll('.thumb')].find(t => t.querySelector('.tag').textContent === '只有 DNG'); t.click(); return true; })()`);
await waitFor(`!!document.querySelector('.stage img.photo')`);
await key('e', 'KeyE', 69);
await sleep(300);
check('只有 RAW 的说明原因并禁用导出', await evaluate(`/暂时不能导出/.test(document.querySelector('.side')?.textContent || '') && document.querySelector('.side .btn.primary')?.disabled === true`));

// 10. 设置、帮助
await key('Escape', 'Escape', 27);
await sleep(200);
await key('?', 'Slash', 191);
check('? 打开快捷键表', await waitFor(`/快捷键与帮助/.test(document.querySelector('.modal')?.textContent || '')`));
await key('Escape', 'Escape', 27);

console.log(results.join('\n'));
console.log(`错误记录 ${errors.length} 条`);
for (const e of errors.slice(0, 20)) console.log('  ' + e);
ws.close();
chrome.kill();
process.exit(0);
