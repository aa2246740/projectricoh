#!/usr/bin/env python3
"""Real DNG inputs through Engine, with an explicit absolute-T1 adapter."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import csv
import hashlib
import json
from collections import defaultdict
import numpy as np
from PIL import Image, ImageDraw, ImageOps
import runtime as r
import tweak as t

WIDTH = 320
SCENES = (
    ("desk", "红印纸与桌面", "2026-10-16/S1b-sd-import/DCIM/100RICOH/R8051130"),
    ("neutral", "灰墙与笔", "2026-10-16/S1b-sd-import/DCIM/100RICOH/R8051137"),
    ("apple", "苹果与杂物", "2026-10-19/stage2c-first-run/R8051144"),
)
LABELS = {"contrast": "对比", "saturation": "饱和", "highlight": "高光", "shadow": "阴影"}


def raw_input(dng, width=WIDTH):
    """Area-average each CFA plane before WB. This is not a texture renderer."""
    if dng.orientation != 1:
        raise ValueError("selected fixture needs orientation 1")
    y0, x0, height, full_width = dng.crop_window()
    output_height = round(height * width / full_width)
    colours = defaultdict(list)
    raw_clip = []
    for oy in range(2):
        for ox in range(2):
            yy = np.arange(y0 + oy, y0 + height - height % 2, 2)[:, None]
            xx = np.arange(x0 + ox, x0 + full_width - full_width % 2, 2)[None, :]
            values = dng.normalised_at(yy, xx)
            raw_clip.append(float(np.mean(values >= .98)))
            plane = Image.fromarray(values.astype(np.float32)).resize((width, output_height), Image.Resampling.BOX)
            colour = int(dng.cfa_at(y0 + oy, x0 + ox))
            colours[colour].append(np.asarray(plane, dtype=float))
    wb = np.stack([np.mean(colours[c], axis=0) for c in range(3)], axis=-1)
    wb = wb / dng.as_shot_neutral
    x = wb.reshape(-1, 3) * 4095
    return x, (width, output_height), {"raw_photosite_near_white_fraction": sum(raw_clip) / 4,
                                      "model_input_above_4095_fraction": float(np.any(x > 4095, axis=1).mean()),
                                      "model_input_below_zero_fraction": float(np.any(x < 0, axis=1).mean())}


def predict(engine, slot, rows, x):
    """Use Engine.predict verbatim for shared curves; adapt only T1 input curves."""
    old = engine.entries[slot]
    if not old["mask"] & 6:
        engine.entries[slot] = dict(old, rows=rows, written=rows)
        try:
            return engine.predict(slot, x, unclipped=True)
        finally:
            engine.entries[slot] = old
    if old["mask"] & 6 != 6 or old["control"] != 0:
        raise ValueError("unsupported T1 mask/control")
    xs = np.asarray(t.input_nodes(rows[0]))
    channel_curves = (rows[6][:33], rows[1], rows[6][33:])
    pre = np.column_stack([np.interp(np.clip(x[:, c], 0, 4095), xs, list(channel_curves[c]))
                           for c in range(3)])
    row = engine.mm.MatrixRow.from_bytes(rows[3][:28])
    ab = np.asarray([engine.fs.decode_word(rows[2][i:i + 4]) for i in range(0, 96, 4)])
    z = engine.fs.Z_of_words(ab[:, 0], ab[:, 1], engine.ctx)
    y, ci = row.apply(pre)
    co = engine.table.forward(ci, z)[0]
    return engine.mm.rgb_from_ycc(y, co)


def statistics(values):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return {"n": 0, "mean": None, "median": None, "p90": None, "max": None}
    assert np.isfinite(values).all()
    return {"n": len(values), "mean": float(values.mean()), "median": float(np.median(values)),
            "p90": float(np.percentile(values, 90)), "max": float(values.max())}


def save_frame(rgb, size, path):
    codes = np.floor(np.clip(rgb, 0, 255) + .5).astype(np.uint8).reshape(size[1], size[0], 3)
    Image.fromarray(codes).save(path, optimize=True)


def write_html(frames, scenes, aggregate):
    data = {"frames": frames, "scenes": scenes, "aggregate": aggregate, "labels": LABELS}
    markup = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>单配方微调 · 模型模拟</title>
<style>
:root{color-scheme:light dark;font-family:system-ui,sans-serif;background:#f4f3ef;color:#20211f}
body{max-width:1360px;margin:0 auto;padding:24px}h1{font-size:26px;margin:0 0 10px}p{line-height:1.6}
.notice{border-left:4px solid #b65b33;padding:8px 14px;background:#fff6e9}
.controls{display:flex;gap:16px;flex-wrap:wrap;margin:22px 0 14px}label{display:flex;gap:7px;align-items:center}
select,button{font:inherit;padding:9px 14px;border:1px solid #a7aaa3;border-radius:4px;background:#fff;color:#20211f}
button[aria-pressed="true"]{background:#242b26;color:white;border-color:#242b26}button:focus-visible,select:focus-visible{outline:3px solid #9c5b32;outline-offset:2px}
.steps{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px}
figure{margin:0}figure img{display:block;width:100%;height:auto;border:1px solid #aaa;box-sizing:border-box;background:#ddd}
figcaption{margin:7px 0 14px;line-height:1.5}.strip{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin:16px 0}
.strip button{padding:0;overflow:hidden}.strip img{width:100%;display:block;height:auto}.strip span{display:block;padding:7px}
.measure{font-variant-numeric:tabular-nums;padding:10px 0;border-top:1px solid #aaa;line-height:1.6}
.source{display:flex;align-items:center;gap:15px}.source img{width:200px;height:auto}
details{margin:20px 0}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:9px;border-bottom:1px solid #bbb}
@media(max-width:700px){body{padding:14px}.pair{grid-template-columns:1fr}.strip{gap:4px}.strip span{font-size:13px}.source{display:block}}
@media(prefers-color-scheme:dark){:root{background:#20211f;color:#eee}.notice{background:#3a3024}select,button{background:#30362f;color:#eee}.measure{border-color:#666}}
</style>
<h1>单配方微调</h1><p class="notice">模型模拟，不是相机实拍。只供判断档位步长；相同源 DNG、曝光与白平衡贯穿所有配方和档位。</p>
<div class="controls"><label>实景<select id="scene"></select></label><label>配方<select id="recipe"><option>01</option><option>02</option><option>03</option><option>05</option><option>06</option></select></label><label>参数<select id="parameter"></select></label></div>
<div class="steps" id="levels"></div><p id="stepnote"></p>
<div class="pair"><figure><img id="base" alt="当前配方默认档的模型模拟"><figcaption>此配方默认 0 档 · 模型模拟</figcaption></figure><figure><img id="chosen" alt="所选档位的模型模拟"><figcaption id="caption"></figcaption></figure></div>
<div class="measure" id="metrics" aria-live="polite"></div><div class="strip" id="strip"></div>
<details><summary>查看原始 GXR JPEG 和模型限制</summary><div class="source"><img id="source" alt="源照片配套的原始 GXR JPEG"><p id="sourceinfo"></p></div><p>原始 JPEG 拍摄时的配方不统一，仅用于识别素材。模拟直接读取 DNG CFA，扣黑电平、按白电平归一并使用 AsShotNeutral，固定增益 1，不以 JPEG 反算或拟合曝光。CFA 平面先缩图，未模拟去马赛克细节、降噪、锐度和镜头处理。三张源图 ISO 均非模型标定 ISO，本页固定用 ISO 200 标定，绝对外观有误差。06 使用已有 R=C、G=B5、B=D 的绝对三通道解释。</p></details>
<details><summary>所有配方的相邻档平均 ΔE00</summary><p>每行是三张图、四组相邻档的等权均值。数值来自浮点模型最终裁剪后的 RGB，不包含 PNG 显示量化。平均值不能代替对人像、户外和局部纹理的观察。</p><table><thead><tr><th>配方</th><th>参数</th><th>平均 ΔE00</th><th>12 组均值范围</th></tr></thead><tbody id="summary"></tbody></table></details>
<script>const DATA=__DATA__;
let currentLevel=0;const $=id=>document.getElementById(id);
for(const s of DATA.scenes){const o=new Option(s.title,s.id);$('scene').add(o)}
for(const [key,label] of Object.entries(DATA.labels))$('parameter').add(new Option(label,key));
function rows(){return DATA.frames.filter(f=>f.scene===$('scene').value&&f.slot===$('recipe').value&&f.parameter===$('parameter').value).sort((a,b)=>a.level-b.level)}
function show(){const f=rows(),zero=f.find(v=>v.level===0),chosen=f.find(v=>v.level===currentLevel),p=$('parameter').value;
$('base').src=zero.image;$('chosen').src=chosen.image;$('caption').textContent=`${$('recipe').value} · ${DATA.labels[p]} ${currentLevel>0?'+':''}${currentLevel} 档 · 模型模拟`;
$('levels').replaceChildren();$('strip').replaceChildren();for(const x of f){let b=document.createElement('button');b.type='button';b.textContent=(x.level>0?'+':'')+x.level;b.setAttribute('aria-pressed',x.level===currentLevel);b.onclick=()=>{currentLevel=x.level;show()};$('levels').append(b);let q=b.cloneNode();q.type='button';q.setAttribute('aria-pressed',x.level===currentLevel);let im=document.createElement('img');im.src=x.image;im.alt=`${DATA.labels[p]} ${x.level} 档模型模拟`;let lab=document.createElement('span');lab.textContent=b.textContent+' 档';q.append(im,lab);q.onclick=b.onclick;$('strip').append(q)}
const e=chosen.adjacent_previous,disabled=$('recipe').value==='03'&&p==='saturation';
$('stepnote').textContent=disabled?'03 是真黑白，饱和度停用，五档结果相同。':p==='saturation'?'每档将原生颜色系数增减 1/8；不是最终 Lab 色度的百分比。':p==='contrast'?'每档使用 12/64 曲线形变系数。正值加深阴影、提亮高光；中灰和端点固定。':'每档使用 16/64 曲线形变系数。正值提亮该区域；中灰和端点固定。';
$('metrics').textContent=(e?`与前一档 ${currentLevel-1} → ${currentLevel}：平均 ΔE00 ${e.mean.toFixed(3)}，中位 ${e.median.toFixed(3)}，p90 ${e.p90.toFixed(3)}。`:'−2 为本组最低档，没有前一档。')+` 模型 RGB 越界像素 ${(chosen.model_rgb_clip_fraction*100).toFixed(2)}%。编码钳位 ${chosen.encoding_clamps} 项。`;
const s=DATA.scenes.find(x=>x.id===$('scene').value);$('source').src=s.source_image;$('sourceinfo').textContent=`${s.title} · ${s.stem} · 源 ISO ${s.iso}。模拟使用 ISO 200 标定；此图用于步长比较。`;}
for(const id of ['scene','recipe','parameter'])$(id).onchange=()=>{currentLevel=0;show()};
for(const a of DATA.aggregate){let tr=document.createElement('tr');for(const txt of [a.slot,DATA.labels[a.parameter],a.mean.toFixed(3),a.min.toFixed(3)+'–'+a.max.toFixed(3)]){let td=document.createElement('td');td.textContent=txt;tr.append(td)}$('summary').append(tr)}
show();console.log('recipe-tweak-preview',DATA.frames.length,'frames',DATA.aggregate.length,'summaries');
</script></html>'''
    (r.LOCAL / "preview.html").write_text(markup.replace("__DATA__", json.dumps(data, ensure_ascii=False)))


def make_contacts(frames, scenes):
    for slot in r.SLOTS:
        for parameter in t.PARAMETERS:
            selected = [f for f in frames if f["slot"] == slot and f["parameter"] == parameter]
            images = {(f["scene"], f["level"]): Image.open(r.LOCAL / f["image"]).convert("RGB") for f in selected}
            height = next(iter(images.values())).height
            sheet = Image.new("RGB", (WIDTH * 5, (height + 34) * 3 + 64), "#f2f1ed")
            d = ImageDraw.Draw(sheet)
            d.text((14, 9), f"{slot} / {parameter}: -2 -1 0 +1 +2 | MODEL SIMULATION, NOT CAMERA CAPTURE", fill="#20211f")
            d.text((14, 30), "DNG CFA + AsShotNeutral, gain 1; calibration ISO200; source ISO3200 / 800 / 400", fill="#20211f")
            for row, scene in enumerate(scenes):
                for col, level in enumerate(range(-2, 3)):
                    x, y = col * WIDTH, 64 + row * (height + 34)
                    sheet.paste(images[scene["id"], level], (x, y))
                    f = next(v for v in selected if v["scene"] == scene["id"] and v["level"] == level)
                    prev = f["adjacent_previous"]
                    text = f'{scene["stem"]}  {level:+d}  mean DE00(prev)={prev["mean"]:.3f}' if prev else f'{scene["stem"]}  -2'
                    d.text((x + 5, y + height + 6), text, fill="#20211f")
            sheet.save(r.LOCAL / "contacts" / f"{slot}-{parameter}.png", optimize=True)


def main():
    r.setup()
    _, _, _, entries = r.baseline()
    v = json.loads((r.LOCAL / "variants.json").read_text())
    if v["schema"] != t.ALGORITHM:
        raise ValueError("rerun verify.py after changing the algorithm")
    engine = r.engine(iso=200)
    fs = engine.fs
    assert abs(float(fs.delta_e00(np.array([[50, 2.6772, -79.7751]]),
                                  np.array([[50, 0, -82.7485]]))[0]) - 2.0425) < .00005
    deps = {p: r.sha(r.ROOT / p) for p in ("research/closed_loop/model.py", "research/closed_loop/common.py",
            "research/closed_loop/local/vendor_manifest.json", "research/recipe_tweak/tweak.py",
            "research/recipe_tweak/preview.py")}
    for name in ("frames", "contacts"):
        (r.LOCAL / name).mkdir(exist_ok=True)
    frames, scenes, metrics = [], [], []
    for scene_id, title, rel in SCENES:
        path = r.ROOT / "captures/a12-50" / rel
        dng_path, jpeg_path = path.with_suffix(".DNG"), path.with_suffix(".JPG")
        for p in (dng_path, jpeg_path):
            deps[str(p.relative_to(r.ROOT))] = r.sha(p)
        dng = fs.dsm().Dng(dng_path)
        x, size, input_info = raw_input(dng)
        source = ImageOps.exif_transpose(Image.open(jpeg_path)).convert("RGB").resize(size, Image.Resampling.LANCZOS)
        source.save(r.LOCAL / "frames" / f"{scene_id}-source.png", optimize=True)
        scenes.append({"id": scene_id, "title": title, "stem": path.name, "iso": dng.exif["iso"],
                       "source_image": f"frames/{scene_id}-source.png", "dng": dng.summary(), "input": input_info,
                       "size": list(size), "fixed_raw_gain": 1, "calibration_iso": 200, "source_iso_calibrated": False})
        for slot in r.SLOTS:
            cache = {}
            for parameter in t.PARAMETERS:
                outputs = []
                for level in range(-2, 3):
                    variant = next(q for q in v["variants"] if (q["slot"], q["parameter"], q["level"]) == (slot, parameter, level))
                    key = variant["entry_hex"]
                    if key not in cache:
                        rows, clamps = t.apply(entries[slot], t.Levels(**variant["levels"]), v["pivot_x"])
                        if t.encode_entry(bytes.fromhex(next(z["entry_hex"] for z in v["variants"]
                                if z["slot"] == slot and z["level"] == 0)), rows).hex() != key:
                            raise ValueError("stale validation variants")
                        raw = predict(engine, slot, rows, x)
                        if not np.isfinite(raw).all():
                            raise ValueError("non-finite model output")
                        rgb = np.clip(raw, 0, 255)
                        filename = f"frames/{scene_id}-{slot}-{parameter}-{level:+d}.png"
                        save_frame(rgb, size, r.LOCAL / filename)
                        cache[key] = (rgb, filename, float(np.any((raw < 0) | (raw > 255), axis=1).mean()))
                    rgb, filename, clip_fraction = cache[key]
                    outputs.append(rgb)
                    frames.append({"scene": scene_id, "slot": slot, "parameter": parameter, "level": level,
                                   "image": filename, "adjacent_previous": None, "model_rgb_clip_fraction": clip_fraction,
                                   "encoding_clamps": len(variant["clamps"]),
                                   "rgb_float_sha256": hashlib.sha256(rgb.astype("<f8").tobytes()).hexdigest()})
                # Four neighbouring pairs, all pixels including model clipping.
                lab = [fs.lab_from_codes(o) for o in outputs]
                y = engine.mm.ycbcr(outputs[2])[0]
                for j in range(4):
                    error = fs.delta_e00(lab[j], lab[j + 1])
                    row = {"scene": scene_id, "slot": slot, "parameter": parameter,
                           "from": j - 2, "to": j - 1, **statistics(error),
                           "fraction_above_1": float((error >= 1).mean()),
                           "fraction_above_3": float((error >= 3).mean()),
                           "default_Y_below_118": statistics(error[y < 118]),
                           "default_Y_at_least_118": statistics(error[y >= 118])}
                    metrics.append(row)
                    frames[-5 + j + 1]["adjacent_previous"] = statistics(error)
            print(f"rendered {scene_id} recipe {slot}", flush=True)
    aggregate = []
    for slot in r.SLOTS:
        for parameter in t.PARAMETERS:
            group = [m for m in metrics if m["slot"] == slot and m["parameter"] == parameter]
            means = [m["mean"] for m in group]
            aggregate.append({"slot": slot, "parameter": parameter, "pairs": len(group),
                              "mean": float(np.mean(means)), "min": min(means), "max": max(means),
                              "adjacent": {f"{j}->{j + 1}": float(np.mean([m["mean"] for m in group if m["from"] == j]))
                                           for j in range(-2, 2)}})
    assert len(frames) == 300 and len(metrics) == 240
    # Shared-curve T1 identity test: adapter and Engine must agree when C=B=D.
    rows = list(entries["06"]["rows"])
    rows[6] = rows[1] * 2
    t1 = predict(engine, "06", tuple(rows), x[:1000])
    original = engine.entries["06"]
    engine.entries["06"] = dict(original, mask=original["mask"] & ~6, control=2)
    shared = predict(engine, "06", tuple(rows), x[:1000])
    engine.entries["06"] = original
    adapter_error = float(np.max(np.abs(t1 - shared)))
    assert adapter_error < 1e-10
    assert all(r.sha(r.ROOT / p) == digest for p, digest in deps.items())
    provenance = engine.provenance.finish()
    r.dump(r.LOCAL / "preview_inputs.json", {"direct": deps, "engine": provenance})
    r.dump(r.LOCAL / "metrics.json", {"model_simulation_not_capture": True, "scenes": scenes,
                                     "pairs": metrics, "aggregate": aggregate,
                                     "T1_shared_curve_equivalence_max_rgb_error": adapter_error,
                                     "baseline_sha256": r.EXPECTED_SHA, "frames": len(frames),
                                     "metric_domain": "all reduced pixels, clipped float model RGB, fixed ISO200 model"})
    r.dump(r.LOCAL / "frames.json", frames)
    with (r.LOCAL / "adjacent_delta_e00.csv").open("w", newline="") as stream:
        keys = ("scene", "slot", "parameter", "from", "to", "n", "mean", "median", "p90", "max", "fraction_above_1", "fraction_above_3")
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows({k: row[k] for k in keys} for row in metrics)
    write_html(frames, scenes, aggregate)
    make_contacts(frames, scenes)
    print(json.dumps({"frames": len(frames), "adjacent_pairs": len(metrics), "T1_equivalence": adapter_error}, ensure_ascii=False))


if __name__ == "__main__":
    main()
