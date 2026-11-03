// 走查：导入「部分失败」时界面怎么说（studio-fix-review-r1，P0-1 / P2-4 / P2-10 的真浏览器核对）。手动运行，不属于 pytest。
//
//   运行：node research/studio_fix_review/browser_walkthrough_partial_import.mjs   （截图写到本目录 ./screenshots/）
//
// 全部在临时目录里：假卡（合成的，不含任何理光字节）、临时 HOME/图库/导出/卷根目录；不碰 /Volumes 下的真实卷。
// 场景：
//   A. 卷根目录读不了（chmod 000，模拟 macOS 没给「可移除的卷」权限）→ 页面明说，不是一直写"未插入"；恢复后提示消失；
//   B. 插卡，其中一对的 JPG 读不出来（chmod 000）→ 红色横幅、列出文件名、不说"可以安全弹出"、状态栏同样；好的 DNG 照常进了图库；
//   C. 关掉横幅后仍能「开始导入」重试；还读不出来就还是红色；
//   D. 把 JPG 恢复可读，继续导入 → 补全那一张（不是多出一张），这时才说"可以安全弹出卡了"；
//   E. 再插第二张卡 → 横幅和状态栏提示"插着 2 张卡，一次只处理第一张"。
// 同一时间只有 3 个进程：本脚本（node）、gxr-studio、Chrome。
import { spawn, execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, renameSync, rmSync, statSync, writeFileSync } from 'node:fs';
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

const SERVER_PORT = 8798;
const CHROME_PORT = 9336;
const BASE = `http://127.0.0.1:${SERVER_PORT}`;
const TOKEN = 'tokpart';
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
const TMP = mkdtempSync(join(tmpdir(), 'gxrpart-'));
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
  for (const p of [join(P.vol, 'FAKECARD/DCIM/100RICOH/R0000104.JPG'), P.vol]) { try { chmodSync(p, p === P.vol ? 0o755 : 0o644); } catch {} }
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
  const t = [...document.querySelectorAll('.thumb')].find(t => t.querySelector('.tag').textContent.startsWith(${JSON.stringify(kind)}));
  return t ? t.querySelector('img').getAttribute('src') : null;
})()`);

// ---- 主流程 -----------------------------------------------------------------------
let exitCode = 1;
const bannerText = () => text('#banner');
const statusText = () => text('#card-status');
try {
  phase('0 准备');
  const mk = (stageDir, label) => execFileSync(join(STUDIO, '.venv/bin/python'), ['-m', 'gxr_studio.devtools.synthetic_card', stageDir, '--label', label, '--no-real'], { cwd: STUDIO, stdio: 'ignore' });
  mk(P.stage, 'FAKECARD');
  mkdir2(join(P.stage, 'second'));
  mk(join(P.stage, 'second'), 'SECONDCARD');
  const jpgPath = join(P.stage, 'FAKECARD/DCIM/100RICOH/R0000104.JPG');
  check('假卡里有 R0000104 这一对 DNG+JPG', existsSync(jpgPath) && existsSync(jpgPath.replace('.JPG', '.DNG')));
  const jpgBytes = readFileSync(jpgPath);
  server = spawn(join(STUDIO, '.venv/bin/gxr-studio'), ['--no-browser', '--port', String(SERVER_PORT)], {
    cwd: STUDIO, stdio: 'ignore',
    env: { ...process.env, HOME: P.home, GXR_STUDIO_HOME: P.app, GXR_STUDIO_LIBRARY: P.lib, GXR_STUDIO_EXPORT: P.exp, GXR_STUDIO_VOLUMES: P.vol, GXR_STUDIO_TOKEN: TOKEN },
  });
  let up = false;
  for (let i = 0; i < 80 && !up; i++) { try { up = (await fetch(BASE + '/')).status > 0; } catch { await sleep(250); } }
  check('服务器启动', up);
  chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run', `--remote-debugging-port=${CHROME_PORT}`, `--user-data-dir=${P.profile}`, '--window-size=1400,900', 'about:blank'], { stdio: 'ignore' });
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
    if (msg.method === 'Runtime.exceptionThrown') { const d = msg.params.exceptionDetails; errors.push('exception: ' + (d.exception?.description || d.text) + ' @' + d.lineNumber); }
    if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') errors.push('console: ' + JSON.stringify(msg.params.args.map((a) => a.value || a.description)));
    if (msg.method === 'Network.responseReceived' && msg.params.response.status >= 400) badResponses.push(`${msg.params.response.status} ${new URL(msg.params.response.url).pathname}`);
  });
  for (const d of ['Page', 'Runtime', 'DOM', 'Network']) await send(`${d}.enable`);

  // A. 卷根目录读不了
  phase('A 系统不让读外接卡（卷根目录 chmod 000）');
  chmodSync(P.vol, 0o000);
  await send('Page.navigate', { url: `${BASE}/?token=${TOKEN}` });
  check('页面加载', await waitFor(`!!document.querySelector('#tabs a[data-tab=photos]')`));
  check('首次打开的新手引导出现', await waitFor(`!!document.querySelector('.modal-overlay')`, 8000));
  check('点「跳过」，引导关掉（它会挡住横幅上的按钮，所以要等它真的消失）', (await clickButton('跳过', '.modal')) && (await waitFor(`!document.querySelector('.modal-overlay')`, 5000)));
  check('横幅明说：电脑不让读，并指到「可移除的卷」', await waitFor(`/可移除的卷/.test(document.querySelector('#banner').textContent)`, 10000), (await bannerText()).trim().slice(0, 80));
  check('状态栏不再只写"未插入"', await waitFor(`/不让工作室读/.test(document.querySelector('#card-status').textContent)`, 5000), (await statusText()).trim());
  await shot('A-permission-denied.png');
  chmodSync(P.vol, 0o755);
  check('恢复权限后提示消失，状态栏回到"未插入"', await waitFor(`!/可移除的卷/.test(document.querySelector('#banner').textContent) && /未插入/.test(document.querySelector('#card-status').textContent)`, 10000), (await statusText()).trim());

  // B. 插卡，JPG 读不出来
  phase('B 插卡，R0000104.JPG 读不出来');
  chmodSync(jpgPath, 0o000);
  const cardBefore = statTree(join(P.stage, 'FAKECARD'));
  renameSync(join(P.stage, 'FAKECARD'), join(P.vol, 'FAKECARD'));
  const card = join(P.vol, 'FAKECARD');
  check('出现"导入没有全部完成"横幅', await waitFor(`/导入没有全部完成/.test(document.querySelector('#banner').textContent)`, 60000), (await bannerText()).trim().slice(0, 100));
  await sleep(500);
  const banner = (await bannerText()).trim();
  check('横幅是红色（bad），不是绿色', await evaluate(`document.querySelector('#banner .banner').classList.contains('bad') && !document.querySelector('#banner .banner').classList.contains('ok')`));
  check('横幅不说"可以安全弹出"', !/安全弹出/.test(banner), banner.slice(0, 120));
  check('横幅建议先别格式化', /先别格式化/.test(banner));
  check('横幅列出没导进来的文件名 R0000104.JPG', /没导进来的：.*R0000104\.JPG/.test(banner), banner.slice(-60));
  const st1 = (await statusText()).trim();
  check('状态栏也不说可以弹出，并提醒先别格式化', !/安全弹出/.test(st1) && /先别格式化/.test(st1), st1);
  check('横幅里有「继续导入」', await evaluate(`[...document.querySelectorAll('#banner button')].some(b => b.textContent.trim() === '继续导入')`));
  await shot('B-partial-import.png');
  let photos = await getJson('/api/photos?limit=5000');
  const r104 = photos.find((p) => p.name === 'R0000104');
  check('好的 DNG 照常导入了：R0000104 在图库里，只有 DNG', !!r104 && r104.has_raw && !r104.has_jpg, JSON.stringify(r104 && { raw: r104.has_raw, jpg: r104.has_jpg }));
  const job = (await getJson('/api/jobs')).find((j) => j.kind === 'import');
  check('后端进度：unreadable 列出 JPG，failed_shots = 1，消息里没有"安全弹出"', job.progress.unreadable.length === 1 && /R0000104\.JPG$/.test(job.progress.unreadable[0]) && job.progress.failed_shots === 1 && !/安全弹出/.test(job.progress.message));

  // C. 关掉横幅，重试，仍失败
  phase('C 关掉横幅，再点「开始导入」，仍然读不出来');
  const btnsBefore = await evaluate(`[...document.querySelectorAll('#banner button')].map(b => b.textContent.trim() + '@' + Math.round(b.getBoundingClientRect().left) + ',' + Math.round(b.getBoundingClientRect().top)).join(' ')`);
  check('点「知道了」', await clickButton('知道了', '#banner'), btnsBefore);

  check('关掉后出现「开始导入」（这张卡没算处理完）', await waitFor(`[...document.querySelectorAll('#banner button')].some(b => b.textContent.trim() === '开始导入')`, 6000), `banner=[${(await bannerText()).trim().slice(0, 100)}] status=[${(await statusText()).trim()}]`);
  check('点「开始导入」', await clickButton('开始导入', '#banner'));
  check('再次是红色的"导入没有全部完成"', await waitFor(`/导入没有全部完成/.test(document.querySelector('#banner').textContent) && document.querySelector('#banner .banner').classList.contains('bad')`, 60000));
  check('仍然没有"安全弹出"', !/安全弹出/.test(await bannerText()));

  // D. 恢复可读，继续导入
  phase('D 把 JPG 恢复可读，点「继续导入」');
  chmodSync(join(P.vol, 'FAKECARD/DCIM/100RICOH/R0000104.JPG'), 0o644);
  check('点「继续导入」', await clickButton('继续导入', '#banner'));
  check('出现绿色的"导入完成"，写明补全 1 张', await waitFor(`/导入完成/.test(document.querySelector('#banner').textContent) && document.querySelector('#banner .banner').classList.contains('ok')`, 60000), (await bannerText()).trim().slice(0, 100));
  const done = (await bannerText()).trim();
  check('这时才说"现在可以安全弹出卡了"，并写明补全 1 张', /现在可以安全弹出卡了/.test(done) && /补全 1 张/.test(done), done.slice(0, 120));
  check('状态栏：可以安全弹出', /可以安全弹出卡了/.test(await statusText()), (await statusText()).trim());
  await shot('D-completed.png');
  photos = await getJson('/api/photos?limit=5000');
  const now104 = photos.filter((p) => p.name === 'R0000104');
  check('R0000104 只有一张，现在是 DNG+JPG（补全，不是多出一张）', now104.length === 1 && now104[0].has_raw && now104[0].has_jpg, JSON.stringify(now104.map((p) => [p.has_raw, p.has_jpg])));
  check('图库里它的角标是 DNG+JPG', await waitFor(`[...document.querySelectorAll('.thumb')].some(t => t.querySelector('img').alt === 'R0000104' && t.querySelector('.tag').textContent === 'DNG+JPG')`, 8000));
  const libJpg = join(P.lib, now104[0].date?.slice(0, 4) || '', now104[0].date || '', 'R0000104.JPG');
  check('图库里的 JPG 和卡上的内容逐字节一致', existsSync(libJpg) && sha(readFileSync(libJpg)) === sha(jpgBytes));

  // E. 第二张卡
  phase('E 再插第二张卡');
  await clickButton('知道了', '#banner');
  renameSync(join(P.stage, 'second', 'SECONDCARD'), join(P.vol, 'SECONDCARD'));
  check('横幅提示插着 2 张卡、一次只处理第一张', await waitFor(`!!document.querySelector('#banner [data-note=multi-card]') && /2 张卡/.test(document.querySelector('#banner [data-note=multi-card]').textContent)`, 12000), (await bannerText()).trim().slice(0, 120));
  check('状态栏提示另外还插着 1 张卡', await waitFor(`/另外还插着 1 张卡/.test(document.querySelector('#card-status').textContent)`, 5000), (await statusText()).trim());
  await shot('E-two-cards.png');

  // 收尾
  phase('收尾');
  const cardAfter = statTree(card);
  check('整个过程之后，卡上每个文件的大小和修改时间都没变（只读）', JSON.stringify(cardAfter) === JSON.stringify(cardBefore), `${Object.keys(cardAfter).length} 个文件`);
  const unexpected = badResponses.filter((r) => !/^403 /.test(r));
  check('没有意外的 4xx/5xx 响应', unexpected.length === 0, `${badResponses.length} 条：${[...new Set(badResponses)].join(' | ')}`);
  check('浏览器没有未捕获的异常或控制台错误（CSP 违规也算控制台错误）', errors.length === 0, errors.slice(0, 3).join(' | '));
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
  writeFileSync(join(HERE, 'walkthrough_partial_result.txt'), results.join('\n') + `\n\nPASS: ${results.length - failed}   FAIL: ${failed}\n浏览器错误记录: ${JSON.stringify(errors)}\n4xx/5xx: ${JSON.stringify(badResponses)}\n临时目录已删除: ${!existsSync(TMP)}\n`);
  process.exit(failed ? 1 : exitCode);
}
function statTree(root) {
  const out = {};
  const walk = (dir) => {
    for (const name of readdirSync(dir).sort()) {
      const p = join(dir, name);
      const st = statSync(p);
      if (st.isDirectory()) walk(p);
      else out[p.slice(root.length)] = `${st.size}:${st.mtimeMs}`;
    }
  };
  walk(root);
  return out;
}
function mkdir2(p) { mkdirSync(p, { recursive: true }); }
