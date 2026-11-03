// 基线：现有工作室（不改它）在真实 Chrome 里拖动「曝光」滑块、切换照片的耗时。
// 用法：node baseline.mjs <studio 根 URL> <token> <输出 JSON> <scratch 用户目录> <照片 id,逗号分隔>
import fs from 'node:fs';
import { execSync } from 'node:child_process';
import { launch, pause, stats } from './cdp.mjs';

const [base, token, outPath, userDir, idsArg] = process.argv.slice(2);
const ids = idsArg.split(',');

const INSTRUMENT = `(() => {
  if (window.__m) return 'already';
  const m = window.__m = { inputs: [], reqs: [], imgs: [], waiters: [] };
  const of = window.fetch;
  window.fetch = async function (url, opts) {
    const u = String(url);
    const rec = { url: u, t0: performance.now(), body: opts && typeof opts.body === 'string' ? opts.body : null };
    if (u.includes('/render')) m.reqs.push(rec);
    try {
      const r = await of.apply(this, arguments);
      rec.tHead = performance.now(); rec.status = r.status;
      const ob = r.blob.bind(r);
      r.blob = async () => { const b = await ob(); rec.tBody = performance.now(); rec.size = b.size; rec.blob = b; return b; };
      return r;
    } catch (e) { rec.err = String(e && e.name); rec.tErr = performance.now(); throw e; }
  };
  const ocu = URL.createObjectURL.bind(URL);
  URL.createObjectURL = (b) => { const u = ocu(b); const rec = m.reqs.find((r) => r.blob === b); if (rec) { rec.blobUrl = u; delete rec.blob; } return u; };
  document.addEventListener('input', (e) => {
    if (e.target && e.target.type === 'range') m.inputs.push({ t: performance.now(), v: Number(e.target.value), label: e.target.getAttribute('aria-label') });
  }, true);
  const seen = new WeakSet();
  const watch = (img) => {
    if (seen.has(img)) return; seen.add(img);
    const rec = { src: img.src, tAdd: performance.now(), hash: location.hash };
    m.imgs.push(rec);
    const done = () => {
      rec.tLoad = performance.now();
      rec.w = img.naturalWidth; rec.h = img.naturalHeight;
      img.decode().catch(() => {}).then(() => {
        rec.tDecoded = performance.now();
        requestAnimationFrame(() => requestAnimationFrame((t2) => {
          rec.tPresent = performance.now();
          for (const w of [...m.waiters]) if (w.pred(rec)) { m.waiters.splice(m.waiters.indexOf(w), 1); w.resolve(rec); }
        }));
      });
    };
    if (img.complete && img.naturalWidth) done(); else img.addEventListener('load', done, { once: true });
  };
  new MutationObserver((muts) => {
    for (const mu of muts) for (const n of mu.addedNodes) {
      if (n.nodeType !== 1) continue;
      if (n.matches && n.matches('img.pv-img')) watch(n);
      if (n.querySelectorAll) n.querySelectorAll('img.pv-img').forEach(watch);
    }
  }).observe(document.body, { childList: true, subtree: true });
  window.__waitImg = (predSrc, timeoutMs) => new Promise((resolve, reject) => {
    const pred = new Function('rec', 'm', predSrc);
    const hit = m.imgs.find((r) => r.tPresent && pred(r, m));
    if (hit) return resolve(hit);
    const w = { pred: (r) => pred(r, m), resolve };
    m.waiters.push(w);
    setTimeout(() => { const i = m.waiters.indexOf(w); if (i >= 0) { m.waiters.splice(i, 1); reject(new Error('img timeout')); } }, timeoutMs);
  });
  return 'ok';
})()`;

function cpuSnapshot() {
  try {
    const top = execSync('top -l 2 -n 8 -s 1 -o cpu -stats pid,command,cpu', { encoding: 'utf8', timeout: 15000 });
    const parts = top.split(/Processes:/);
    const last = 'Processes:' + parts[parts.length - 1];
    return { uptime: execSync('uptime', { encoding: 'utf8' }).trim(), top: last.split('\n').slice(0, 22).join('\n') };
  } catch (e) {
    return { error: String(e) };
  }
}

const result = { when: new Date().toISOString(), base, photos: ids, cpuBefore: cpuSnapshot(), runs: [] };
const cdp = await launch({ userDataDir: userDir, width: 1440, height: 900 });
let page;
try {
  page = await cdp.page();
  const ver = await cdp.send('Browser.getVersion');
  result.browser = ver.product;
  await page.goto(`${base}/?token=${token}`);
  result.gpu = await page.eval(`(() => { const gl = document.createElement('canvas').getContext('webgl2'); const e = gl.getExtension('WEBGL_debug_renderer_info'); return { vendor: gl.getParameter(e.UNMASKED_VENDOR_WEBGL), renderer: gl.getParameter(e.UNMASKED_RENDERER_WEBGL), dpr: devicePixelRatio, screen: [screen.width, screen.height] }; })()`);
  console.log('GPU', JSON.stringify(result.gpu));
  await page.eval(INSTRUMENT);

  async function openPhoto(id, label) {
    const t = await page.eval(`(() => { const t = performance.now(); location.hash = '#/photo/${id}'; return t; })()`);
    const rec = await page.eval(`window.__waitImg("return rec.hash === '#/photo/${id}' && rec.tAdd >= ${t} && rec.src.startsWith('blob:')", 120000)`, { timeoutMs: 130000 });
    const req = await page.eval(`(() => { const r = __m.reqs.find((q) => q.blobUrl === ${JSON.stringify(rec.src)}); return r ? { url: r.url, t0: r.t0, tHead: r.tHead, tBody: r.tBody, size: r.size } : null; })()`);
    const out = { kind: 'open', label, id, t0: t, first_present_ms: rec.tPresent - t, load_ms: rec.tLoad - t, decode_ms: rec.tDecoded - rec.tLoad, w: rec.w, h: rec.h, req };
    console.log(label, id, Math.round(out.first_present_ms), 'ms', rec.w, 'x', rec.h);
    return out;
  }

  async function sliderRect(label) {
    return page.eval(`(() => { const el = [...document.querySelectorAll('input[type=range]')].find((x) => x.getAttribute('aria-label') === ${JSON.stringify(label)}); if (!el) return null; el.scrollIntoView({ block: 'center' }); const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height, min: +el.min, max: +el.max, v: +el.value }; })()`);
  }

  async function drag(label, seconds = 4, hz = 60) {
    const r = await sliderRect(label);
    if (!r) throw new Error('找不到滑块 ' + label);
    const y = r.y + r.h / 2;
    const x0 = r.x + ((r.v - r.min) / (r.max - r.min)) * r.w;
    const amp = r.w * 0.3;
    const n = Math.round(seconds * hz);
    const tStart = await page.eval('performance.now()');
    await page.mouse('mousePressed', x0, y, 1, 'left');
    const wall0 = Date.now();
    for (let i = 1; i <= n; i++) {
      const phase = i / n; // 0→1：右 → 左 → 回中
      const x = x0 + amp * Math.sin(phase * 2 * Math.PI);
      await page.mouse('mouseMoved', x, y, 1, 'left');
      const due = wall0 + (i * 1000) / hz;
      const wait = due - Date.now();
      if (wait > 0) await pause(wait);
    }
    await page.mouse('mouseReleased', x0, y, 0, 'left');
    const tRelease = await page.eval('performance.now()');
    // 松手后等工作室发出的清晰版（size=full 或 stage 渲染）出现
    let settle = null;
    try {
      const rec = await page.eval(`window.__waitImg("const q = m.reqs.find((x) => x.blobUrl === rec.src); return q && q.t0 >= ${tRelease} - 5;", 120000)`, { timeoutMs: 130000 });
      settle = rec.tPresent - tRelease;
    } catch (e) { settle = null; }
    const data = await page.eval(`(() => {
      const ins = __m.inputs.filter((i) => i.t >= ${tStart} && i.t <= ${tRelease} + 5);
      const imgs = __m.imgs.filter((r) => r.tPresent && r.tAdd >= ${tStart}).map((r) => { const q = __m.reqs.find((x) => x.blobUrl === r.src); return { tPresent: r.tPresent, tLoad: r.tLoad, w: r.w, h: r.h, reqT0: q ? q.t0 : null, url: q ? q.url : null, size: q ? q.size : null, tHead: q ? q.tHead : null }; });
      const reqs = __m.reqs.filter((q) => q.t0 >= ${tStart}).map((q) => ({ url: q.url, t0: q.t0, tHead: q.tHead, tBody: q.tBody, err: q.err || null, size: q.size || null }));
      return { ins, imgs, reqs };
    })()`);
    // 每个输入：第一张「请求在这个输入之后才发出」的画面出现的时刻
    const lat = [];
    const shown = data.imgs.filter((i) => i.reqT0 != null).sort((a, b) => a.tPresent - b.tPresent);
    for (const inp of data.ins) {
      const f = shown.find((s) => s.reqT0 >= inp.t);
      if (f) lat.push(f.tPresent - inp.t);
    }
    const during = shown.filter((s) => s.tPresent <= tRelease);
    const out = {
      kind: 'drag', label, seconds, inputs: data.ins.length, requests: data.reqs.length,
      aborted: data.reqs.filter((q) => q.err === 'AbortError').length,
      frames_shown_during_drag: during.length,
      frames_per_second_during_drag: +(during.length / ((tRelease - tStart) / 1000)).toFixed(2),
      input_to_new_frame_ms: stats(lat),
      inputs_never_shown_before_release: data.ins.filter((inp) => !during.find((s) => s.reqT0 >= inp.t)).length,
      release_to_sharp_frame_ms: settle,
      server_ms: stats(data.reqs.filter((q) => q.tHead).map((q) => q.tHead - q.t0)),
      image_sizes: [...new Set(data.imgs.map((i) => `${i.w}x${i.h}`))],
      raw: data,
    };
    console.log('drag', label, JSON.stringify({ fps: out.frames_per_second_during_drag, lat: out.input_to_new_frame_ms, settle, reqs: out.requests, aborted: out.aborted }));
    return out;
  }

  async function clickTab(name) {
    await page.eval(`(() => { const b = [...document.querySelectorAll('button[role=tab]')].find((x) => x.textContent.trim() === ${JSON.stringify(name)}); if (b) b.click(); return !!b; })()`);
    await pause(300);
  }

  // 1) 冷打开第一张，切到「调整」
  result.runs.push(await openPhoto(ids[0], 'cold-open'));
  await clickTab('调整');
  await pause(1500);
  // 2) 拖动曝光（两轮）
  result.runs.push(await drag('曝光', 4));
  await pause(1000);
  result.runs.push(await drag('曝光', 4));
  await pause(1000);
  await page.screenshot(`${outPath.replace(/\.json$/, '')}-adjust.png`);
  // 3) 切换照片：冷（第一次看）和热（第二次看）
  for (const id of ids.slice(1)) result.runs.push(await openPhoto(id, 'switch-cold'));
  for (const id of ids) result.runs.push(await openPhoto(id, 'switch-warm'));
  result.cpuAfter = cpuSnapshot();
  // 4) 页面内存
  result.memory = await page.eval(`(() => ({ jsHeapUsed: performance.memory ? performance.memory.usedJSHeapSize : null }))()`);
} finally {
  // 清掉 drag 原始数据里的大对象后再写
  fs.writeFileSync(outPath, JSON.stringify(result, null, 1));
  await cdp.close();
}
const sw = (k) => stats(result.runs.filter((r) => r.label === k).map((r) => r.first_present_ms));
console.log('switch-cold', JSON.stringify(sw('switch-cold')), 'switch-warm', JSON.stringify(sw('switch-warm')));
