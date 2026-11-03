// WebGL2 退路：同一套逐像素算法写成 GLSL ES 3.00（片元着色器），接口与 engine.js 相同，供同一个页面和测量脚本使用。
// 没有计算着色器：只做「服务器下发的 float16 代理」这条路；配方表放进 R32F 纹理，用 texelFetch 读，取整与 WGSL 版一致。
import { Engine } from './engine.js';

const VS = `#version 300 es
void main() { vec2 xy = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2)); gl_Position = vec4(xy * 2.0 - 1.0, 0.0, 1.0); }`;

const COLOR_FS = `#version 300 es
precision highp float; precision highp int; precision highp sampler2D; precision highp sampler3D;
uniform vec4 P[18];
uniform sampler2D recT; uniform sampler2D toneT; uniform sampler3D lutT; uniform sampler2D proxyT;
out vec4 outColor;
float rec(int i) { return texelFetch(recT, ivec2(i & 4095, i >> 12), 0).r; }
float tone(int i) { return texelFetch(toneT, ivec2(i, 0), 0).r; }
vec3 q8(vec3 v) { return floor(clamp(v, 0.0, 255.0) + 0.5); }
vec3 applyTable(vec3 v) {
  vec3 o;
  for (int c = 0; c < 3; c++) { float pos = clamp(v[c], 0.0, 255.0) * 4.0; int i = min(int(pos), 1019); float f = pos - float(i); float lo = tone(i); o[c] = lo + (tone(i + 1) - lo) * f; }
  return o;
}
vec3 recipeChain(vec3 codesIn, vec3 gains, bool useTable) {
  vec3 x = clamp(codesIn * gains, 0.0, 4095.0);
  vec3 pc;
  for (int c = 0; c < 3; c++) { int i = min(int(x[c]), 4094); float v0 = rec(i * 3 + c); pc[c] = v0 + (rec((i + 1) * 3 + c) - v0) * (x[c] - float(i)); }
  float y  = rec(12288) * pc.x + rec(12289) * pc.y + rec(12290) * pc.z + rec(12297);
  float cb = rec(12291) * pc.x + rec(12292) * pc.y + rec(12293) * pc.z + rec(12298);
  float cr = rec(12294) * pc.x + rec(12295) * pc.y + rec(12296) * pc.z + rec(12299);
  int nx = int(P[6].w); int ny = int(P[7].x);
  float u = (cb - P[6].x) * P[6].z; float v = (cr - P[6].y) * P[6].z;
  int iu = clamp(int(clamp(u, -1e6, 1e6)), 0, nx - 2); int iv = clamp(int(clamp(v, -1e6, 1e6)), 0, ny - 2);
  float fu = u - float(iu); float fv = v - float(iv);
  int at = iv * nx + iu; int G = 12300;
  vec2 a00 = vec2(rec(G + at * 2), rec(G + at * 2 + 1));
  vec2 a01 = vec2(rec(G + (at + 1) * 2), rec(G + (at + 1) * 2 + 1));
  vec2 a10 = vec2(rec(G + (at + nx) * 2), rec(G + (at + nx) * 2 + 1));
  vec2 a11 = vec2(rec(G + (at + nx + 1) * 2), rec(G + (at + nx + 1) * 2 + 1));
  vec2 gg = (a00 * (1.0 - fu) + a01 * fu) * (1.0 - fv) + (a10 * (1.0 - fu) + a11 * fu) * fv;
  float cbo = cb * gg.x - cr * gg.y; float cro = cb * gg.y + cr * gg.x;
  vec3 rgb = clamp(vec3(y + 1.402 * cro, y - 0.344136 * cbo - 0.714136 * cro, y + 1.772 * cbo), 0.0, 255.0);
  if (useTable) rgb = applyTable(rgb);
  return q8(rgb);
}
float log10f(float x) { return log2(max(x, 1e-30)) * 0.30102999566; }
float enc1(float x, int s) {
  if (s == 0) { if (x <= 0.0031308) return 12.92 * x; return 1.055 * pow(max(x, 0.0), 1.0 / 2.4) - 0.055; }
  if (s == 1) { if (x < 0.018) return 4.5 * x; return 1.099 * pow(max(x, 0.0), 0.45) - 0.099; }
  if (s == 2) return sign(x) * pow(abs(x), 1.0 / 2.4);
  if (s == 3) { if (x <= 0.006) return 8.0 * x + 0.09; return 0.27 * log10f(1.3 * x + 0.0115) + 0.6; }
  return x;
}
float dec1(float x, int s) {
  if (s == 0) { if (x <= 0.04045) return x / 12.92; return pow(max((x + 0.055) / 1.055, 0.0), 2.4); }
  if (s == 1) { if (x < 0.081) return x / 4.5; return pow(max((x + 0.099) / 1.099, 0.0), 1.0 / 0.45); }
  if (s == 2) return sign(x) * pow(abs(x), 2.4);
  if (s == 3) { if (x <= 0.1380) return (x - 0.09) / 8.0; return (pow(10.0, (x - 0.6) / 0.27) - 0.0115) / 1.3; }
  return x;
}
vec3 enc3(vec3 v, int s) { return vec3(enc1(v.x, s), enc1(v.y, s), enc1(v.z, s)); }
vec3 dec3(vec3 v, int s) { return vec3(dec1(v.x, s), dec1(v.y, s), dec1(v.z, s)); }
vec3 mat3x(vec3 v, vec4 a, vec4 b, vec4 c) { return vec3(dot(a.xyz, v) + a.w, dot(b.xyz, v) + b.w, dot(c.xyz, v) + c.w); }
vec3 lutAt(ivec3 c) { return texelFetch(lutT, c, 0).xyz; }
vec3 tetra(vec3 x) {
  int n = int(P[8].z); vec3 pos = x * float(n - 1);
  ivec3 base = min(ivec3(pos), ivec3(n - 2)); vec3 f = pos - vec3(base);
  int o0 = 0; int o1 = 1; int o2 = 2; int t;
  if (f[o1] > f[o0]) { t = o0; o0 = o1; o1 = t; }
  if (f[o2] > f[o1]) { t = o1; o1 = o2; o2 = t; }
  if (f[o1] > f[o0]) { t = o0; o0 = o1; o1 = t; }
  ivec3 b = base; vec3 v0 = lutAt(b);
  b[o0] += 1; vec3 v1 = lutAt(b);
  b[o1] += 1; vec3 v2 = lutAt(b);
  b[o2] += 1; vec3 v3 = lutAt(b);
  return v0 + f[o0] * (v1 - v0) + f[o1] * (v2 - v1) + f[o2] * (v3 - v2);
}
vec3 lutRender(vec3 lin_in) {
  vec3 x = enc3(lin_in, int(P[8].x));
  if (P[8].w > 0.5) x = (64.0 + 876.0 * x) / 1023.0;
  x = (x - P[9].xyz) / (P[10].xyz - P[9].xyz);
  x = (x - vec3(P[11].x)) / (P[11].y - P[11].x);
  vec3 o = tetra(clamp(x, 0.0, 1.0));
  vec3 srgb = enc3(mat3x(dec3(o, int(P[8].y)), P[15], P[16], P[17]), 0);
  return clamp(srgb, 0.0, 1.0) * 255.0;
}
vec3 srgbToLin(vec3 u) { vec3 x = u / 255.0; return mix(pow((x + 0.055) / 1.055, vec3(2.4)), x / 12.92, lessThanEqual(x, vec3(0.04045))); }
vec3 applyBase(vec3 u) {
  vec3 x = max(srgbToLin(u) * P[0].xyz, 0.0);
  vec3 e = mix(1.055 * pow(x, vec3(1.0 / 2.4)) - 0.055, x * 12.92, lessThanEqual(x, vec3(0.0031308)));
  vec3 o = floor(clamp(e * 255.0 + 0.5, 0.0, 255.0));
  if (P[1].x > 0.5) o = floor(clamp(applyTable(o) + 0.5, 0.0, 255.0));
  return o;
}
vec3 applyExtra(vec3 u, vec2 pix, vec2 wh) {
  float bp = P[2].x;
  if (bp != 0.0) { vec3 y = u / 255.0; float k = abs(bp) / 100.0 * 0.35; if (bp > 0.0) y = clamp((y - k) / max(1e-4, 1.0 - k), 0.0, 1.0); else y = y * (1.0 - k) + k; u = floor(clamp(y * 255.0 + 0.5, 0.0, 255.0)); }
  float sat = P[2].y;
  if (sat != 0.0) { float gray = u.x * 0.2126 + u.y * 0.7152 + u.z * 0.0722; u = floor(clamp(gray + (u - gray) * (1.0 + sat / 100.0) + 0.5, 0.0, 255.0)); }
  float vib = P[2].z;
  if (vib != 0.0) { float gray = u.x * 0.2126 + u.y * 0.7152 + u.z * 0.0722; float dull = 1.0 - clamp((max(u.x, max(u.y, u.z)) - min(u.x, min(u.y, u.z))) / 255.0, 0.0, 1.0); u = floor(clamp(gray + (u - gray) * (1.0 + vib / 100.0 * dull) + 0.5, 0.0, 255.0)); }
  float vig = P[2].w;
  if (vig != 0.0) { float hx = max((wh.x - 1.0) / 2.0, 1.0); float hy = max((wh.y - 1.0) / 2.0, 1.0); float r = clamp(length(vec2((pix.x - (wh.x - 1.0) / 2.0) / hx, (pix.y - (wh.y - 1.0) / 2.0) / hy)), 0.0, 1.0); float g = 1.0 + vig / 100.0 * 0.65 * (r * r * (3.0 - 2.0 * r)); u = floor(clamp(u * g + 0.5, 0.0, 255.0)); }
  return u;
}
void main() {
  ivec2 pix = ivec2(gl_FragCoord.xy);
  vec3 codes = texelFetch(proxyT, pix, 0).xyz;
  int mode = int(P[1].y);
  vec3 u;
  if (mode == 0) u = recipeChain(codes, P[0].xyz, P[1].x > 0.5);
  else {
    vec3 base; vec3 lin_in;
    if (mode == 1) { base = recipeChain(codes, vec3(1.0), false); lin_in = mat3x(srgbToLin(base), P[12], P[13], P[14]); }
    else { base = q8(enc3(clamp(codes / 4095.0, 0.0, 1.0), 0) * 255.0); lin_in = mat3x(codes, P[12], P[13], P[14]); }
    u = q8(mix(base, lutRender(lin_in), P[1].w));
    if (P[1].z > 0.5) u = applyBase(u);
  }
  u = applyExtra(u, vec2(pix), P[3].xy);
  outColor = vec4(u / 255.0, 1.0);
}`;

const GEO_FS = `#version 300 es
precision highp float; precision highp int; precision highp sampler2D;
uniform vec4 G[4]; uniform sampler2D colorT; uniform float flipY;
out vec4 outColor;
vec3 texel(int x, int y) { return texelFetch(colorT, ivec2(x, y), 0).xyz * 255.0; }
void main() {
  float W = G[0].x; float H = G[0].y;
  vec2 fc = gl_FragCoord.xy; if (flipY > 0.5) fc.y = G[0].w - fc.y;
  vec2 o = (fc - 0.5 - G[3].xy) * G[1].w;
  if (o.x < -0.5 || o.y < -0.5 || o.x > G[2].z - 0.5 || o.y > G[2].w - 0.5) { outColor = vec4(vec3(G[3].z), 1.0); return; }
  float X = G[2].x + o.x; float Y = G[2].y + o.y;
  float dx = X - (W - 1.0) / 2.0; float dy = Y - (H - 1.0) / 2.0;
  float sx = G[1].x * dx + G[1].y * dy + (W - 1.0) / 2.0; float sy = -G[1].y * dx + G[1].x * dy + (H - 1.0) / 2.0;
  if (!(sx >= -1e-3 && sy >= -1e-3 && sx <= W - 1.0 + 1e-3 && sy <= H - 1.0 + 1e-3)) { outColor = vec4(vec3(27.0, 28.0, 31.0) / 255.0, 1.0); return; }
  float fx = floor(sx); float fy = floor(sy);
  int x0 = clamp(int(fx), 0, int(W) - 1); int y0 = clamp(int(fy), 0, int(H) - 1);
  int x1 = min(x0 + 1, int(W) - 1); int y1 = min(y0 + 1, int(H) - 1);
  float tx = sx - fx; float ty = sy - fy;
  vec3 s = texel(x0, y0) * ((1.0 - tx) * (1.0 - ty)) + texel(x1, y0) * (tx * (1.0 - ty)) + texel(x0, y1) * ((1.0 - tx) * ty) + texel(x1, y1) * (tx * ty);
  outColor = vec4(floor(clamp(s + 0.5, 0.0, 255.0)) / 255.0, 1.0);
}`;

function compile(gl, fs) {
  const p = gl.createProgram();
  for (const [type, src] of [[gl.VERTEX_SHADER, VS], [gl.FRAGMENT_SHADER, fs]]) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error('GLSL: ' + gl.getShaderInfoLog(s));
    gl.attachShader(p, s);
  }
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error('link: ' + gl.getProgramInfoLog(p));
  return p;
}

export class EngineGL extends Engine {
  async init(canvas) {
    const gl = canvas.getContext('webgl2', { antialias: false, alpha: false, preserveDrawingBuffer: false });
    if (!gl) throw new Error('没有 WebGL2');
    this.gl = gl;
    this.canvas = canvas;
    const t0 = performance.now();
    this.pColor = compile(gl, COLOR_FS);
    this.pGeo = compile(gl, GEO_FS);
    this.pipelineMs = performance.now() - t0;
    this.format = 'webgl2-rgba8';
    const e = gl.getExtension('WEBGL_debug_renderer_info');
    this.info = { vendor: 'webgl2', architecture: e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : '', description: 'WebGL2 fallback' };
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    this.fences = [];
    // 让页面里的 onSubmittedWorkDone 照常用：等最近一次提交的 fence 完成
    this.device = { queue: { onSubmittedWorkDone: () => this.waitFence() } };
    this.toneTex = this.tex2d(gl.R32F, 1021, 1, gl.RED, gl.FLOAT, new Float32Array(1021));
    this.dummyLutTex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_3D, this.dummyLutTex);
    gl.texImage3D(gl.TEXTURE_3D, 0, gl.RGBA32F, 2, 2, 2, 0, gl.RGBA, gl.FLOAT, new Float32Array(32));
    this.nearest(gl.TEXTURE_3D);
    this.bytes = { textures: 0, buffers: 0 };
    return this.info;
  }

  nearest(target) {
    const gl = this.gl;
    gl.texParameteri(target, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(target, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(target, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(target, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  }

  tex2d(internal, w, h, format, type, data) {
    const gl = this.gl;
    const t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texImage2D(gl.TEXTURE_2D, 0, internal, w, h, 0, format, type, data);
    this.nearest(gl.TEXTURE_2D);
    return t;
  }

  waitFence() {
    const gl = this.gl;
    const f = this.lastFence;
    if (!f) return Promise.resolve();
    return new Promise((res) => {
      const check = () => {
        const s = gl.clientWaitSync(f, 0, 0);
        if (s === gl.ALREADY_SIGNALED || s === gl.CONDITION_SATISFIED) res();
        else setTimeout(check, 0);
      };
      check();
    });
  }

  fence() {
    const gl = this.gl;
    if (this.lastFence) gl.deleteSync(this.lastFence);
    this.lastFence = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
    gl.flush();
  }

  recipeTex(buf) {
    const f = new Float32Array(buf);
    const rows = Math.ceil(f.length / 4096);
    const padded = new Float32Array(rows * 4096);
    padded.set(f);
    return this.tex2d(this.gl.R32F, 4096, rows, this.gl.RED, this.gl.FLOAT, padded);
  }

  async loadPhoto(name, mode = 'proxy') {
    const hit = this.photos.get(name);
    if (hit) { this.photos.delete(name); this.photos.set(name, hit); return { cached: true, ms: {} }; }
    const gl = this.gl, ms = {};
    let t = performance.now();
    const meta = await (await fetch(`/data/${name}/meta.json`)).json();
    const scene = meta.unit === 'jlaunch' ? await (await fetch(`/data/${name}/scene.json`)).json() : null;
    const [buf, ...recs] = await Promise.all([this.fetchBin(`/data/${name}/proxy.f16`), ...[1, 2, 3, 4, 5, 6, 7, 8].map((s) => this.fetchBin(`/data/${name}/rec_${s}_p.bin`))]);
    ms.fetch = performance.now() - t;
    t = performance.now();
    const { w, h } = meta;
    const proxyTex = this.tex2d(gl.RGBA16F, w, h, gl.RGBA, gl.HALF_FLOAT, new Uint16Array(buf));
    const recipes = {};
    recs.forEach((b, i) => { recipes[i + 1] = this.recipeTex(b); });
    const colorTex = this.tex2d(gl.RGBA8, w, h, gl.RGBA, gl.UNSIGNED_BYTE, null);
    const fbo = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, colorTex, 0);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    this.fence();
    await this.waitFence();
    ms.upload = performance.now() - t;
    const ph = { name, mode: 'proxy', meta, scene, w, h, recipes, colorTex, fbo, proxyTex: { destroy: () => gl.deleteTexture(proxyTex) }, proxyGL: proxyTex };
    ph.colorTex = { destroy: () => gl.deleteTexture(colorTex), gl: colorTex };
    this.photos.set(name, ph);
    while (this.photos.size > this.maxPhotos) {
      const [k, old] = this.photos.entries().next().value;
      this.photos.delete(k);
      old.proxyTex.destroy(); old.colorTex.destroy();
      Object.values(old.recipes).forEach((x) => gl.deleteTexture(x));
    }
    return { cached: false, ms };
  }

  async loadLut(info) {
    if (this.luts.has(info.name)) return this.luts.get(info.name);
    const gl = this.gl;
    const buf = await this.fetchBin(`/data/${info.file}`);
    const t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_3D, t);
    gl.texImage3D(gl.TEXTURE_3D, 0, gl.RGBA32F, info.n, info.n, info.n, 0, gl.RGBA, gl.FLOAT, new Float32Array(buf));
    this.nearest(gl.TEXTURE_3D);
    const v = { info, tex: t };
    this.luts.set(info.name, v);
    return v;
  }

  // 借用 WebGPU 版的 uniform 打包，截下数组再交给 GL
  packColor(ph, recipeInfo, lutV) {
    const cap = {};
    const real = { device: this.device, uniform: this.uniform, toneBuf: this.toneBuf };
    this.device = { queue: { writeBuffer: (b, o, arr) => { cap[b] = arr; } } };
    this.uniform = 'u';
    this.toneBuf = 't';
    Engine.prototype.writeUniform.call(this, ph, recipeInfo, lutV);
    Object.assign(this, real);
    return cap;
  }

  drawColor(ph) {
    const gl = this.gl, p = this.params;
    const slot = p.recipe || 4;
    const lutV = p.lut ? this.luts.get(p.lut) : null;
    const cap = this.packColor(ph, ph.meta.recipes[`${slot}_p`], lutV);
    if (cap.t) { gl.bindTexture(gl.TEXTURE_2D, this.toneTex); gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, 1021, 1, gl.RED, gl.FLOAT, cap.t); }
    gl.useProgram(this.pColor);
    gl.uniform4fv(gl.getUniformLocation(this.pColor, 'P'), cap.u);
    const bind = (unit, target, tex, name) => { gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(target, tex); gl.uniform1i(gl.getUniformLocation(this.pColor, name), unit); };
    bind(0, gl.TEXTURE_2D, ph.recipes[slot], 'recT');
    bind(1, gl.TEXTURE_2D, this.toneTex, 'toneT');
    bind(2, gl.TEXTURE_3D, lutV ? lutV.tex : this.dummyLutTex, 'lutT');
    bind(3, gl.TEXTURE_2D, ph.proxyGL, 'proxyT');
    gl.bindFramebuffer(gl.FRAMEBUFFER, ph.fbo);
    gl.viewport(0, 0, ph.w, ph.h);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  drawGeo(ph, fbo, outW, outH, exact, flip) {
    const gl = this.gl;
    const [cx, cy, cw, chh] = this.cropRect(ph);
    const th = ((this.params.straighten || 0) * Math.PI) / 180;
    let scale = 1, ox = 0, oy = 0;
    if (!exact) { scale = Math.max(cw / outW, chh / outH); ox = (outW - cw / scale) / 2; oy = (outH - chh / scale) / 2; }
    gl.useProgram(this.pGeo);
    gl.uniform4fv(gl.getUniformLocation(this.pGeo, 'G'), new Float32Array([ph.w, ph.h, outW, outH, Math.cos(th), Math.sin(th), th ? 1 : 0, scale, cx, cy, cw, chh, ox, oy, 0.11, 0]));
    gl.uniform1f(gl.getUniformLocation(this.pGeo, 'flipY'), flip ? 1 : 0);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, ph.colorTex.gl);
    gl.uniform1i(gl.getUniformLocation(this.pGeo, 'colorT'), 0);
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.viewport(0, 0, outW, outH);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  frame() {
    const ph = this.current;
    if (!ph || (!this.dirtyColor && !this.dirtyGeo)) return null;
    const t0 = performance.now();
    const c = this.canvas, dpr = devicePixelRatio || 1;
    const W = Math.max(1, Math.round(c.clientWidth * dpr)), H = Math.max(1, Math.round(c.clientHeight * dpr));
    if (c.width !== W || c.height !== H) { c.width = W; c.height = H; }
    const color = this.dirtyColor;
    if (this.dirtyColor) this.drawColor(ph);
    this.drawGeo(ph, null, W, H, false, true);
    this.fence();
    this.dirtyColor = this.dirtyGeo = false;
    return { cpu: performance.now() - t0, color, W, H };
  }

  async readback() {
    const gl = this.gl, ph = this.current;
    const [, , cw, chh] = this.cropRect(ph);
    const tex = this.tex2d(gl.RGBA8, cw, chh, gl.RGBA, gl.UNSIGNED_BYTE, null);
    const fbo = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
    this.drawColor(ph);
    this.drawGeo(ph, fbo, cw, chh, true, false);
    const out = new Uint8Array(cw * chh * 4);
    gl.readPixels(0, 0, cw, chh, gl.RGBA, gl.UNSIGNED_BYTE, out);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.deleteFramebuffer(fbo);
    gl.deleteTexture(tex);
    this.dirtyColor = this.dirtyGeo = true;
    return { w: cw, h: chh, data: out };
  }

  async benchGpu(n = 60, W = 2560, H = 1600) {
    const gl = this.gl, ph = this.current;
    const tex = this.tex2d(gl.RGBA8, W, H, gl.RGBA, gl.UNSIGNED_BYTE, null);
    const fbo = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
    this.fence();
    await this.waitFence();
    const t0 = performance.now();
    for (let i = 0; i < n; i++) { this.drawColor(ph); this.drawGeo(ph, fbo, W, H, false, false); }
    this.fence();
    await this.waitFence();
    const ms = (performance.now() - t0) / n;
    gl.deleteFramebuffer(fbo);
    gl.deleteTexture(tex);
    this.dirtyColor = this.dirtyGeo = true;
    return ms;
  }
}
