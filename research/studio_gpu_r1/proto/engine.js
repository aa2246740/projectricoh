// WebGPU 预览引擎原型。数据只上传一次；拖滑块只改一小块 uniform 和 1021 点调子表，然后重画。
import { COLOR_PASS, GEO_PASS, BIN_PASS, EXPORT_PASS } from './shaders.wgsl.js';

// ---- render/tones.py 的 JS 版（调子表在浏览器里算，PCHIP 与 scipy.interpolate.PchipInterpolator 相同） ----
const WARM_EV = 0.35, TINT_EV = 0.25, SH_AMT = 0.13, TABLE_SIZE = 1021;
export function channelGains(a) {
  const ev = a.exposure_ev || 0, warm = (a.warm || 0) / 100, tint = (a.tint || 0) / 100;
  if (!ev && !warm && !tint) return null;
  return [2 ** (ev + WARM_EV * warm + TINT_EV * tint), 2 ** ev, 2 ** (ev - WARM_EV * warm + TINT_EV * tint)];
}
function toneFunction(t, a) {
  let y = t;
  if (a.contrast) { const k = a.contrast / 100; y = y + k * (y * y * (3 - 2 * y) - y); }
  if (a.highlight) y = y + (a.highlight / 100) * SH_AMT * 6.75 * y * y * (1 - y);
  if (a.shadow) y = y + (a.shadow / 100) * SH_AMT * 6.75 * y * (1 - y) ** 2;
  return Math.min(1, Math.max(0, y));
}
function pchip(xs, ys) {
  const n = xs.length, h = [], m = [];
  for (let k = 0; k < n - 1; k++) { h.push(xs[k + 1] - xs[k]); m.push((ys[k + 1] - ys[k]) / h[k]); }
  const d = new Array(n).fill(0);
  if (n === 2) { d[0] = d[1] = m[0]; }
  else {
    for (let k = 1; k < n - 1; k++) {
      if (m[k - 1] * m[k] <= 0) { d[k] = 0; continue; }
      const w1 = 2 * h[k] + h[k - 1], w2 = h[k] + 2 * h[k - 1];
      d[k] = (w1 + w2) / (w1 / m[k - 1] + w2 / m[k]);
    }
    const edge = (h0, h1, m0, m1) => {
      let dd = ((2 * h0 + h1) * m0 - h0 * m1) / (h0 + h1);
      if (Math.sign(dd) !== Math.sign(m0)) dd = 0;
      else if (Math.sign(m0) !== Math.sign(m1) && Math.abs(dd) > Math.abs(3 * m0)) dd = 3 * m0;
      return dd;
    };
    d[0] = edge(h[0], h[1], m[0], m[1]);
    d[n - 1] = edge(h[n - 2], h[n - 3], m[n - 2], m[n - 3]);
  }
  return (x) => {
    let k = 0;
    while (k < n - 2 && x > xs[k + 1]) k++;
    const t = (x - xs[k]) / h[k], t2 = t * t, t3 = t2 * t;
    return (2 * t3 - 3 * t2 + 1) * ys[k] + (t3 - 2 * t2 + t) * h[k] * d[k] + (-2 * t3 + 3 * t2) * ys[k + 1] + (t3 - t2) * h[k] * d[k + 1];
  };
}
export function displayTable(a, curve) {
  const toneId = !a.contrast && !a.highlight && !a.shadow;
  if (toneId && !curve) return null;
  const out = new Float32Array(TABLE_SIZE);
  const f = curve ? pchip(curve.map((p) => p[0]), curve.map((p) => p[1])) : null;
  for (let i = 0; i < TABLE_SIZE; i++) {
    const x = (255 * i) / (TABLE_SIZE - 1);
    let y = toneFunction(x / 255, a) * 255;
    if (f) y = Math.min(255, Math.max(0, f(Math.min(curve[curve.length - 1][0], Math.max(curve[0][0], y)))));
    out[i] = y;
  }
  return out;
}

// ---- lut/spaces.py matrix(gamut) ----
const PRIM = { rec709: [[.64, .33], [.30, .60], [.15, .06]], rec2020: [[.708, .292], [.170, .797], [.131, .046]] };
const GAMUT = { srgb: 'rec709', rec709: 'rec709', gamma24: 'rec709', linear: 'rec709', llog: 'rec2020' };
const SPACE_ID = { srgb: 0, rec709: 1, gamma24: 2, llog: 3, linear: 4 };
function inv3(m) {
  const [a, b, c] = m[0], [d, e, f] = m[1], [g, h, i] = m[2];
  const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g, det = a * A + b * B + c * C;
  return [[A / det, -(b * i - c * h) / det, (b * f - c * e) / det], [B / det, (a * i - c * g) / det, -(a * f - c * d) / det], [C / det, -(a * h - b * g) / det, (a * e - b * d) / det]];
}
const mul3 = (x, y) => x.map((r) => [0, 1, 2].map((j) => r[0] * y[0][j] + r[1] * y[1][j] + r[2] * y[2][j]));
function gamutMatrix(name) {
  const xy = PRIM[name];
  const X = [xy.map(([x, y]) => x / y), [1, 1, 1], xy.map(([x, y]) => (1 - x - y) / y)];
  const white = [0.3127 / 0.3290, 1, (1 - 0.3127 - 0.3290) / 0.3290];
  const Xi = inv3(X);
  const s = [0, 1, 2].map((r) => Xi[r][0] * white[0] + Xi[r][1] * white[1] + Xi[r][2] * white[2]);
  return X.map((row) => row.map((v, j) => v * s[j]));
}

const BYTES_PER_ROW_ALIGN = 256;

export class Engine {
  constructor() {
    this.photos = new Map(); // 名字 → 已上传的显卡资源（LRU）
    this.luts = new Map();
    this.maxPhotos = 8;
    this.params = { adjust: {}, curve: null, recipe: 1, lut: null, lutStrength: 1, straighten: 0, crop: null };
    this.dirtyColor = true;
    this.dirtyGeo = true;
    this.frameLog = [];
    this.inputs = [];
  }

  async init(canvas) {
    const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
    if (!adapter) throw new Error('没有 WebGPU 适配器');
    this.adapter = adapter;
    const info = adapter.info || {};
    this.info = { vendor: info.vendor, architecture: info.architecture, device: info.device, description: info.description, features: [...adapter.features], isFallback: info.isFallbackAdapter ?? adapter.isFallbackAdapter };
    this.device = await adapter.requestDevice({
      requiredLimits: { maxStorageBufferBindingSize: adapter.limits.maxStorageBufferBindingSize, maxBufferSize: adapter.limits.maxBufferSize },
    });
    const d = this.device;
    d.lost.then((e) => console.error('device lost', e.message));
    this.canvas = canvas;
    this.ctx = canvas.getContext('webgpu');
    this.format = navigator.gpu.getPreferredCanvasFormat();
    this.ctx.configure({ device: d, format: this.format, alphaMode: 'opaque' });

    const FC = GPUShaderStage.FRAGMENT | GPUShaderStage.COMPUTE;
    this.layout0 = d.createBindGroupLayout({ entries: [
      { binding: 0, visibility: FC, buffer: { type: 'uniform' } },
      { binding: 1, visibility: FC, buffer: { type: 'read-only-storage' } },
      { binding: 2, visibility: FC, buffer: { type: 'read-only-storage' } },
      { binding: 3, visibility: FC, texture: { sampleType: 'unfilterable-float', viewDimension: '3d' } },
    ] });
    this.layoutProxy = d.createBindGroupLayout({ entries: [{ binding: 0, visibility: GPUShaderStage.FRAGMENT, texture: { sampleType: 'unfilterable-float' } }] });
    this.layoutGeo = d.createBindGroupLayout({ entries: [
      { binding: 0, visibility: GPUShaderStage.FRAGMENT, buffer: { type: 'uniform' } },
      { binding: 1, visibility: GPUShaderStage.FRAGMENT, texture: { sampleType: 'unfilterable-float' } },
    ] });
    this.layoutBin = d.createBindGroupLayout({ entries: [
      { binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'uniform' } },
      { binding: 1, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'read-only-storage' } },
      { binding: 2, visibility: GPUShaderStage.COMPUTE, storageTexture: { access: 'write-only', format: 'rgba32float' } },
    ] });
    this.layoutExp = d.createBindGroupLayout({ entries: [
      { binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'uniform' } },
      { binding: 1, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'read-only-storage' } },
      { binding: 2, visibility: GPUShaderStage.COMPUTE, storageTexture: { access: 'write-only', format: 'rgba8unorm' } },
    ] });
    const t0 = performance.now();
    const mod = (code) => d.createShaderModule({ code });
    const colorMod = mod(COLOR_PASS), geoMod = mod(GEO_PASS), binMod = mod(BIN_PASS), expMod = mod(EXPORT_PASS);
    this.colorPipe = d.createRenderPipeline({
      layout: d.createPipelineLayout({ bindGroupLayouts: [this.layout0, this.layoutProxy] }),
      vertex: { module: colorMod, entryPoint: 'vs' }, fragment: { module: colorMod, entryPoint: 'fs', targets: [{ format: 'rgba8unorm' }] },
    });
    this.geoPipeCanvas = d.createRenderPipeline({
      layout: d.createPipelineLayout({ bindGroupLayouts: [this.layoutGeo] }),
      vertex: { module: geoMod, entryPoint: 'vs' }, fragment: { module: geoMod, entryPoint: 'fs', targets: [{ format: this.format }] },
    });
    this.geoPipeRead = d.createRenderPipeline({
      layout: d.createPipelineLayout({ bindGroupLayouts: [this.layoutGeo] }),
      vertex: { module: geoMod, entryPoint: 'vs' }, fragment: { module: geoMod, entryPoint: 'fs', targets: [{ format: 'rgba8unorm' }] },
    });
    this.binPipe = d.createComputePipeline({ layout: d.createPipelineLayout({ bindGroupLayouts: [this.layoutBin] }), compute: { module: binMod, entryPoint: 'main' } });
    this.expPipe = d.createComputePipeline({ layout: d.createPipelineLayout({ bindGroupLayouts: [this.layout0, this.layoutExp] }), compute: { module: expMod, entryPoint: 'main' } });
    await d.queue.onSubmittedWorkDone();
    this.pipelineMs = performance.now() - t0;
    for (const m of [colorMod, geoMod, binMod, expMod]) {
      const ci = await m.getCompilationInfo();
      for (const msg of ci.messages) if (msg.type === 'error') throw new Error(`WGSL: ${msg.message} @${msg.lineNum}`);
    }
    this.uniform = d.createBuffer({ size: 18 * 16, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
    this.geoUniform = d.createBuffer({ size: 4 * 16, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
    this.toneBuf = d.createBuffer({ size: TABLE_SIZE * 4, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST });
    this.dummyLut = d.createTexture({ size: [2, 2, 2], dimension: '3d', format: 'rgba32float', usage: GPUTextureUsage.TEXTURE_BINDING });
    this.bytes = { textures: 0, buffers: 0 };
    return this.info;
  }

  // ---- 数据 ----
  async fetchBin(url, retry = 2) {
    let r;
    try { r = await fetch(url); } catch (e) { if (retry > 0) return this.fetchBin(url, retry - 1); throw e; }
    if (!r.ok) throw new Error(`${url} ${r.status}`);
    return r.arrayBuffer();
  }

  recipeBuffer(bytes) {
    const b = this.device.createBuffer({ size: bytes.byteLength, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST });
    this.device.queue.writeBuffer(b, 0, bytes);
    this.bytes.buffers += bytes.byteLength;
    return b;
  }

  // mode: 'proxy' = 下载服务器做好的 float16 代理图；'raw' = 下载 DNG 字节，在显卡上拆包 + 2×2 合并
  async loadPhoto(name, mode = 'proxy') {
    const hit = this.photos.get(name);
    if (hit && hit.mode === mode) {
      this.photos.delete(name);
      this.photos.set(name, hit);
      return { cached: true, ms: {} };
    }
    const d = this.device;
    const ms = {};
    let t = performance.now();
    const meta = await (await fetch(`/data/${name}/meta.json`)).json();
    let scene = null;
    if (meta.unit === 'jlaunch') scene = await (await fetch(`/data/${name}/scene.json`)).json();
    const recFetch = Promise.all([1, 2, 3, 4, 5, 6, 7, 8].map((s) => this.fetchBin(`/data/${name}/rec_${s}_p.bin`)));
    const { w, h } = meta;
    const proxyTex = d.createTexture({ size: [w, h], format: mode === 'raw' ? 'rgba32float' : 'rgba16float', usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST | GPUTextureUsage.STORAGE_BINDING });
    if (mode === 'proxy') {
      const buf = await this.fetchBin(`/data/${name}/proxy.f16`);
      ms.fetch_proxy = performance.now() - t;
      t = performance.now();
      d.queue.writeTexture({ texture: proxyTex }, buf, { bytesPerRow: w * 8 }, [w, h]);
      await d.queue.onSubmittedWorkDone();
      ms.upload_proxy = performance.now() - t;
    } else {
      const raw = meta.raw;
      const file = await this.fetchBin(`/dng/${name}`);
      ms.fetch_dng = performance.now() - t;
      t = performance.now();
      const strip = file.slice(raw.strip_offsets[0], raw.strip_offsets[0] + raw.strip_bytes);
      const padded = new Uint8Array(Math.ceil(strip.byteLength / 4) * 4);
      padded.set(new Uint8Array(strip));
      const rawBuf = d.createBuffer({ size: padded.byteLength, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST });
      d.queue.writeBuffer(rawBuf, 0, padded);
      const u = new Float32Array(16);
      u.set([raw.crop[0], raw.crop[1], raw.crop[2], raw.crop[3]], 0);
      u.set(raw.wb_gains, 4);
      u.set([raw.row_bytes, raw.orientation], 8);
      u.set(raw.phase.flat(), 12);
      const ub = d.createBuffer({ size: 64, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
      d.queue.writeBuffer(ub, 0, u);
      const enc = d.createCommandEncoder();
      const pass = enc.beginComputePass();
      pass.setPipeline(this.binPipe);
      pass.setBindGroup(0, d.createBindGroup({ layout: this.layoutBin, entries: [{ binding: 0, resource: { buffer: ub } }, { binding: 1, resource: { buffer: rawBuf } }, { binding: 2, resource: proxyTex.createView() }] }));
      pass.dispatchWorkgroups(Math.ceil(w / 16), Math.ceil(h / 16));
      pass.end();
      d.queue.submit([enc.finish()]);
      await d.queue.onSubmittedWorkDone();
      ms.upload_and_bin_on_gpu = performance.now() - t;
      rawBuf.destroy();
      ub.destroy();
    }
    t = performance.now();
    const recs = await recFetch;
    ms.fetch_recipes_wait = performance.now() - t;
    const recipes = {};
    recs.forEach((b, i) => { recipes[i + 1] = this.recipeBuffer(b); });
    const colorTex = d.createTexture({ size: [w, h], format: 'rgba8unorm', usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_SRC });
    this.bytes.textures += w * h * (mode === 'raw' ? 16 : 8) + w * h * 4;
    const ph = { name, mode, meta, scene, proxyTex, colorTex, recipes, w, h };
    ph.proxyGroup = d.createBindGroup({ layout: this.layoutProxy, entries: [{ binding: 0, resource: proxyTex.createView() }] });
    ph.geoGroup = d.createBindGroup({ layout: this.layoutGeo, entries: [{ binding: 0, resource: { buffer: this.geoUniform } }, { binding: 1, resource: colorTex.createView() }] });
    this.photos.set(name, ph);
    while (this.photos.size > this.maxPhotos) {
      const [k, old] = this.photos.entries().next().value;
      this.photos.delete(k);
      old.proxyTex.destroy(); old.colorTex.destroy();
      Object.values(old.recipes).forEach((b) => b.destroy());
      this.bytes.textures -= old.w * old.h * 12;
    }
    return { cached: false, ms };
  }

  async loadLut(info) {
    if (this.luts.has(info.name)) return this.luts.get(info.name);
    const buf = await this.fetchBin(`/data/${info.file}`);
    const n = info.n;
    const tex = this.device.createTexture({ size: [n, n, n], dimension: '3d', format: 'rgba32float', usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST });
    this.device.queue.writeTexture({ texture: tex }, buf, { bytesPerRow: n * 16, rowsPerImage: n }, [n, n, n]);
    this.bytes.textures += buf.byteLength;
    const v = { info, tex };
    this.luts.set(info.name, v);
    return v;
  }

  show(name) {
    this.current = this.photos.get(name);
    this.dirtyColor = this.dirtyGeo = true;
  }

  set(changes) {
    const geoOnly = Object.keys(changes).every((k) => k === 'straighten' || k === 'crop');
    Object.assign(this.params, changes);
    if (!geoOnly) this.dirtyColor = true;
    this.dirtyGeo = true;
  }

  // ---- uniform ----
  writeUniform(ph, recipeInfo, lutV) {
    const p = this.params, a = p.adjust || {};
    const u = new Float32Array(18 * 4);
    const g = channelGains({ exposure_ev: a.exposure_ev, warm: a.wb?.warm, tint: a.wb?.tint }) || [1, 1, 1];
    u.set([...g, 0], 0);
    const table = displayTable(a, p.curve);
    if (table) this.device.queue.writeBuffer(this.toneBuf, 0, table);
    const lutMode = lutV ? (['srgb', 'rec709', 'gamma24'].includes(lutV.info.input_space) ? 1 : 2) : 0;
    const anyBase = !!(a.exposure_ev || a.wb?.warm || a.wb?.tint || table);
    u.set([table ? 1 : 0, lutMode, anyBase ? 1 : 0, p.lutStrength ?? 1], 4);
    u.set([a.black_point || 0, a.saturation || 0, a.vibrance || 0, a.vignette || 0], 8);
    u.set([ph.w, ph.h, 0, 0], 12);
    u.set([recipeInfo.origin[0], recipeInfo.origin[1], 1 / recipeInfo.step, recipeInfo.nx], 24);
    u.set([recipeInfo.ny, 0, 0, 0], 28);
    if (lutV) {
      const L = lutV.info;
      u.set([SPACE_ID[L.input_space], SPACE_ID[L.output_space], L.n, 0], 32);
      u.set([...L.domain_min, 0], 36);
      u.set([...L.domain_max, 0], 40);
      u.set([L.range3[0], L.range3[1], 0, 0], 44);
      const Min = inv3(gamutMatrix(GAMUT[L.input_space]));
      let M, off = [0, 0, 0];
      if (lutMode === 1) M = mul3(Min, gamutMatrix('rec709'));
      else {
        M = mul3(Min, ph.scene.A);
        off = [0, 1, 2].map((r) => Min[r][0] * ph.scene.b[0] + Min[r][1] * ph.scene.b[1] + Min[r][2] * ph.scene.b[2]);
      }
      for (let r = 0; r < 3; r++) u.set([...M[r], off[r]], 48 + r * 4);
      const O = mul3(inv3(gamutMatrix('rec709')), gamutMatrix(GAMUT[L.output_space]));
      for (let r = 0; r < 3; r++) u.set([...O[r], 0], 60 + r * 4);
    }
    this.device.queue.writeBuffer(this.uniform, 0, u);
  }

  cropRect(ph) {
    const c = this.params.crop;
    if (!c) return [0, 0, ph.w, ph.h];
    // finish/geometry.py crop_valid 的取整
    const x = Math.min(Math.max(0, Math.round(c[0] * ph.w)), ph.w - 1), y = Math.min(Math.max(0, Math.round(c[1] * ph.h)), ph.h - 1);
    const rw = Math.min(Math.max(1, Math.round(c[2] * ph.w)), ph.w - x), rh = Math.min(Math.max(1, Math.round(c[3] * ph.h)), ph.h - y);
    return [x, y, rw, rh];
  }

  writeGeo(ph, outW, outH, exact) {
    const [cx, cy, cw, chh] = this.cropRect(ph);
    const th = ((this.params.straighten || 0) * Math.PI) / 180;
    let scale = 1, ox = 0, oy = 0;
    if (!exact) {
      scale = Math.max(cw / outW, chh / outH);
      ox = (outW - cw / scale) / 2;
      oy = (outH - chh / scale) / 2;
    }
    this.device.queue.writeBuffer(this.geoUniform, 0, new Float32Array([ph.w, ph.h, outW, outH, Math.cos(th), Math.sin(th), th ? 1 : 0, scale, cx, cy, cw, chh, ox, oy, 0.11, 0]));
  }

  group0(ph, recipeBuf, lutV) {
    return this.device.createBindGroup({ layout: this.layout0, entries: [
      { binding: 0, resource: { buffer: this.uniform } },
      { binding: 1, resource: { buffer: recipeBuf } },
      { binding: 2, resource: { buffer: this.toneBuf } },
      { binding: 3, resource: (lutV ? lutV.tex : this.dummyLut).createView({ dimension: '3d' }) },
    ] });
  }

  encodeColor(enc, ph) {
    const p = this.params;
    const slot = p.recipe || 4;
    const lutV = p.lut ? this.luts.get(p.lut) : null;
    this.writeUniform(ph, ph.meta.recipes[`${slot}_p`], lutV);
    const pass = enc.beginRenderPass({ colorAttachments: [{ view: ph.colorTex.createView(), loadOp: 'clear', storeOp: 'store', clearValue: [0, 0, 0, 1] }] });
    pass.setPipeline(this.colorPipe);
    pass.setBindGroup(0, this.group0(ph, ph.recipes[slot], lutV));
    pass.setBindGroup(1, ph.proxyGroup);
    pass.draw(3);
    pass.end();
  }

  // 画一帧到画布；返回 CPU 编码耗时
  frame() {
    const ph = this.current;
    if (!ph || (!this.dirtyColor && !this.dirtyGeo)) return null;
    const t0 = performance.now();
    const c = this.canvas;
    const dpr = devicePixelRatio || 1;
    const W = Math.max(1, Math.round(c.clientWidth * dpr)), H = Math.max(1, Math.round(c.clientHeight * dpr));
    if (c.width !== W || c.height !== H) { c.width = W; c.height = H; }
    const enc = this.device.createCommandEncoder();
    const color = this.dirtyColor;
    if (this.dirtyColor) this.encodeColor(enc, ph);
    this.writeGeo(ph, W, H, false);
    const pass = enc.beginRenderPass({ colorAttachments: [{ view: this.ctx.getCurrentTexture().createView(), loadOp: 'clear', storeOp: 'store', clearValue: [0.11, 0.11, 0.11, 1] }] });
    pass.setPipeline(this.geoPipeCanvas);
    pass.setBindGroup(0, ph.geoGroup);
    pass.draw(3);
    pass.end();
    this.device.queue.submit([enc.finish()]);
    this.dirtyColor = this.dirtyGeo = false;
    return { cpu: performance.now() - t0, color, W, H };
  }

  // 读回：裁切后画面，缩放 1（与 Python 同分辨率），RGBA 字节
  async readback() {
    const ph = this.current;
    const [, , cw, chh] = this.cropRect(ph);
    const d = this.device;
    const tex = d.createTexture({ size: [cw, chh], format: 'rgba8unorm', usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC });
    const enc = d.createCommandEncoder();
    this.encodeColor(enc, ph);
    this.writeGeo(ph, cw, chh, true);
    const pass = enc.beginRenderPass({ colorAttachments: [{ view: tex.createView(), loadOp: 'clear', storeOp: 'store', clearValue: [0, 0, 0, 1] }] });
    pass.setPipeline(this.geoPipeRead);
    pass.setBindGroup(0, ph.geoGroup);
    pass.draw(3);
    pass.end();
    const out = await this.copyOut(enc, tex, cw, chh);
    tex.destroy();
    this.dirtyColor = this.dirtyGeo = true;
    return { w: cw, h: chh, data: out };
  }

  async copyOut(enc, tex, w, h) {
    const d = this.device;
    const bpr = Math.ceil((w * 4) / BYTES_PER_ROW_ALIGN) * BYTES_PER_ROW_ALIGN;
    const buf = d.createBuffer({ size: bpr * h, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
    enc.copyTextureToBuffer({ texture: tex }, { buffer: buf, bytesPerRow: bpr }, [w, h]);
    d.queue.submit([enc.finish()]);
    await buf.mapAsync(GPUMapMode.READ);
    const src = new Uint8Array(buf.getMappedRange());
    const out = new Uint8Array(w * h * 4);
    for (let y = 0; y < h; y++) out.set(src.subarray(y * bpr, y * bpr + w * 4), y * w * 4);
    buf.unmap();
    buf.destroy();
    return out;
  }

  // 显卡吞吐：同一帧（颜色 + 几何到画布大小的离屏目标）连续提交 n 次
  async benchGpu(n = 60, W = 2560, H = 1600) {
    const ph = this.current, d = this.device;
    const tex = d.createTexture({ size: [W, H], format: 'rgba8unorm', usage: GPUTextureUsage.RENDER_ATTACHMENT });
    await d.queue.onSubmittedWorkDone();
    const t0 = performance.now();
    for (let i = 0; i < n; i++) {
      const enc = d.createCommandEncoder();
      this.encodeColor(enc, ph);
      this.writeGeo(ph, W, H, false);
      const pass = enc.beginRenderPass({ colorAttachments: [{ view: tex.createView(), loadOp: 'clear', storeOp: 'store', clearValue: [0, 0, 0, 1] }] });
      pass.setPipeline(this.geoPipeRead);
      pass.setBindGroup(0, ph.geoGroup);
      pass.draw(3);
      pass.end();
      d.queue.submit([enc.finish()]);
    }
    await d.queue.onSubmittedWorkDone();
    const ms = (performance.now() - t0) / n;
    tex.destroy();
    this.dirtyColor = this.dirtyGeo = true;
    return ms;
  }

  // 全尺寸导出：DNG 字节 → 显卡拆包/去马赛克/颜色链 → 读回 → 浏览器编 JPEG
  async exportFull(name, quality = 0.95) {
    const d = this.device, ms = {};
    let t = performance.now();
    const meta = await (await fetch(`/data/${name}/meta.json`)).json();
    const raw = meta.raw;
    const slot = this.params.recipe || 4;
    const [file, recX] = await Promise.all([this.fetchBin(`/dng/${name}`), this.fetchBin(`/data/${name}/rec_${slot}_x.bin`)]);
    ms.fetch_dng_and_table = performance.now() - t;
    t = performance.now();
    const strip = new Uint8Array(file, raw.strip_offsets[0], raw.strip_bytes);
    const padded = new Uint8Array(Math.ceil(strip.byteLength / 4) * 4);
    padded.set(strip);
    const rawBuf = d.createBuffer({ size: padded.byteLength, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST });
    d.queue.writeBuffer(rawBuf, 0, padded);
    const recBuf = this.recipeBuffer(recX);
    const W = raw.crop[3], H = raw.crop[2];
    const ph = this.photos.get(name) || { w: W, h: H, scene: meta.unit === 'jlaunch' ? await (await fetch(`/data/${name}/scene.json`)).json() : null };
    const lutV = this.params.lut ? this.luts.get(this.params.lut) : null;
    this.writeUniform({ ...ph, w: W, h: H }, meta.recipes[`${slot}_x`], lutV);
    const u = new Float32Array(16);
    u.set(raw.crop, 0);
    u.set(raw.wb_gains.map((g) => g / 4095), 4);
    u.set([raw.row_bytes, raw.orientation], 8);
    u.set(raw.phase.flat(), 12);
    const ub = d.createBuffer({ size: 64, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
    d.queue.writeBuffer(ub, 0, u);
    const out = d.createTexture({ size: [W, H], format: 'rgba8unorm', usage: GPUTextureUsage.STORAGE_BINDING | GPUTextureUsage.COPY_SRC | GPUTextureUsage.TEXTURE_BINDING });
    await d.queue.onSubmittedWorkDone();
    ms.upload = performance.now() - t;
    t = performance.now();
    const enc = d.createCommandEncoder();
    const pass = enc.beginComputePass();
    pass.setPipeline(this.expPipe);
    pass.setBindGroup(0, this.group0(ph, recBuf, lutV));
    pass.setBindGroup(1, d.createBindGroup({ layout: this.layoutExp, entries: [{ binding: 0, resource: { buffer: ub } }, { binding: 1, resource: { buffer: rawBuf } }, { binding: 2, resource: out.createView() }] }));
    pass.dispatchWorkgroups(Math.ceil(W / 16), Math.ceil(H / 16));
    pass.end();
    d.queue.submit([enc.finish()]);
    await d.queue.onSubmittedWorkDone();
    ms.gpu_demosaic_and_colour = performance.now() - t;
    t = performance.now();
    const rgba = await this.copyOut(d.createCommandEncoder(), out, W, H);
    ms.readback = performance.now() - t;
    t = performance.now();
    const oc = new OffscreenCanvas(W, H);
    oc.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(rgba.buffer), W, H), 0, 0);
    const jpeg = await oc.convertToBlob({ type: 'image/jpeg', quality });
    ms.jpeg_encode = performance.now() - t;
    rawBuf.destroy(); recBuf.destroy(); ub.destroy(); out.destroy();
    this.dirtyColor = this.dirtyGeo = true;
    return { ms, w: W, h: H, rgba, jpegBytes: jpeg.size };
  }
}
