// 端到端走查（手动运行，不属于 pytest）：全新的临时 HOME 和图库里，从首次打开一路走到导出。
//
//   运行：node research/studio_integration/browser_walkthrough_integration.mjs   （截图写到 ./screenshots/）
//
// 脚本自己做的事：
//   1. 建一个临时目录（里面有：HOME、应用数据、图库、导出目录、卷根目录、Chrome 配置、上传用的 DAT 副本）；
//   2. 用 gxr_studio.devtools.synthetic_card 造假卡（先放在 stage/ 里），再把本机固件包里的 GXRCE.DAT 现场复制进去，
//      "插卡"时整个挪进卷根目录——应用发现卡之后卡就被登记为只读，所以 DAT 必须在这之前放好；
//   3. 启动 gxr-studio（只扫描临时卷根目录，不会碰 /Volumes 下任何真实的卡）和无头 Chrome，经 DevTools 协议发真实鼠标/键盘事件；
//   4. 走完流程，最后（无论成功失败）杀掉两个进程并删除整个临时目录——里面有从固件包复制的相机数据，不能留。
// 同一时间只有 3 个进程：本脚本（node）、gxr-studio、Chrome。
import { spawn, execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '../..');
const STUDIO = join(REPO, 'studio');
const SHOTS = join(HERE, 'screenshots');
mkdirSync(SHOTS, { recursive: true });

const DAT_135 = join(REPO, 'firmware/package_v37_g135/local/SD_ROOT/GXRCE.DAT');
const DAT_127 = join(REPO, 'firmware/package_v36_g127/local/SD_ROOT/GXRCE.DAT');
const SHA_135 = '57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a';
const SHA_127 = '9100616f24dae04eb43138805336b3eebc3eebcc5b86f14b3e0b30969474ead6';

const SERVER_PORT = 8797;
const CHROME_PORT = 9335;
const BASE = `http://127.0.0.1:${SERVER_PORT}`;
const TOKEN = 'tokint';
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

// ---- 临时目录（结束时一定删除）----------------------------------------------------
const TMP = mkdtempSync(join(tmpdir(), 'gxrint-'));
const P = {
  home: join(TMP, 'home'),
  app: join(TMP, 'home/app-data'),
  lib: join(TMP, 'lib'),
  exp: join(TMP, 'exp'),
  vol: join(TMP, 'vol'),
  stage: join(TMP, 'stage'),
  upload: join(TMP, 'upload'),
  profile: join(TMP, 'chrome-profile'),
};
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
  await Promise.all([waitExit(chrome, 5000), waitExit(server, 5000)]);
  for (const c of [chrome, server]) if (c && c.exitCode === null) c.kill('SIGKILL');
  await Promise.all([waitExit(chrome, 2000), waitExit(server, 2000)]);
  for (let i = 0; i < 5 && existsSync(TMP); i++) {
    try { rmSync(TMP, { recursive: true, force: true }); } catch {}
    if (existsSync(TMP)) await sleep(500);
  }
  console.log(existsSync(TMP) ? `!! 临时目录没删掉：${TMP}` : `临时目录已删除：${TMP}`);
}
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, async () => { await cleanup(); process.exit(130); });

// ---- 工具 -----------------------------------------------------------------------
const api = (path, opts = {}) => fetch(BASE + path, { ...opts, headers: { 'X-GXR-Token': TOKEN, 'Content-Type': 'application/json', ...(opts.headers || {}) } });
const getJson = async (path) => (await api(path)).json();

function treeHash(root) {
  const out = {};
  const walk = (dir) => {
    for (const name of readdirSync(dir).sort()) {
      const p = join(dir, name);
      const st = statSync(p);
      if (st.isDirectory()) walk(p);
      else out[p.slice(root.length)] = `${st.size}:${st.mtimeMs}:${sha(readFileSync(p))}`;
    }
  };
  walk(root);
  return out;
}

// 读 JPEG 的宽高（SOF 段）
function jpegSize(buf) {
  if (buf[0] !== 0xff || buf[1] !== 0xd8) return null;
  let i = 2;
  while (i + 9 < buf.length) {
    if (buf[i] !== 0xff) { i++; continue; }
    const marker = buf[i + 1];
    if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) return { h: buf.readUInt16BE(i + 5), w: buf.readUInt16BE(i + 7) };
    i += 2 + buf.readUInt16BE(i + 2);
  }
  return null;
}

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
    try {
      if (await evaluate(expr)) return true;
    } catch {}
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
// 真实鼠标点击：按文字找按钮/链接/标签页，先滚到可见再点中心。root 默认只在右侧面板里找
const clickButton = async (text, root = '.viewer') => {
  const box = await evaluate(`(() => {
    const el = [...document.querySelectorAll(${JSON.stringify(root + ' button, ' + root + ' a, ' + root + ' [role=tab]')})].find(b => b.textContent.trim().startsWith(${JSON.stringify(text)}) && !b.disabled);
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
const pressKey = async (key, code, keyCode, { down = true, up = true } = {}) => {
  if (down) await send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: keyCode, text: key === ' ' ? ' ' : undefined });
  if (up) await send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: keyCode });
  await sleep(200);
};
const typeInto = async (selector, value) => {
  await evaluate(`document.querySelector(${JSON.stringify(selector)}).focus()`);
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
const setRange = (label, value) => evaluate(`(() => {
  const s = [...document.querySelectorAll('input[type=range]')].find(i => i.getAttribute('aria-label') === ${JSON.stringify(label)});
  if (!s) return false;
  s.value = ${JSON.stringify(String(value))};
  s.dispatchEvent(new Event('input', { bubbles: true }));
  s.dispatchEvent(new Event('change', { bubbles: true }));
  return true;
})()`);
const openSettings = async () => {
  await clickSelector('#btn-settings');
  return waitFor(`!!document.querySelector('.modal [data-section=calibration]')`, 8000);
};
const closeModal = async () => {
  await pressKey('Escape', 'Escape', 27);
  return waitFor(`!document.querySelector('.modal')`, 3000);
};
const thumbSrcOf = (kind) => evaluate(`(() => {
  const t = [...document.querySelectorAll('.thumb')].find(t => t.querySelector('.tag').textContent === ${JSON.stringify(kind)});
  return t ? t.querySelector('img').getAttribute('src') : null;
})()`);

// ---- 主流程 -----------------------------------------------------------------------
let exitCode = 1;
try {
  // 0. 准备：假卡 + 固件包里的 DAT
  phase('0 准备假卡和相机数据（都在临时目录里）');
  const dat135 = existsSync(DAT_135) ? readFileSync(DAT_135) : null;
  const dat127 = existsSync(DAT_127) ? readFileSync(DAT_127) : null;
  if (!check('本机固件包里有 GXRCE.DAT（g135、g127，哈希对得上）', !!dat135 && !!dat127 && sha(dat135) === SHA_135 && sha(dat127) === SHA_127)) throw new Error('缺少固件包里的 DAT，无法走查');
  execFileSync(join(STUDIO, '.venv/bin/python'), ['-m', 'gxr_studio.devtools.synthetic_card', P.stage, '--label', 'FAKECARD'], { cwd: STUDIO, stdio: 'ignore' });
  const stagedCard = join(P.stage, 'FAKECARD');
  copyFileSync(DAT_135, join(stagedCard, 'GXRCE.DAT')); // 现场复制，不进仓库
  copyFileSync(DAT_127, join(P.upload, 'older GXRCE.DAT')); // 之后用"选择文件"上传的另一代
  check('假卡里有 DCIM 和刚复制的 GXRCE.DAT', existsSync(join(stagedCard, 'DCIM')) && sha(readFileSync(join(stagedCard, 'GXRCE.DAT'))) === SHA_135);
  const cardBefore = treeHash(stagedCard);

  server = spawn(join(STUDIO, '.venv/bin/gxr-studio'), ['--no-browser', '--port', String(SERVER_PORT)], {
    cwd: STUDIO,
    stdio: 'ignore',
    env: {
      ...process.env,
      HOME: P.home,
      GXR_STUDIO_HOME: P.app,
      GXR_STUDIO_LIBRARY: P.lib,
      GXR_STUDIO_EXPORT: P.exp,
      GXR_STUDIO_VOLUMES: P.vol,
      GXR_STUDIO_TOKEN: TOKEN,
    },
  });
  let up = false;
  for (let i = 0; i < 80 && !up; i++) {
    try { up = (await fetch(BASE + '/')).status > 0; } catch { await sleep(250); }
  }
  check('服务器启动（临时 HOME、图库、导出目录，卷根目录里还没有卡）', up);

  chrome = spawn(CHROME, [
    '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run', `--remote-debugging-port=${CHROME_PORT}`,
    `--user-data-dir=${P.profile}`, '--window-size=1400,900', 'about:blank',
  ], { stdio: 'ignore' });
  let targets;
  for (let i = 0; i < 60; i++) {
    try {
      targets = await (await fetch(`http://127.0.0.1:${CHROME_PORT}/json`)).json();
      if (targets.some((t) => t.type === 'page')) break;
    } catch {}
    await sleep(250);
  }
  ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener('open', r));
  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
    if (msg.method === 'Runtime.exceptionThrown') {
      const d = msg.params.exceptionDetails;
      errors.push('exception: ' + (d.exception?.description || d.text) + ' @' + d.lineNumber);
    }
    if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') errors.push('console: ' + JSON.stringify(msg.params.args.map((a) => a.value || a.description)));
    if (msg.method === 'Network.responseReceived' && msg.params.response.status >= 400) {
      badResponses.push(`${msg.params.response.status} ${new URL(msg.params.response.url).pathname}`);
    }
  });
  for (const d of ['Page', 'Runtime', 'DOM', 'Network']) await send(`${d}.enable`);

  // 1. 首次打开
  phase('1 首次打开');
  await send('Page.navigate', { url: `${BASE}/?token=${TOKEN}` });
  check('页面加载', await waitFor(`!!document.querySelector('#tabs a[data-tab=photos]')`));
  check('首次打开显示新手引导', await waitFor(`!!document.querySelector('.modal-overlay')`, 5000));
  await shot('01-first-open.png');
  await clickButton('跳过', '.modal');
  check('跳过引导后图库为空、写明还没有照片', await waitFor(`/还没有照片/.test(document.querySelector('#view').textContent)`, 5000));
  await evaluate('performance.setResourceTimingBufferSize(3000)');
  let st = await getJson('/api/camdata/status');
  check('状态：没有相机数据、没有标定、没有卡', st.ready === false && st.camera_data.imported === false && st.calibration.state === 'missing' && st.cards.length === 0, JSON.stringify({ next: st.next, cards: st.cards.length }));

  // 2. 插假卡 + 导入照片
  phase('2 插入假卡，自动导入照片');
  renameSync(stagedCard, join(P.vol, 'FAKECARD')); // "插卡"：同一个文件系统内改名，瞬间完成
  const card = join(P.vol, 'FAKECARD');
  check('插卡后出现导入横幅', await waitFor(`document.querySelector('#banner').textContent.trim().length > 0`, 12000));
  check('导入完成横幅', await waitFor(`/导入完成/.test(document.querySelector('#banner').textContent)`, 60000), (await text('#banner')).trim().slice(0, 60));
  check('图库有缩略图', await waitFor(`document.querySelectorAll('.thumb').length >= 10`, 10000), `数量 ${await evaluate(`document.querySelectorAll('.thumb').length`)}`);
  await shot('02-card-imported.png');
  st = await getJson('/api/camdata/status');
  check('状态里列出这张卡带 GXRCE.DAT', st.cards.length === 1 && st.cards[0].has_dat === true, JSON.stringify(st.cards));
  await clickButton('知道了', '#banner');
  const photos = await getJson('/api/photos?limit=5000');
  const pair = photos.find((p) => p.has_raw && p.has_jpg && /^R805/.test(p.name)) || photos.find((p) => p.has_raw && p.has_jpg);
  const rawOnly = photos.find((p) => p.has_raw && !p.has_jpg);
  check('有一对可解码的 DNG+JPG 和一张只有 DNG 的', !!pair && !!rawOnly, `${pair?.name} / ${rawOnly?.name}`);
  const srcBeforeImport = await thumbSrcOf('只有 DNG');
  check('导入前只有 DNG 的缩略图地址带的版本是 none-none（还没有任何数据）', /\?v=none-none$/.test(srcBeforeImport || ''), srcBeforeImport);

  // 3. 打开 DNG → 配方标签 → 引导
  phase('3 打开 DNG，配方标签里没有相机数据');
  await api(`/api/photos/${pair.id}/edit`, { method: 'DELETE' });
  const clickedThumb = await evaluate(`(() => { const img = [...document.querySelectorAll('.thumb img')].find(i => i.alt === ${JSON.stringify(pair.name)}); if (!img) return false; img.parentElement.click(); return true; })()`);
  check('点开这一对（DNG+JPG）', clickedThumb && (await waitFor(`!!document.querySelector('.viewer .side-tabs')`, 10000)));
  await clickButton('配方', '.side-tabs');
  check('配方标签：8 个底子', await waitFor(`document.querySelectorAll('.base-grid button').length === 8`, 8000));
  check('没有相机数据：显示「从卡导入」引导', await waitFor(`[...document.querySelectorAll('.camdata-guide button')].some(b => b.textContent.includes('从卡导入'))`, 6000));
  await shot('03-recipes-no-camdata.png');

  // 4. 从卡导入相机数据
  phase('4 点「从卡导入」');
  const cardSnapshotBeforeImport = treeHash(card);
  check('点「从卡导入」', await clickButton('从卡导入', '.camdata-guide'));
  check('引导变成「还差颜色标定」', await waitFor(`/还差颜色标定/.test((document.querySelector('.camdata-guide')||{}).textContent || '')`, 15000), (await text('.camdata-guide')).trim().slice(0, 80));
  check('引导指向「设置」里的开发用入口', await evaluate(`[...document.querySelectorAll('.camdata-guide button')].some(b => b.textContent.includes('导入颜色标定（开发用）'))`));
  await shot('04-calibration-guide.png');
  st = await getJson('/api/camdata/status');
  check('相机数据已导入：第 135 代，来源是这张卡', st.camera_data.imported === true && st.camera_data.generation === 135 && st.camera_data.source.sha256 === SHA_135 && st.camera_data.source.origin?.label === 'FAKECARD',
    JSON.stringify({ gen: st.camera_data.generation, origin: st.camera_data.source?.origin }));
  check('标定仍是缺的，所以还不能出图', st.ready === false && st.next === 'import_calibration', st.next);
  check('卡上的文件导入前后完全一致（大小、修改时间、哈希）', JSON.stringify(treeHash(card)) === JSON.stringify(cardSnapshotBeforeImport) && JSON.stringify(treeHash(card)) === JSON.stringify(Object.fromEntries(Object.entries(cardBefore))));

  // 4b. 回到图库，在「设置」里用文件选择器换一代、再从卡换回来：图库的缩略图地址要跟着变
  phase('4b 图库里：设置 → 选择文件（g127）→ 再从卡导入（g135）');
  await evaluate(`location.hash = '#/photos'`);
  check('回到图库', await waitFor(`document.querySelectorAll('.thumb').length >= 10`, 8000));
  const srcAfterCard = await thumbSrcOf('只有 DNG');
  check('导入相机数据后，只有 DNG 的缩略图地址的版本变了（浏览器不会再用旧图）', /\?v=/.test(srcAfterCard || '') && srcAfterCard !== srcBeforeImport, srcAfterCard);
  check('有 JPG 的照片地址不带 ?v=', !/\?v=/.test(await evaluate(`[...document.querySelectorAll('.thumb img')].find(i => i.alt === ${JSON.stringify(pair.name)}).getAttribute('src')`)));
  check('打开设置', await openSettings());
  check('设置里写明：颜色标定这一步目前只在开发机上可用', /只在开发这个工具的电脑上能用/.test(await text('.modal [data-section=calibration]')) && /开发用/.test(await text('.modal [data-section=calibration]')));
  check('设置里的摘要：相机数据已导入第 135 代，标定还没导入', /已导入（第 135 代）/.test(await text('[data-section=camdata-status]')) && /还没导入/.test(await text('[data-section=camdata-status]')), (await text('[data-section=camdata-status]')).trim());
  await shot('05-settings-top.png');
  await evaluate(`document.querySelector('[data-section=calibration]').scrollIntoView({ block: 'end' })`);
  await shot('05b-settings-calibration-entry.png');
  await chooseFile('.modal input[type=file]', join(P.upload, 'older GXRCE.DAT'));
  check('选文件上传 g127：摘要变成第 127 代', await waitFor(`/第 127 代/.test(document.querySelector('[data-section=camdata-status]').textContent)`, 15000));
  st = await getJson('/api/camdata/status');
  check('后端记录：g127，来源是「文件」，不带本地路径', st.camera_data.generation === 127 && st.camera_data.source.sha256 === SHA_127 && st.camera_data.source.origin?.kind === 'file' && st.camera_data.source.name === 'older GXRCE.DAT' && !JSON.stringify(st).includes(TMP));
  check('图库里只有 DNG 的缩略图地址随之换新（不用刷新页面）', await waitFor(`(() => { const t = [...document.querySelectorAll('.thumb')].find(t => t.querySelector('.tag').textContent === '只有 DNG'); return t.querySelector('img').getAttribute('src') !== ${JSON.stringify(srcAfterCard)}; })()`, 8000));
  check('设置里点「从卡导入」换回第 135 代', await clickButton('从卡导入', '.modal') && (await waitFor(`/第 135 代/.test(document.querySelector('[data-section=camdata-status]').textContent)`, 15000)));
  await closeModal();

  // 5. 导入标定包（开发方式），在大图打开着的时候
  phase('5 打开大图，设置 → 导入颜色标定（开发用）');
  await evaluate(`location.hash = '#/photo/${pair.id}'`);
  check('大图打开', await waitFor(`!!document.querySelector('.viewer .side-tabs')`, 8000));
  await clickButton('配方', '.side-tabs');
  check('配方标签里仍是「还差颜色标定」', await waitFor(`/还差颜色标定/.test((document.querySelector('.camdata-guide')||{}).textContent || '')`, 8000));
  const photoFetches = () => evaluate(`performance.getEntriesByType('resource').filter(e => new URL(e.name).pathname === '/api/photos/${pair.id}').length`);
  const fetchesBefore = await photoFetches();
  check('打开设置', await openSettings());
  check('先不填路径就点：提示要填路径', await clickButton('导入颜色标定（开发用）', '.modal') && (await waitFor(`/请先填写文件夹/.test(document.querySelector('[data-section=calibration]').textContent)`, 3000)));
  await typeInto('.modal [data-section=calibration] input[type=text]', REPO);
  check('填入仓库根目录，点导入', await clickButton('导入颜色标定（开发用）', '.modal'));
  check('设置里提示已导入标定包（开发机研究目录）', await waitFor(`/已导入标定包（开发机研究目录）/.test(document.querySelector('[data-section=calibration]').textContent)`, 90000), (await text('[data-section=calibration] [role=status]')).trim());
  check('设置摘要：标定已导入', await waitFor(`/颜色标定：已导入/.test(document.querySelector('[data-section=camdata-status]').textContent)`, 5000));
  await evaluate(`document.querySelector('[data-section=calibration] [role=status]').scrollIntoView({ block: 'end' })`);
  await shot('06-calibration-imported.png');
  await closeModal();
  st = await getJson('/api/camdata/status');
  check('后端：ready，下一步为空', st.ready === true && st.next === null, JSON.stringify({ ready: st.ready, next: st.next, cal: st.calibration.state }));
  check('大图打开着，导入后自动刷新：引导消失', await waitFor(`!document.querySelector('.camdata-guide')`, 15000));
  check('大图打开着，导入后重新取了这张照片的信息', (await photoFetches()) > fetchesBefore, `${fetchesBefore} → ${await photoFetches()}`);
  check('预览是图片（blob），不是照片本身', await waitFor(`(document.querySelector('.stage img.photo')||{}).src?.startsWith('blob:')`, 30000));
  check('预览说明里有「电脑预测」', /电脑预测/.test(await text('.stage-note')), (await text('.stage-note')).trim().slice(0, 70));

  // 6. 套配方，调旋钮
  phase('6 套用配方、调旋钮');
  check('点底子「05 富士 CC」', await clickButton('05 富士 CC'));
  let edit = await getJson(`/api/photos/${pair.id}/edit`);
  check('配方已保存：05', edit.recipe && edit.recipe.slot === 5, JSON.stringify(edit.recipe));
  check('拖「对比」滑块', await setRange('对比', 2));
  check('预览按新参数重新渲染', await waitFor(`(document.querySelector('.stage img.photo')||{}).src?.startsWith('blob:')`, 30000));
  await sleep(800);
  edit = await getJson(`/api/photos/${pair.id}/edit`);
  check('对比保存到 sidecar', edit.recipe && edit.recipe.levels && edit.recipe.levels.contrast !== undefined, JSON.stringify(edit.recipe?.levels));
  check('旋钮标签：有「相机」类标签（第 135 代）', await evaluate(`[...document.querySelectorAll('.knob-tag')].some(t => t.textContent === '相机')`));
  await shot('07-recipe-applied.png');

  // 7. 曝光和曲线
  phase('7 调整：曝光和曲线');
  await clickButton('调整', '.side-tabs');
  check('调整标签：曝光滑块', await waitFor(`!!document.querySelector('input[aria-label=曝光]')`, 8000));
  check('曝光 +0.7 EV', await setRange('曝光', 0.7));
  await sleep(900);
  check('曲线：起始两个点', await waitFor(`document.querySelectorAll('.curve .curve-point').length === 2`, 4000));
  // 曲线在面板的最下面，先滚到可见，再量坐标（视口外的鼠标事件点不到它）
  const cb = await evaluate(`(() => { const el = document.querySelector('.curve'); el.scrollIntoView({ block: 'center' }); const r = el.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; })()`);
  const px = cb.x + cb.w * 0.5;
  const py = cb.y + cb.h * 0.5;
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: px, y: py, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: px, y: py - 20, button: 'left' });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: px, y: py - 20, button: 'left', clickCount: 1 });
  await sleep(900);
  check('曲线：点空白处加了一个点（3 / 16）', await waitFor(`(document.querySelector('.curve-wrap span')||{}).textContent.startsWith('3 / 16')`, 3000));
  edit = await getJson(`/api/photos/${pair.id}/edit`);
  check('曝光和曲线保存到 sidecar', edit.adjust?.exposure_ev === 0.7 && edit.curve?.master?.length === 3, JSON.stringify({ ev: edit.adjust?.exposure_ev, pts: edit.curve?.master?.length }));
  check('调整后的预览仍是图片（blob）', await waitFor(`(document.querySelector('.stage img.photo')||{}).src?.startsWith('blob:')`, 30000));
  await shot('08-adjust-curve.png');

  // 8. 裁成 XPan
  phase('8 裁切成 XPan 65:24');
  await clickButton('裁切', '.side-tabs');
  check('裁切标签：点「XPan 65:24」', await waitFor(`[...document.querySelectorAll('.viewer button')].some(b => b.textContent.trim() === 'XPan 65:24')`, 5000) && (await clickButton('XPan 65:24')));
  await sleep(800);
  const crop = await getJson(`/api/photos/${pair.id}/crop`);
  const ratio = crop.pixels ? crop.pixels.width / crop.pixels.height : null;
  check('XPan 已写进 sidecar，比例约 65:24', crop.active === true && crop.preset === 'xpan-65-24' && ratio !== null && Math.abs(ratio - 65 / 24) < 0.02, JSON.stringify({ preset: crop.preset, active: crop.active, pixels: crop.pixels }));
  check('配方、曝光、曲线没有被裁切冲掉（同一份 sidecar）', await (async () => {
    const e = await getJson(`/api/photos/${pair.id}/edit`);
    return e.recipe?.slot === 5 && e.adjust?.exposure_ev === 0.7 && e.curve?.master?.length === 3;
  })());
  check('裁切后没有出现红色错误提示（例如「编辑已经被改过」）', await evaluate(`!document.querySelector('.toast.error')`));
  check('画面上出现裁切框',await evaluate(`document.querySelector('.crop-box').style.width !== ''`));
  await shot('09-crop-xpan.png');

  // 9. 导出
  phase('9 导出');
  await clickButton('导出', '.side-tabs');
  check('导出标签：写明电脑预测的配方效果', await waitFor(`document.querySelector('.side-body').textContent.includes('电脑预测的配方效果')`, 5000));
  check('点「开始导出」', await clickButton('开始导出', '.side-body'));
  check('导出完成（电脑预测）', await waitFor(`/导出完成（电脑预测）/.test((document.querySelector('.side .result')||{}).textContent || '')`, 120000), (await text('.side .result')).trim().slice(0, 100));
  await shot('10-export-done.png');

  // 10. 确认导出的文件
  phase('10 确认导出的文件');
  const exported = readdirSync(P.exp);
  check('导出目录里恰好一个文件', exported.length === 1, JSON.stringify(exported));
  const file = join(P.exp, exported[0] || '');
  check('文件名带「电脑预测」', /电脑预测/.test(exported[0] || ''), exported[0]);
  const buf = existsSync(file) ? readFileSync(file) : Buffer.alloc(0);
  check('是有内容的 JPEG', buf.length > 10000 && buf[0] === 0xff && buf[1] === 0xd8, `${buf.length} 字节`);
  const size = jpegSize(buf);
  check('导出尺寸是 XPan 比例（约 65:24）', !!size && Math.abs(size.w / size.h - 65 / 24) < 0.02, JSON.stringify(size));
  const shownPath = await text('.side .result code');
  check('界面显示的路径就是这个文件', shownPath.trim() === file || shownPath.trim().endsWith(exported[0] || '?'), shownPath.trim().slice(-60));

  // 11. 收尾检查
  phase('11 收尾检查');
  const cardAfter = treeHash(card);
  check('整个流程之后，卡上的文件仍然一字未改', JSON.stringify(cardAfter) === JSON.stringify(cardBefore), `${Object.keys(cardAfter).length} 个文件`);
  const unexpected = badResponses.filter((r) => !/^409 \/api\/photos\/[0-9a-f]+\/render$/.test(r));
  check('没有意外的 4xx/5xx 响应（还没标定时渲染的 409 除外）', unexpected.length === 0, `${badResponses.length} 条：${[...new Set(badResponses)].join(' | ')}`);
  check('浏览器没有未捕获的异常或控制台错误（409 的网络日志除外）', errors.filter((e) => !/Failed to load resource.*409/.test(e)).length === 0, errors.slice(0, 3).join(' | '));
  exitCode = results.some((r) => r.startsWith('FAIL')) ? 1 : 0;
} catch (err) {
  console.log('走查中断：' + (err && err.stack || err));
  results.push('FAIL 走查中断 ' + (err && err.message));
  exitCode = 1;
} finally {
  try { ws && ws.close(); } catch {}
  await cleanup();
  const failed = results.filter((r) => r.startsWith('FAIL')).length;
  console.log(`\nPASS: ${results.length - failed}   FAIL: ${failed}   浏览器错误记录: ${errors.length}   4xx/5xx: ${badResponses.length}`);
  if (failed) console.log(results.filter((r) => r.startsWith('FAIL')).join('\n'));
  writeFileSync(join(HERE, 'walkthrough_result.txt'), results.join('\n') + `\n\nPASS: ${results.length - failed}   FAIL: ${failed}\n浏览器错误记录: ${JSON.stringify(errors)}\n4xx/5xx: ${JSON.stringify(badResponses)}\n临时目录已删除: ${!existsSync(TMP)}\n`);
  process.exit(failed ? 1 : exitCode);
}
