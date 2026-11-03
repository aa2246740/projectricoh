// 在现有工作室里实测显卡预览：真实鼠标拖滑块（输入 → 显卡画完 → 下一次刷新），以及换照片（改 hash → 新照片第一帧画完）。
// 用法：node measure_studio.mjs <工作室 URL> <令牌> <cdp.mjs 目录> <用户目录> <输出 JSON> <照片 id,逗号分隔>
import fs from 'node:fs';
import { execSync } from 'node:child_process';

const [base, token, cdpDir, userDir, outPath, idsArg, seqArg] = process.argv.slice(2);
const { launch, pause, stats } = await import(`${cdpDir}/cdp.mjs`);
const ids = idsArg.split(',');
const load = () => execSync('uptime', { encoding: 'utf8' }).trim();
const result = { when: new Date().toISOString(), base, ids, load_before: load(), drags: [], switches: [] };

const HOOK_FN = `async () => {
  const gs = await import('/assets/gpu_stage.js');
  const m = window.__m = window.__m || { inputs: [], frames: [], rafs: [], rec: false };
  if (!window.__hooked) {
    window.__hooked = true;
    document.addEventListener('input', (e) => { if (m.rec && e.target && e.target.type === 'range') m.inputs.push({ t: performance.now(), v: +e.target.value }); }, true);
    const loop = (t) => { if (m.rec) m.rafs.push(t); requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  }
  const e = gs.gpuEngineForTests();
  if (e && !e.__hooked) {
    e.__hooked = true;
    e.onFrame = (f) => {
      const rec = { t: f.submitted, color: f.color, key: e.currentKey() };
      (m.allFrames = m.allFrames || []).push(rec);
      if (m.rec) {
        const pend = m.inputs.filter((i) => !i.frame);
        pend.forEach((i) => { i.frame = rec; });
        m.frames.push(rec);
      }
      e.device.queue.onSubmittedWorkDone().then(() => { rec.gpu = performance.now(); requestAnimationFrame(() => { rec.next = performance.now(); }); });
    };
  }
  return { engine: !!e, info: e && e.info };
}`;

const cdp = await launch({ userDataDir: userDir, width: 1440, height: 900 });
try {
  const page = await cdp.page();
  result.browser = (await cdp.send('Browser.getVersion')).product;
  await page.goto(`${base}/?token=${token}`);
  await page.eval(`window.__hookNow = ${HOOK_FN}; true`);
  result.gpu = await page.eval(`(() => { const gl = document.createElement('canvas').getContext('webgl2'); const x = gl.getExtension('WEBGL_debug_renderer_info'); return gl.getParameter(x.UNMASKED_RENDERER_WEBGL); })()`);

  async function openPhoto(id) {
    const t0 = await page.eval(`(() => { window.__m && (window.__m.allFrames = []); const t = performance.now(); location.hash = '#/photo/${id}'; return t; })()`);
    // 等到引擎画出这张照片的第一帧（颜色层重算过），或者退回了服务器出图（<img>）
    const r = await page.eval(`new Promise((res) => {
      const t0 = ${t0};
      const tick = () => {
        const m = window.__m || {};
        const f = (m.allFrames || []).find((x) => x.key && x.key.includes('${id}') && x.color && x.next);
        const img = document.querySelector('img.pv-img');
        if (f) return res({ way: 'gpu', firstFrameMs: f.next - t0, gpuDoneMs: f.gpu - t0, key: f.key });
        if (img && img.complete && img.naturalWidth && performance.now() - t0 > 50) return res({ way: 'server', ms: performance.now() - t0 });
        if (performance.now() - t0 > 20000) return res({ way: 'timeout' });
        window.__hookNow();
        setTimeout(tick, 4);
      };
      tick();
    })`, { timeoutMs: 30000 });
    return { id, ...r };
  }

  async function drag(label, seconds = 4, hz = 120) {
    const r = await page.eval(`(() => { const el = [...document.querySelectorAll('input[type=range]')].find((x) => x.getAttribute('aria-label') === ${JSON.stringify(label)}); if (!el) return null; el.scrollIntoView({ block: 'center' }); const b = el.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height, min: +el.min, max: +el.max, v: +el.value }; })()`);
    if (!r) return { label, error: 'no slider' };
    await page.eval(`(() => { const m = window.__m; m.inputs = []; m.frames = []; m.rafs = []; m.rec = true; })()`);
    const y = r.y + r.h / 2;
    const x0 = r.x + ((r.v - r.min) / (r.max - r.min)) * r.w;
    const amp = r.w * 0.3;
    const n = seconds * hz;
    await page.mouse('mousePressed', x0, y, 1, 'left');
    const wall0 = Date.now();
    for (let i = 1; i <= n; i++) {
      await page.mouse('mouseMoved', x0 + amp * Math.sin((i / n) * 2 * Math.PI), y, 1, 'left');
      const wait = wall0 + (i * 1000) / hz - Date.now();
      if (wait > 0) await pause(wait);
    }
    await page.mouse('mouseReleased', x0, y, 0, 'left');
    await pause(600);
    const d = await page.eval(`(() => { const m = window.__m; m.rec = false; return { inputs: m.inputs.map((i) => ({ t: i.t, gpu: i.frame && i.frame.gpu, next: i.frame && i.frame.next })), frames: m.frames.map((f) => ({ t: f.t, gpu: f.gpu, next: f.next, color: f.color })), rafs: m.rafs, imgs: document.querySelectorAll('img.pv-img').length, canvas: !!document.querySelector('canvas.pv-gpu') }; })()`);
    const iv = d.rafs.slice(1).map((t, i) => t - d.rafs[i]);
    const out = {
      label, mouse_hz: hz, inputs: d.inputs.length, frames: d.frames.length,
      inputs_without_frame: d.inputs.filter((i) => !i.gpu).length,
      raf_interval_ms: stats(iv), raf_over_1_5x_8_3ms: iv.filter((v) => v > 12.5).length,
      input_to_gpu_done_ms: stats(d.inputs.filter((i) => i.gpu).map((i) => i.gpu - i.t)),
      input_to_next_vsync_ms: stats(d.inputs.filter((i) => i.next).map((i) => i.next - i.t)),
      server_images_in_dom: d.imgs, canvas: d.canvas,
    };
    fs.writeFileSync(outPath.replace(/\.json$/, `-frames-${label}.json`), JSON.stringify(d));
    console.log('drag', label, JSON.stringify({ inputs: out.inputs, frames: out.frames, raf: out.raf_interval_ms, in2gpu: out.input_to_gpu_done_ms, in2vsync: out.input_to_next_vsync_ms, img: out.server_images_in_dom }));
    return out;
  }

  // 1) 冷打开第一张、装钩子
  result.switches.push({ kind: 'cold-first', ...(await openPhoto(ids[0])) });
  await page.eval('window.__hookNow()');
  // 2) 拖动（调整页）
  await page.eval(`(() => { const b = [...document.querySelectorAll('button[role=tab]')].find((x) => x.textContent.trim() === '调整'); b && b.click(); })()`);
  await pause(800);
  for (const label of ['曝光', '阴影', '饱和度']) result.drags.push(await drag(label));
  await page.screenshot(outPath.replace(/\.json$/, '-adjust.png'));
  // 3) 换照片。seqArg：'种类:照片id:看多久ms,...'。种类 jump = 不相邻（没有预取），next = 相邻且前一张看了一会儿，warm = 已看过
  const seq = seqArg ? seqArg.split(',').map((x) => x.split(':')) : [...ids.slice(1).map((id) => ['cold', id, '0']), ...ids.map((id) => ['warm', id, '0'])];
  for (const [kind, id, dwell] of seq) {
    result.switches.push({ kind, ...(await openPhoto(id)) });
    if (+dwell) await pause(+dwell);
  }
  result.load_after = load();
} finally {
  fs.writeFileSync(outPath, JSON.stringify(result, null, 1));
  await cdp.close();
}
const pick = (k) => stats(result.switches.filter((s) => s.kind === k && s.way === 'gpu').map((s) => s.firstFrameMs));
for (const k of [...new Set(result.switches.map((s) => s.kind))]) console.log('switch', k, JSON.stringify(pick(k)));
console.log(result.switches.map((s) => `${s.kind}:${s.way}:${Math.round(s.firstFrameMs ?? s.ms ?? -1)}`).join(' '));
