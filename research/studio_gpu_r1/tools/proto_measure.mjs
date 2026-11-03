// 原型实测：显卡信息、拖动帧时间、换照片、显存/内存、读回（颜色一致性）、全尺寸导出。
// 用法：node proto_measure.mjs <原型 URL> <输出 JSON> <scratch 用户目录> <阶段,逗号分隔: smoke,drag,switch,readback,export,hdr>
import fs from 'node:fs';
import { execSync } from 'node:child_process';
import { launch, pause, stats } from './cdp.mjs';

const [url, outPath, userDir, stagesArg] = process.argv.slice(2);
const stages = new Set((stagesArg || 'smoke').split(','));
const HERE = new URL('.', import.meta.url).pathname;
const sets = JSON.parse(fs.readFileSync(`${HERE}/../proto/paramsets.json`, 'utf8'));

function gpuProcessRss(chromePid) {
  try {
    const ps = execSync('ps -axo pid,ppid,rss,command', { encoding: 'utf8', maxBuffer: 1 << 24 });
    const rows = ps.split('\n').slice(1).map((l) => l.trim().match(/^(\d+)\s+(\d+)\s+(\d+)\s+(.*)$/)).filter(Boolean).map((m) => ({ pid: +m[1], ppid: +m[2], rss: +m[3], cmd: m[4] }));
    const kids = rows.filter((r) => r.ppid === chromePid);
    const gpu = kids.find((r) => r.cmd.includes('--type=gpu-process'));
    const renderers = kids.filter((r) => r.cmd.includes('--type=renderer'));
    return { gpu_mb: gpu ? +(gpu.rss / 1024).toFixed(0) : null, renderer_mb: renderers.map((r) => +(r.rss / 1024).toFixed(0)), total_mb: +((kids.reduce((s, r) => s + r.rss, 0) + (rows.find((r) => r.pid === chromePid)?.rss || 0)) / 1024).toFixed(0) };
  } catch (e) {
    return { error: String(e) };
  }
}
function load() {
  try { return execSync('uptime', { encoding: 'utf8' }).trim(); } catch { return null; }
}

const result = { when: new Date().toISOString(), url, load_before: load(), stages: [...stages] };
const cdp = await launch({ userDataDir: userDir, width: 1440, height: 900, extra: (process.env.CHROME_EXTRA || '').split(' ').filter(Boolean) });
const errors = [];
try {
  const page = await cdp.page();
  cdp.on((m) => {
    if (m.method === 'Runtime.exceptionThrown') errors.push(JSON.stringify(m.params.exceptionDetails).slice(0, 600));
    if (m.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(m.params.type)) errors.push(m.params.args.map((a) => a.value ?? a.description).join(' ').slice(0, 600));
  });
  result.browser = (await cdp.send('Browser.getVersion')).product;
  await page.goto(url);
  result.ready = await page.eval('window.__ready', { timeoutMs: 60000 });
  result.webgl = await page.eval(`(() => { const gl = document.createElement('canvas').getContext('webgl2'); const e = gl.getExtension('WEBGL_debug_renderer_info'); return gl.getParameter(e.UNMASKED_RENDERER_WEBGL); })()`);
  result.display = await page.eval(`({ dpr: devicePixelRatio, screen: [screen.width, screen.height], colorGamutP3: matchMedia('(color-gamut: p3)').matches, colorGamutRec2020: matchMedia('(color-gamut: rec2020)').matches, dynamicRangeHigh: matchMedia('(dynamic-range: high)').matches, videoDynamicRangeHigh: matchMedia('(video-dynamic-range: high)').matches, canvasSize: [document.getElementById('stage').width, document.getElementById('stage').height] })`);
  console.log('ready', JSON.stringify(result.ready), result.webgl, JSON.stringify(result.display));
  const chromePid = cdp.proc.pid;
  result.mem_after_ready = gpuProcessRss(chromePid);

  if (stages.has('switch')) {
    const names = await page.eval(`(async () => (await (await fetch('/data/index.json')).json()).photos.map((p) => p.name))()`);
    const runs = [];
    for (const n of names) runs.push(await page.eval(`window.__open(${JSON.stringify(n)}, 'proxy')`));      // 首次：下载 float16 代理图
    for (const n of names) runs.push(await page.eval(`window.__open(${JSON.stringify(n)}, 'proxy')`));      // 已在显存
    await page.eval(`(() => { for (const k of [...__eng.photos.keys()]) { const p = __eng.photos.get(k); p.proxyTex.destroy(); p.colorTex.destroy(); } __eng.photos.clear(); })()`);
    for (const n of names) runs.push({ ...(await page.eval(`window.__open(${JSON.stringify(n)}, 'raw')`)), note: 'DNG 字节 → 显卡拆包合并' });
    result.switch = runs;
    const f = (pred) => stats(runs.filter(pred).map((r) => r.to_first_frame_ms));
    result.switch_summary = { proxy_first: f((r) => r.mode === 'proxy' && !r.cached), cached: f((r) => r.cached), raw_gpu: f((r) => r.mode === 'raw' && !r.cached) };
    console.log('switch', JSON.stringify(result.switch_summary));
    result.mem_after_switch = gpuProcessRss(chromePid);
    result.gpu_bytes_est = await page.eval('__eng.bytes');
  }

  if (stages.has('drag')) {
    const names = await page.eval(`(async () => (await (await fetch('/data/index.json')).json()).photos.map((p) => p.name))()`);
    result.drag = [];
    for (const [label, preset] of [['曝光', null], ['曝光', 'lut'], ['阴影', null], ['拉直', null]]) {
      await page.eval(`window.__open(${JSON.stringify(names[0])})`);
      await page.eval('window.__reset()');
      if (preset === 'lut') await page.eval(`window.__applySet(${JSON.stringify(sets.find((s) => s.id === 's5_lut_display'))})`);
      await pause(300);
      const r = await page.eval(`(() => { const el = [...document.querySelectorAll('input[type=range]')].find((x) => x.getAttribute('aria-label') === ${JSON.stringify(label)}); el.scrollIntoView({ block: 'center' }); const b = el.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height, min: +el.min, max: +el.max, v: +el.value }; })()`);
      await page.eval(`(() => { __m.inputs = []; __m.frames = []; __m.rafs = []; __m.recording = true; })()`);
      const y = r.y + r.h / 2, x0 = r.x + ((r.v - r.min) / (r.max - r.min)) * r.w, amp = r.w * 0.3;
      const hz = 120, n = 4 * hz;
      await page.mouse('mousePressed', x0, y, 1, 'left');
      const wall0 = Date.now();
      for (let i = 1; i <= n; i++) {
        await page.mouse('mouseMoved', x0 + amp * Math.sin((i / n) * 2 * Math.PI), y, 1, 'left');
        const wait = wall0 + (i * 1000) / hz - Date.now();
        if (wait > 0) await pause(wait);
      }
      await page.mouse('mouseReleased', x0, y, 0, 'left');
      await pause(500);
      const d = await page.eval(`(() => { __m.recording = false; return { inputs: __m.inputs.map((i) => ({ t: i.t, v: i.v, gpuDone: i.frame && i.frame.gpuDone, nextRaf: i.frame && i.frame.nextRafNow, raf: i.frame && i.frame.raf })), frames: __m.frames.map((f) => ({ raf: f.raf, cpu: f.cpu, color: f.color, gpuDone: f.gpuDone, nextRaf: f.nextRafNow, inputs: f.inputs })), rafs: __m.rafs }; })()`);
      const rafInt = d.rafs.slice(1).map((t, i) => t - d.rafs[i]);
      const toGpu = d.inputs.filter((i) => i.gpuDone).map((i) => i.gpuDone - i.t);
      const toPresent = d.inputs.filter((i) => i.nextRaf).map((i) => i.nextRaf - i.t);
      const frameGpu = d.frames.filter((f) => f.gpuDone).map((f) => f.gpuDone - (f.raf));
      const span = (d.rafs[d.rafs.length - 1] - d.rafs[0]) / 1000;
      const out = {
        slider: label, preset, mouse_hz: hz, inputs: d.inputs.length, frames_drawn: d.frames.length,
        drawn_fps: +(d.frames.length / span).toFixed(1),
        raf_interval_ms: stats(rafInt),
        raf_over_16_7ms: rafInt.filter((v) => v > 16.7 * 1.5).length,
        raf_over_8_3ms: rafInt.filter((v) => v > 8.34 * 1.5).length,
        cpu_encode_ms: stats(d.frames.map((f) => f.cpu)),
        frame_raf_to_gpu_done_ms: stats(frameGpu),
        input_to_gpu_done_ms: stats(toGpu),
        input_to_next_vsync_ms: stats(toPresent),
        inputs_without_frame: d.inputs.filter((i) => !i.gpuDone).length,
      };
      result.drag.push(out);
      fs.writeFileSync(outPath.replace(/\.json$/, `-frames-${label}${preset ? '-' + preset : ''}.json`), JSON.stringify(d));
      console.log('drag', label, preset || '', JSON.stringify({ fps: out.drawn_fps, raf: out.raf_interval_ms, in2gpu: out.input_to_gpu_done_ms, in2vsync: out.input_to_next_vsync_ms }));
    }
    await page.screenshot(outPath.replace(/\.json$/, '-screenshot.png'));
    result.bench_gpu_ms_per_frame = {
      canvas_2560x1600: await page.eval('window.__bench(60, 2560, 1600)'),
      canvas_3456x2234: await page.eval('window.__bench(60, 3456, 2234)'),
    };
    console.log('bench', JSON.stringify(result.bench_gpu_ms_per_frame));
    result.mem_after_drag = gpuProcessRss(chromePid);
    result.js_heap = await page.eval('performance.memory ? { used_mb: performance.memory.usedJSHeapSize / 1048576, total_mb: performance.memory.totalJSHeapSize / 1048576 } : null');
  }

  if (stages.has('readback')) {
    const photos = await page.eval(`(async () => (await (await fetch('/data/index.json')).json()).photos)()`);
    result.readback = [];
    for (const ph of photos) {
      for (const ps of sets) {
        if (ps.units && !ps.units.includes(ph.unit)) continue;
        for (const mode of stages.has('rawgpu') ? ['proxy', 'raw'] : ['proxy']) {
          const r = await page.eval(`window.__readback(${JSON.stringify(ph.name)}, ${JSON.stringify(ps)}, '${mode}')`);
          result.readback.push({ photo: ph.name, set: ps.id, mode, ...r });
        }
      }
    }
    console.log('readback', result.readback.length, 'images');
  }

  if (stages.has('export')) {
    const photos = await page.eval(`(async () => (await (await fetch('/data/index.json')).json()).photos)()`);
    result.export = [];
    const exportSets = sets.filter((s) => ['s1_recipe01', 's2_recipe02_tone', 's3_recipe04_curve_extra', 's5_lut_display'].includes(s.id));
    for (const ph of photos.filter((p) => ['R8051410', 'R8051691'].includes(p.name))) {
      for (const ps of exportSets) {
        const r = await page.eval(`window.__export(${JSON.stringify(ph.name)}, ${JSON.stringify(ps)})`, { timeoutMs: 120000 });
        result.export.push({ photo: ph.name, set: ps.id, ...r });
        console.log('export', ph.name, ps.id, JSON.stringify(r.ms));
      }
    }
    result.mem_after_export = gpuProcessRss(chromePid);
  }

  if (stages.has('hdr')) {
    result.hdr = await page.eval(`(async () => {
      const out = {};
      const c = document.createElement('canvas');
      const ctx = c.getContext('webgpu');
      const dev = window.__eng.device;
      for (const [name, cfg] of [['rgba16float-p3-extended', { format: 'rgba16float', colorSpace: 'display-p3', toneMapping: { mode: 'extended' } }], ['rgba16float-srgb-extended', { format: 'rgba16float', colorSpace: 'srgb', toneMapping: { mode: 'extended' } }], ['bgra8-p3', { format: 'bgra8unorm', colorSpace: 'display-p3' }]]) {
        try { ctx.configure({ device: dev, alphaMode: 'opaque', ...cfg }); const g = ctx.getConfiguration ? ctx.getConfiguration() : null; out[name] = g ? { format: g.format, colorSpace: g.colorSpace, toneMapping: g.toneMapping } : 'configured(no getConfiguration)'; } catch (e) { out[name] = 'error: ' + e.message; }
      }
      const c2 = document.createElement('canvas').getContext('2d', { colorSpace: 'display-p3' });
      out.canvas2d_p3 = c2 && c2.getContextAttributes ? c2.getContextAttributes() : null;
      try { const c3 = document.createElement('canvas').getContext('2d', { colorSpace: 'display-p3', colorType: 'float16' }); out.canvas2d_float16 = c3 ? c3.getContextAttributes() : null; } catch (e) { out.canvas2d_float16 = 'error: ' + e.message; }
      out.matchMedia = { p3: matchMedia('(color-gamut: p3)').matches, hdr: matchMedia('(dynamic-range: high)').matches };
      out.wgsl_features = navigator.gpu.wgslLanguageFeatures ? [...navigator.gpu.wgslLanguageFeatures] : null;
      return out;
    })()`);
    console.log('hdr', JSON.stringify(result.hdr));
  }
  if (stages.has('shot')) {
    const ps = { id: 'shot', recipe: 5, lut: null, adjust: { exposure_ev: 0.3, wb: { warm: 12, tint: 0 }, contrast: 18, highlight: -35, shadow: 25, vibrance: 15, vignette: -20 }, curve: [[0, 0], [64, 48], [128, 128], [192, 210], [255, 255]], straighten: 2.5, crop: [0.06, 0.08, 0.86, 0.84] };
    await page.eval(`window.__open('R8051707')`);
    await page.eval(`window.__applySet(${JSON.stringify(ps)})`);
    await page.eval(`window.__syncUi(${JSON.stringify(ps)})`);
    await pause(400);
    await page.screenshot(outPath.replace(/\.json$/, '.png'));
  }
  if (stages.has('smoke')) await page.screenshot(outPath.replace(/\.json$/, '-smoke.png'));
} finally {
  result.errors = errors;
  result.load_after = load();
  fs.writeFileSync(outPath, JSON.stringify(result, null, 1));
  await cdp.close();
}
if (errors.length) console.log('页面错误', errors.slice(0, 5));
