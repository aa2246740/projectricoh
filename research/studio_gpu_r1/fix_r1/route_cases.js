// 在工作室页面里调用真正的 gpu_stage.route()（与拖滑块同一条路），读回成片纹理交给本机接收器。
// 显示类 LUT 的精确表第一次要算几秒：这期间 route 返回 'server'（先用服务器出图），这里等到它切到显卡。
(async () => {
  const { state } = await import('/assets/state.js');
  for (let i = 0; i < 300 && !(state.settings && state.settings.gpu_preview); i++) await new Promise((r) => setTimeout(r, 100));
  const gs = await import('/assets/gpu_stage.js');
  const results = [];
  for (const c of window.__fixCases) {
    const geometry = { straighten: 0, vertical: 0, horizontal: 0, distortion: 0, rotate90: 0, flip: false, ...c.geometry };
    const view = { photo: { id: c.photo, name: c.id }, stage: c.stage, ed: { v2: true, lut: c.lut || null, geometry, frame: { style: 'none' }, stamp: { enabled: false }, caps: { recipe: 'full' } } };
    const ctx = { stage: c.stage, recipe: c.recipe, adjust: c.adjust || {}, curve: c.curve || null, geometry, crop: c.crop || null, geometryKey: 'fix' };
    let way = 'wait';
    const t0 = performance.now();
    const ways = [];
    for (let n = 0; n < 900 && way !== 'gpu'; n++) {
      way = await new Promise((resolve) => { const r = gs.route(view, ctx, () => resolve('wait')); if (r !== 'wait') resolve(r); });
      if (ways[ways.length - 1] !== way) ways.push(way);
      if (way === 'server') await new Promise((r) => setTimeout(r, 100));
    }
    if (way !== 'gpu') { results.push({ id: c.id, way, ways }); continue; }
    const engine = gs.gpuEngineForTests();
    const t = performance.now();
    const rb = await engine.readback();
    const sent = await fetch(`/__fix/readback/${c.id}?w=${rb.w}&h=${rb.h}&mode=${window.__fixMode}`, { method: 'POST', body: rb.data });
    if (!sent.ok) throw new Error('readback receipt failed ' + sent.status);
    results.push({ id: c.id, way, ways, toGpuMs: t - t0, readbackAndTransferMs: performance.now() - t, w: rb.w, h: rb.h, adapter: engine.info, label: view.ed.label, calibrated: view.ed.calibrated });
  }
  return results;
})()
