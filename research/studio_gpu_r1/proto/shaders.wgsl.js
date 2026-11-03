// 显卡管线的 WGSL。每一步按 studio/src/gxr_studio 的现有算法逐项对应（文件名:函数写在注释里），不另发明调整。
// 数值约定：链内颜色是 0..255 的浮点；每个 Python 里会落成 uint8 的地方，这里都做 floor(clamp(x)+0.5)。

export const COMMON = /* wgsl */ `
struct P {
  gains: vec4f,     // render/tones.py channel_gains：R、G、B 乘数（无调整时为 1）
  flags: vec4f,     // x: 有调子表  y: LUT 模式 0 无 / 1 显示类 / 2 Log 类  z: apply_base 是否生效（LUT 后） w: LUT 强度
  extra: vec4f,     // finish/pixels.py apply_extra：黑点、饱和度、自然饱和度、暗角（-100..100）
  dims: vec4f,      // 代理图（未裁切画面）宽、高；输出宽、高
  geo: vec4f,       // 拉直：cos、sin、是否拉直、缩放（输出像素 → 裁切后画面像素）
  crop: vec4f,      // 裁切矩形（未裁切画面像素）：x、y、w、h
  bake: vec4f,      // render/chain.py ChromaBake：origin cb、origin cr、1/step、nx
  bake2: vec4f,     // ny、—、—、—
  lutA: vec4f,      // LUT：输入空间 id、输出空间 id、边长 n、输入 range（0 full / 1 legal）
  lutDom0: vec4f,   // domain_min
  lutDom1: vec4f,   // domain_max
  lutRng: vec4f,    // range3 lo、hi
  inM0: vec4f, inM1: vec4f, inM2: vec4f,     // 进 LUT 前的 3×3（+偏移 w）：显示类 = inv(M_gamut)·M709；Log 类 = inv(M_gamut)·场景仿射
  outM0: vec4f, outM1: vec4f, outM2: vec4f,  // LUT 输出 → XYZ → sRGB 线性：inv(M709)·M_gamut_out
};
@group(0) @binding(0) var<uniform> p: P;
@group(0) @binding(1) var<storage, read> rec: array<f32>;   // pre(4096×3) | matrix(9) | offset(3) | gain(ny×nx×2)
@group(0) @binding(2) var<storage, read> tone: array<f32>;  // render/tones.py display_table（1021 点）
@group(0) @binding(3) var lut3: texture_3d<f32>;             // .cube 3D 表，x=R、y=G、z=B

const PRE_N: u32 = 4096u;
const MAT_AT: u32 = 12288u;
const OFF_AT: u32 = 12297u;
const GAIN_AT: u32 = 12300u;

fn q8(v: vec3f) -> vec3f { return floor(clamp(v, vec3f(0.0), vec3f(255.0)) + 0.5); }

// render/tones.py apply_table：0..255 浮点，均匀网格线性插值，TABLE_STEP=4
fn applyTable(v: vec3f) -> vec3f {
  var o: vec3f;
  for (var c = 0u; c < 3u; c++) {
    let pos = clamp(v[c], 0.0, 255.0) * 4.0;
    let i = min(u32(pos), 1019u);
    let f = pos - f32(i);
    let lo = tone[i];
    o[c] = lo + (tone[i + 1u] - lo) * f;
  }
  return o;
}

// render/chain.py _chroma_chunk：码值 → 一维曲线 → YCbCr 矩阵 → (Cb,Cr) 复数增益（双线性）→ BT.601 → RGB
fn recipeChain(codesIn: vec3f, gains: vec3f, useTable: bool) -> vec3f {
  let x = clamp(codesIn * gains, vec3f(0.0), vec3f(4095.0));
  var pc: vec3f;
  for (var c = 0u; c < 3u; c++) {
    let i = min(u32(x[c]), 4094u);
    let v0 = rec[i * 3u + c];
    pc[c] = v0 + (rec[(i + 1u) * 3u + c] - v0) * (x[c] - f32(i));
  }
  let y  = rec[MAT_AT + 0u] * pc.x + rec[MAT_AT + 1u] * pc.y + rec[MAT_AT + 2u] * pc.z + rec[OFF_AT + 0u];
  let cb = rec[MAT_AT + 3u] * pc.x + rec[MAT_AT + 4u] * pc.y + rec[MAT_AT + 5u] * pc.z + rec[OFF_AT + 1u];
  let cr = rec[MAT_AT + 6u] * pc.x + rec[MAT_AT + 7u] * pc.y + rec[MAT_AT + 8u] * pc.z + rec[OFF_AT + 2u];
  let nx = i32(p.bake.w);
  let ny = i32(p.bake2.x);
  let u = (cb - p.bake.x) * p.bake.z;
  let v = (cr - p.bake.y) * p.bake.z;
  let iu = clamp(i32(clamp(u, -1e6, 1e6)), 0, nx - 2);   // numpy astype(int32) = 向零取整，再夹
  let iv = clamp(i32(clamp(v, -1e6, 1e6)), 0, ny - 2);
  let fu = u - f32(iu);
  let fv = v - f32(iv);
  let at = u32(iv * nx + iu);
  let a00 = vec2f(rec[GAIN_AT + at * 2u], rec[GAIN_AT + at * 2u + 1u]);
  let a01 = vec2f(rec[GAIN_AT + (at + 1u) * 2u], rec[GAIN_AT + (at + 1u) * 2u + 1u]);
  let a10 = vec2f(rec[GAIN_AT + (at + u32(nx)) * 2u], rec[GAIN_AT + (at + u32(nx)) * 2u + 1u]);
  let a11 = vec2f(rec[GAIN_AT + (at + u32(nx) + 1u) * 2u], rec[GAIN_AT + (at + u32(nx) + 1u) * 2u + 1u]);
  let gg = (a00 * (1.0 - fu) + a01 * fu) * (1.0 - fv) + (a10 * (1.0 - fu) + a11 * fu) * fv;
  let cbo = cb * gg.x - cr * gg.y;
  let cro = cb * gg.y + cr * gg.x;
  var rgb = vec3f(y + 1.402 * cro, y - 0.344136 * cbo - 0.714136 * cro, y + 1.772 * cbo);
  rgb = clamp(rgb, vec3f(0.0), vec3f(255.0));
  if (useTable) { rgb = applyTable(rgb); }
  return q8(rgb);   // chain.quantize
}

// lut/spaces.py encode / decode（只放这一轮用到的：srgb=0 rec709=1 gamma24=2 llog=3 linear=4）
fn log10f(x: f32) -> f32 { return log2(max(x, 1e-30)) * 0.30102999566; }
fn enc1(x: f32, s: u32) -> f32 {
  if (s == 0u) { if (x <= 0.0031308) { return 12.92 * x; } return 1.055 * pow(max(x, 0.0), 1.0 / 2.4) - 0.055; }
  if (s == 1u) { if (x < 0.018) { return 4.5 * x; } return 1.099 * pow(max(x, 0.0), 0.45) - 0.099; }
  if (s == 2u) { return sign(x) * pow(abs(x), 1.0 / 2.4); }
  if (s == 3u) { if (x <= 0.006) { return 8.0 * x + 0.09; } return 0.27 * log10f(1.3 * x + 0.0115) + 0.6; }
  return x;
}
fn dec1(x: f32, s: u32) -> f32 {
  if (s == 0u) { if (x <= 0.04045) { return x / 12.92; } return pow(max((x + 0.055) / 1.055, 0.0), 2.4); }
  if (s == 1u) { if (x < 0.081) { return x / 4.5; } return pow(max((x + 0.099) / 1.099, 0.0), 1.0 / 0.45); }
  if (s == 2u) { return sign(x) * pow(abs(x), 2.4); }
  if (s == 3u) { if (x <= 0.1380) { return (x - 0.09) / 8.0; } return (pow(10.0, (x - 0.6) / 0.27) - 0.0115) / 1.3; }
  return x;
}
fn enc3(v: vec3f, s: u32) -> vec3f { return vec3f(enc1(v.x, s), enc1(v.y, s), enc1(v.z, s)); }
fn dec3(v: vec3f, s: u32) -> vec3f { return vec3f(dec1(v.x, s), dec1(v.y, s), dec1(v.z, s)); }
fn mat3x(v: vec3f, a: vec4f, b: vec4f, c: vec4f) -> vec3f {
  return vec3f(dot(a.xyz, v) + a.w, dot(b.xyz, v) + b.w, dot(c.xyz, v) + c.w);
}

// lut/cube.py Cube.tetrahedral：按小数部分从大到小（相等时通道序号小的在前）逐轴累加
fn lutAt(c: vec3i) -> vec3f { return textureLoad(lut3, c, 0).xyz; }
fn tetra(x: vec3f) -> vec3f {
  let n = i32(p.lutA.z);
  let pos = x * f32(n - 1);
  let base = min(vec3i(pos), vec3i(n - 2));
  let f = pos - vec3f(base);
  // 稳定的降序 argsort
  var o0 = 0; var o1 = 1; var o2 = 2;
  if (f[o1] > f[o0]) { let t = o0; o0 = o1; o1 = t; }
  if (f[o2] > f[o1]) { let t = o1; o1 = o2; o2 = t; }
  if (f[o1] > f[o0]) { let t = o0; o0 = o1; o1 = t; }
  var b = base;
  let v0 = lutAt(b);
  b[o0] += 1; let v1 = lutAt(b);
  b[o1] += 1; let v2 = lutAt(b);
  b[o2] += 1; let v3 = lutAt(b);
  return v0 + f[o0] * (v1 - v0) + f[o1] * (v2 - v1) + f[o2] * (v3 - v2);
}

// lut/spaces.py Target.render + lut/photo.py _apply 的量化；inp 已经在 LUT 输入空间的线性 RGB
fn lutRender(lin_in: vec3f) -> vec3f {
  var x = enc3(lin_in, u32(p.lutA.x));
  if (p.lutA.w > 0.5) { x = (64.0 + 876.0 * x) / 1023.0; }
  x = (x - p.lutDom0.xyz) / (p.lutDom1.xyz - p.lutDom0.xyz);
  x = (x - vec3f(p.lutRng.x)) / (p.lutRng.y - p.lutRng.x);
  let out = tetra(clamp(x, vec3f(0.0), vec3f(1.0)));
  let lin = dec3(out, u32(p.lutA.y));
  let srgb = enc3(mat3x(lin, p.outM0, p.outM1, p.outM2), 0u);
  return clamp(srgb, vec3f(0.0), vec3f(1.0)) * 255.0;
}

// finish/pixels.py apply_base（LUT 之后的曝光、色温色调、对比/高光/阴影、曲线；输入输出都是 0..255 整数）
fn srgbToLin(u: vec3f) -> vec3f {
  let x = u / 255.0;
  return select(pow((x + 0.055) / 1.055, vec3f(2.4)), x / 12.92, x <= vec3f(0.04045));
}
fn applyBase(u: vec3f) -> vec3f {
  var lin = srgbToLin(u) * p.gains.xyz;
  let x = max(lin, vec3f(0.0));
  let e = select(1.055 * pow(x, vec3f(1.0 / 2.4)) - 0.055, x * 12.92, x <= vec3f(0.0031308));
  var o = floor(clamp(e * 255.0 + 0.5, vec3f(0.0), vec3f(255.0)));
  if (p.flags.x > 0.5) { o = floor(clamp(applyTable(o) + 0.5, vec3f(0.0), vec3f(255.0))); }
  return o;
}

// finish/pixels.py apply_extra：黑点 → 饱和度 → 自然饱和度 → 暗角，每步落成 uint8
fn applyExtra(u0: vec3f, pix: vec2f, wh: vec2f) -> vec3f {
  var u = u0;
  let bp = p.extra.x;
  if (bp != 0.0) {
    var y = u / 255.0;
    let k = abs(bp) / 100.0 * 0.35;
    if (bp > 0.0) { y = clamp((y - k) / max(1e-4, 1.0 - k), vec3f(0.0), vec3f(1.0)); } else { y = y * (1.0 - k) + k; }
    u = floor(clamp(y * 255.0 + 0.5, vec3f(0.0), vec3f(255.0)));
  }
  let sat = p.extra.y;
  if (sat != 0.0) {
    let gray = u.x * 0.2126 + u.y * 0.7152 + u.z * 0.0722;
    u = floor(clamp(gray + (u - gray) * (1.0 + sat / 100.0) + 0.5, vec3f(0.0), vec3f(255.0)));
  }
  let vib = p.extra.z;
  if (vib != 0.0) {
    let gray = u.x * 0.2126 + u.y * 0.7152 + u.z * 0.0722;
    let dull = 1.0 - clamp((max(u.x, max(u.y, u.z)) - min(u.x, min(u.y, u.z))) / 255.0, 0.0, 1.0);
    u = floor(clamp(gray + (u - gray) * (1.0 + vib / 100.0 * dull) + 0.5, vec3f(0.0), vec3f(255.0)));
  }
  let vig = p.extra.w;
  if (vig != 0.0) {
    let hx = max((wh.x - 1.0) / 2.0, 1.0);
    let hy = max((wh.y - 1.0) / 2.0, 1.0);
    let r = clamp(length(vec2f((pix.x - (wh.x - 1.0) / 2.0) / hx, (pix.y - (wh.y - 1.0) / 2.0) / hy)), 0.0, 1.0);
    let g = 1.0 + vig / 100.0 * 0.65 * (r * r * (3.0 - 2.0 * r));
    u = floor(clamp(u * g + 0.5, vec3f(0.0), vec3f(255.0)));
  }
  return u;
}

// 一个像素的整条颜色链（预览与导出共用）
fn colorChain(codes: vec3f, pix: vec2f, wh: vec2f) -> vec3f {
  let mode = u32(p.flags.y);
  var u: vec3f;
  if (mode == 0u) {
    u = recipeChain(codes, p.gains.xyz, p.flags.x > 0.5);
  } else {
    var base: vec3f;
    var lin_in: vec3f;
    if (mode == 1u) {
      base = recipeChain(codes, vec3f(1.0), false);           // 显示类：底图去掉调整
      lin_in = mat3x(srgbToLin(base), p.inM0, p.inM1, p.inM2);
    } else {
      base = q8(enc3(clamp(codes / 4095.0, vec3f(0.0), vec3f(1.0)), 0u) * 255.0); // 仅强度混合时用
      lin_in = mat3x(codes, p.inM0, p.inM1, p.inM2);          // Log 类：码值 → 场景 XYZ → LUT 输入色域
    }
    let looked = lutRender(lin_in);
    u = q8(mix(base, looked, p.flags.w));                       // 强度 1 = 现有行为；<1 是新功能
    if (p.flags.z > 0.5) { u = applyBase(u); }
  }
  return applyExtra(u, pix, wh);
}
`;

// 第一遍：代理图 → 颜色（代理图分辨率，rgba8unorm 存整数码值）
export const COLOR_PASS = COMMON + /* wgsl */ `
@group(1) @binding(0) var proxy: texture_2d<f32>;
@vertex fn vs(@builtin(vertex_index) i: u32) -> @builtin(position) vec4f {
  let xy = vec2f(f32((i << 1u) & 2u), f32(i & 2u));
  return vec4f(xy * 2.0 - 1.0, 0.0, 1.0);
}
@fragment fn fs(@builtin(position) pos: vec4f) -> @location(0) vec4f {
  let pix = vec2i(pos.xy);
  let codes = textureLoad(proxy, pix, 0).xyz;
  let u = colorChain(codes, vec2f(pix), p.dims.xy);
  return vec4f(u / 255.0, 1.0);
}
`;

// 第二遍：拉直 + 裁切 + 缩放到输出（finish/geometry.py _straighten_coords / _sample，FILL = 1B1C1F）
export const GEO_PASS = /* wgsl */ `
struct G { dims: vec4f, geo: vec4f, crop: vec4f, view: vec4f };
@group(0) @binding(0) var<uniform> g: G;
@group(0) @binding(1) var colorTex: texture_2d<f32>;
@vertex fn vs(@builtin(vertex_index) i: u32) -> @builtin(position) vec4f {
  let xy = vec2f(f32((i << 1u) & 2u), f32(i & 2u));
  return vec4f(xy * 2.0 - 1.0, 0.0, 1.0);
}
fn texel(x: i32, y: i32) -> vec3f { return textureLoad(colorTex, vec2i(x, y), 0).xyz * 255.0; }
@fragment fn fs(@builtin(position) pos: vec4f) -> @location(0) vec4f {
  let W = g.dims.x; let H = g.dims.y;
  // 输出像素 → 未裁切画面坐标（缩放 1 时正好是整数像素）
  let o = (pos.xy - 0.5 - g.view.xy) * g.geo.w;
  if (o.x < -0.5 || o.y < -0.5 || o.x > g.crop.z - 0.5 || o.y > g.crop.w - 0.5) { return vec4f(g.view.zzz, 1.0); }
  let X = g.crop.x + o.x;
  let Y = g.crop.y + o.y;
  let dx = X - (W - 1.0) / 2.0;
  let dy = Y - (H - 1.0) / 2.0;
  let sx = g.geo.x * dx + g.geo.y * dy + (W - 1.0) / 2.0;
  let sy = -g.geo.y * dx + g.geo.x * dy + (H - 1.0) / 2.0;
  let valid = sx >= -1e-3 && sy >= -1e-3 && sx <= W - 1.0 + 1e-3 && sy <= H - 1.0 + 1e-3;
  if (!valid) { return vec4f(vec3f(27.0, 28.0, 31.0) / 255.0, 1.0); }
  let fx = floor(sx); let fy = floor(sy);
  let x0 = clamp(i32(fx), 0, i32(W) - 1); let y0 = clamp(i32(fy), 0, i32(H) - 1);
  let x1 = min(x0 + 1, i32(W) - 1); let y1 = min(y0 + 1, i32(H) - 1);
  let tx = sx - fx; let ty = sy - fy;
  let s = texel(x0, y0) * ((1.0 - tx) * (1.0 - ty)) + texel(x1, y0) * (tx * (1.0 - ty)) + texel(x0, y1) * ((1.0 - tx) * ty) + texel(x1, y1) * (tx * ty);
  return vec4f(floor(clamp(s + 0.5, vec3f(0.0), vec3f(255.0))) / 255.0, 1.0);
}
`;

// RAW 12 位打包字节 → 半分辨率白平衡码值（raw/codes.py half_res_codes，2×2 同色取平均，不做去马赛克）
export const BIN_PASS = /* wgsl */ `
struct R { crop: vec4f, wbn: vec4f, info: vec4f, phase: vec4f };  // crop y0 x0 h w；wb/4095；rowBytes、方向；2×2 相位
@group(0) @binding(0) var<uniform> r: R;
@group(0) @binding(1) var<storage, read> raw: array<u32>;
@group(0) @binding(2) var outTex: texture_storage_2d<rgba32float, write>;
fn byteAt(i: u32) -> u32 { return (raw[i >> 2u] >> ((i & 3u) * 8u)) & 255u; }
fn px(y: u32, x: u32) -> f32 {
  let rb = u32(r.info.x);
  let b = y * rb + (x >> 1u) * 3u;
  if ((x & 1u) == 0u) { return f32((byteAt(b) << 4u) | (byteAt(b + 1u) >> 4u)); }
  return f32(((byteAt(b + 1u) & 15u) << 8u) | byteAt(b + 2u));
}
@compute @workgroup_size(16, 16) fn main(@builtin(global_invocation_id) id: vec3u) {
  let w2 = u32(r.crop.w) / 2u; let h2 = u32(r.crop.z) / 2u;
  if (id.x >= w2 || id.y >= h2) { return; }
  let y = u32(r.crop.x) + id.y * 2u; let x = u32(r.crop.y) + id.x * 2u;
  var sum = vec3f(0.0); var cnt = vec3f(0.0);
  for (var i = 0u; i < 2u; i++) { for (var j = 0u; j < 2u; j++) {
    let c = u32(r.phase[i * 2u + j]);
    sum[c] += px(y + i, x + j) / 4095.0; cnt[c] += 1.0;
  } }
  let codes = sum / cnt * r.wbn.xyz;   // 均值 / AsShotNeutral × 4095
  textureStore(outTex, vec2i(id.xy), vec4f(codes, 0.0));   // 方向 1；其它方向在写入坐标上转
}
`;

// 全尺寸导出：12 位拆包 + 白平衡 + MHC 5×5 去马赛克（raw/demosaic.py）+ 整条颜色链，一遍写成 8 位
export const EXPORT_PASS = COMMON + /* wgsl */ `
struct R { crop: vec4f, wbg: vec4f, info: vec4f, phase: vec4f };   // wbg = 4095/neutral/4095 = 1/neutral
@group(1) @binding(0) var<uniform> r: R;
@group(1) @binding(1) var<storage, read> raw: array<u32>;
@group(1) @binding(2) var outTex: texture_storage_2d<rgba8unorm, write>;
fn byteAt(i: u32) -> u32 { return (raw[i >> 2u] >> ((i & 3u) * 8u)) & 255u; }
fn mir(c: i32, n: i32) -> i32 { var v = c; if (v < 0) { v = -v; } if (v >= n) { v = 2 * (n - 1) - v; } return v; }
fn colorAt(y: i32, x: i32) -> u32 { return u32(r.phase[u32((y & 1) * 2 + (x & 1))]); }
// 白平衡后的马赛克值（裁切坐标，镜像延拓）
fn m(y0: i32, x0: i32) -> f32 {
  let y = mir(y0, i32(r.crop.z)); let x = mir(x0, i32(r.crop.w));
  let ry = u32(y) + u32(r.crop.x); let rx = u32(x) + u32(r.crop.y);
  let b = ry * u32(r.info.x) + (rx >> 1u) * 3u;
  var v: u32;
  if ((rx & 1u) == 0u) { v = (byteAt(b) << 4u) | (byteAt(b + 1u) >> 4u); } else { v = ((byteAt(b + 1u) & 15u) << 8u) | byteAt(b + 2u); }
  return f32(v) / 4095.0 * r.wbg[colorAt(y, x)] ;
}
@compute @workgroup_size(16, 16) fn main(@builtin(global_invocation_id) id: vec3u) {
  let W = i32(r.crop.w); let H = i32(r.crop.z);
  if (i32(id.x) >= W || i32(id.y) >= H) { return; }
  let x = i32(id.x); let y = i32(id.y);
  var n: array<f32, 25>;
  for (var j = 0; j < 5; j++) { for (var i = 0; i < 5; i++) { n[j * 5 + i] = m(y + j - 2, x + i - 2); } }
  let c = n[12];
  // _K_G / _K_H / _K_V / _K_X（各 /8）
  let kg = (4.0 * c + 2.0 * (n[7] + n[11] + n[13] + n[17]) - (n[2] + n[10] + n[14] + n[22])) / 8.0;
  let kh = (5.0 * c + 4.0 * (n[11] + n[13]) - (n[10] + n[14]) - (n[6] + n[8] + n[16] + n[18]) + 0.5 * (n[2] + n[22])) / 8.0;
  let kv = (5.0 * c + 4.0 * (n[7] + n[17]) - (n[2] + n[22]) - (n[6] + n[8] + n[16] + n[18]) + 0.5 * (n[10] + n[14])) / 8.0;
  let kx = (6.0 * c + 2.0 * (n[6] + n[8] + n[16] + n[18]) - 1.5 * (n[2] + n[10] + n[14] + n[22])) / 8.0;
  let col = colorAt(y, x);
  let right = colorAt(y, x + 1);
  let rg = col == 1u && right == 0u;
  var rgb: vec3f;
  if (col == 0u) { rgb = vec3f(c, kg, kx); }
  else if (col == 2u) { rgb = vec3f(kx, kg, c); }
  else if (rg) { rgb = vec3f(kh, c, kv); }
  else { rgb = vec3f(kv, c, kh); }
  let u = colorChain(rgb * 4095.0, vec2f(f32(x), f32(y)), vec2f(f32(W), f32(H)));
  textureStore(outTex, vec2i(x, y), vec4f(u / 255.0, 1.0));
}
`;
