// 在现有工作室页面里调用真正的 gpu_stage.route()（与拖滑块时同一条路），读回成片纹理，发给本机接收器。
// 用法：node parity_page.mjs <工作室 URL> <令牌> <cdp.mjs 所在目录> <用户目录> <cases.json> <读回目录>
import fs from 'node:fs';
const [base, token, cdpDir, userDir, casesPath, port] = process.argv.slice(2);
const { launch } = await import(`${cdpDir}/cdp.mjs`);
const cases = JSON.parse(fs.readFileSync(casesPath, 'utf8'));
const cdp = await launch({ userDataDir: userDir, width: 1000, height: 700 });
try {
  const page = await cdp.page();
  await page.goto(`${base}/?token=${token}`);
  for (const c of cases) {
    const r = await page.eval(`(async () => {
      const gs = await import('/assets/gpu_stage.js');
      const c = ${JSON.stringify(c)};
      const geometry = { straighten: 0, vertical: 0, horizontal: 0, distortion: 0, rotate90: 0, flip: false, ...(c.geometry || {}) };
      const view = { photo: { id: c.photo, name: c.id }, stage: c.stage, ed: { v2: true, lut: c.lut || null, geometry, frame: { style: 'none' }, stamp: { enabled: false }, caps: { recipe: 'full' } } };
      const ctx = { stage: c.stage, recipe: c.recipe, adjust: c.adjust || {}, curve: c.curve || null, geometry, crop: c.crop || null, geometryKey: 'k' };
      let way = 'wait';
      for (let i = 0; i < 60 && way === 'wait'; i++) {
        way = await new Promise((res) => { const w = gs.route(view, ctx, () => res('wait')); if (w !== 'wait') res(w); });
      }
      if (way !== 'gpu') return { way };
      const e = gs.gpuEngineForTests();
      const t0 = performance.now();
      const rb = await e.readback();
      const ms = performance.now() - t0;
      window.__rb = rb.data;
      return { way, w: rb.w, h: rb.h, readback_ms: ms, label: view.ed.label, calibrated: view.ed.calibrated, full: view.gpuFull, adapter: e.info };
    })()`, { timeoutMs: 120000 });
    console.log(c.id, JSON.stringify(r));
    if (r.way !== 'gpu') continue;
    // 工作室页面的 CSP 只允许连自己：读回的字节分块用 base64 经 CDP 取回
    const total = await page.eval('window.__rb.length');
    const parts = [];
    for (let at = 0; at < total; at += 6 << 20) {
      const b64 = await page.eval(`new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(fr.result.split(',')[1]); fr.readAsDataURL(new Blob([window.__rb.subarray(${at}, ${at} + (6 << 20))])); })`, { timeoutMs: 60000 });
      parts.push(Buffer.from(b64, 'base64'));
    }
    fs.writeFileSync(`${port}/${c.id}__${r.w}x${r.h}.rgba`, Buffer.concat(parts));
  }
} finally {
  await cdp.close();
}
