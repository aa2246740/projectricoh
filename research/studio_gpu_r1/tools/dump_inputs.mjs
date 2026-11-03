// 给本机 wgpu（Rust）测量程序准备输入：同一份 WGSL 源码 + 与浏览器完全相同的 uniform/调子表字节。
// 用法：node dump_inputs.mjs <gpudata> <输出目录>
import fs from 'node:fs';
import path from 'node:path';
import { Engine } from '../proto/engine.js';
import { EXPORT_PASS } from '../proto/shaders.wgsl.js';

const [data, out] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, 'export.wgsl'), EXPORT_PASS);
const REPO = path.resolve(new URL('.', import.meta.url).pathname, '../../..');
const index = JSON.parse(fs.readFileSync(path.join(data, 'index.json'), 'utf8'));
const sets = JSON.parse(fs.readFileSync(new URL('../proto/paramsets.json', import.meta.url), 'utf8'));
const jobs = [];
for (const name of ['R8051410', 'R8051691']) {
  const meta = JSON.parse(fs.readFileSync(path.join(data, name, 'meta.json'), 'utf8'));
  const scene = meta.unit === 'jlaunch' ? JSON.parse(fs.readFileSync(path.join(data, name, 'scene.json'), 'utf8')) : null;
  const raw = meta.raw;
  const W = raw.crop[3], H = raw.crop[2];
  const r = new Float32Array(16);
  r.set(raw.crop, 0);
  r.set(raw.wb_gains.map((g) => g / 4095), 4);
  r.set([raw.row_bytes, raw.orientation], 8);
  r.set(raw.phase.flat(), 12);
  fs.writeFileSync(path.join(out, `r_${name}.bin`), Buffer.from(r.buffer));
  for (const ps of sets.filter((s) => ['s1_recipe01', 's2_recipe02_tone', 's3_recipe04_curve_extra', 's5_lut_display'].includes(s.id))) {
    const cap = {};
    const eng = new Engine();
    eng.device = { queue: { writeBuffer: (buf, off, arr) => { cap[buf] = arr; } } };
    eng.uniform = 'u';
    eng.toneBuf = 't';
    eng.params = { recipe: ps.recipe || 4, lut: ps.lut || null, lutStrength: 1, curve: ps.curve || null, straighten: 0, crop: null, adjust: ps.adjust || {} };
    const lutInfo = ps.lut ? index.luts.find((l) => l.name === ps.lut) : null;
    eng.writeUniform({ w: W, h: H, scene }, meta.recipes[`${ps.recipe || 4}_x`], lutInfo ? { info: lutInfo } : null);
    const tag = `${name}_${ps.id}`;
    fs.writeFileSync(path.join(out, `u_${tag}.bin`), Buffer.from(cap.u.buffer));
    fs.writeFileSync(path.join(out, `t_${tag}.bin`), Buffer.from((cap.t || new Float32Array(1021)).buffer));
    jobs.push([
      tag,
      path.join(REPO, raw.file),
      raw.strip_offsets[0],
      raw.strip_bytes,
      W,
      H,
      path.join(out, `u_${tag}.bin`),
      path.join(out, `t_${tag}.bin`),
      path.join(out, `r_${name}.bin`),
      path.join(data, name, `rec_${ps.recipe || 4}_x.bin`),
      lutInfo ? path.join(data, lutInfo.file) : '-',
      lutInfo ? lutInfo.n : 0,
    ].join(' '));
  }
}
fs.writeFileSync(path.join(out, 'jobs.txt'), jobs.join('\n') + '\n');
console.log(jobs.length, 'jobs');
