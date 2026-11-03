"""Python 参考渲染：用 studio 现有函数（只读调用）在代理图分辨率上算出每组参数的结果，存成无损 PNG。

与线上预览的关系：
- 配方链 = `render.service.render_preview` 的同一组函数（`_proxy` 的码值 → `chain.bake_chroma(PREVIEW_STEP)` →
  `chain.chroma_u8(codes, bk, gains, table)`），只是不做 JPEG 编码；成片调整 = `finish.pixels.apply_extra`。
- 显示类 LUT = `lut.photo._apply(Target, 底图)` → `apply_base` → `apply_extra`（线上的底图多一次 JPEG q95，另行统计）。
- Log 类 LUT = `lut.photo` 里的 `_apply(target, NEUTRAL.display(codes), scene_colour(dng).xyz(codes))`。
- 几何 = `finish.geometry.warp`（拉直）+ `crop_valid`（按矩形裁）。

用法：studio/.venv/bin/python reference.py <home> <gpudata> [--full NAME:SET ...]
另外把 Log 路径需要的 码值→场景 XYZ 仿射系数写进 gpudata/<photo>/scene.json（本机数据）。
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "studio/src"))

from gxr_studio.camdata import calib  # noqa: E402
from gxr_studio.finish.geometry import crop_valid, warp  # noqa: E402
from gxr_studio.finish.pixels import apply_base, apply_extra  # noqa: E402
from gxr_studio.finish.spec import Geometry  # noqa: E402
from gxr_studio.lut import spaces  # noqa: E402
from gxr_studio.lut.cube import Cube  # noqa: E402
from gxr_studio.lut.photo import _apply  # noqa: E402
from gxr_studio.lut.scene import ANCHOR, scene_colour  # noqa: E402
from gxr_studio.raw import NEUTRAL, open_dng, render_full  # noqa: E402
from gxr_studio.raw.codes import CODE_MAX  # noqa: E402
from gxr_studio.render import chain  # noqa: E402
from gxr_studio.render.params import RecipeSel, parse_adjust, parse_curve  # noqa: E402
from gxr_studio.render.recipes import CameraData  # noqa: E402
from gxr_studio.render.service import EXPORT_STEP, PREVIEW_STEP  # noqa: E402
from gxr_studio.render.tones import channel_gains, display_table  # noqa: E402

HERE = Path(__file__).resolve().parent


def scene_affine(dng) -> dict:
    sc = scene_colour(dng)
    u, f = ANCHOR["u_m"], ANCHOR["f"]
    white = sc.neutral @ sc.matrix.T
    scale = 0.18 / ((u - f) * white[1])
    a = sc.matrix * sc.neutral[None, :] * scale / CODE_MAX  # xyz = codes @ a.T + b
    b = -f * (sc.matrix * sc.neutral[None, :] * scale).sum(axis=1)
    return {"A": a.tolist(), "b": b.tolist()}


def render_set(ps: dict, codes: np.ndarray, bakes: dict, unit: str, luts: dict, dng_path: str | None, jpeg_base: bool = False):
    adjust = parse_adjust(ps.get("adjust") or {})
    master = parse_curve({"master": ps["curve"]}) if ps.get("curve") else None
    lut = ps.get("lut")
    if lut is None:
        bk = bakes[ps["recipe"]]
        rgb = chain.chroma_u8(codes, bk, channel_gains(adjust), display_table(adjust, master))
        rgb = apply_extra(rgb, adjust)
    else:
        info = luts[lut]
        target = spaces.Target(Cube.read(info["path"]), info["input_space"], info["output_space"])
        if info["input_space"] in spaces.DISPLAY:
            base = chain.chroma_u8(codes, bakes[ps["recipe"]], None, None)
            if jpeg_base:  # 线上预览：底图先经 render_preview(quality=95) 编成 JPEG 再解码
                buf = io.BytesIO()
                Image.fromarray(base, "RGB").save(buf, "JPEG", quality=95, subsampling=0)
                base = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))
            rgb = _apply(target, base)
        else:
            dng = open_dng(dng_path)
            colour = scene_colour(dng)
            rgb = _apply(target, NEUTRAL.display(codes), colour.xyz(codes))
        rgb = apply_base(rgb, adjust, master)
        rgb = apply_extra(rgb, adjust)
    if ps.get("straighten"):
        rgb, _valid = warp(rgb, Geometry(straighten=float(ps["straighten"])))
    if ps.get("crop"):
        rgb = crop_valid(rgb, tuple(ps["crop"]))
    return np.ascontiguousarray(rgb)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("home")
    ap.add_argument("gpudata")
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    home, data = Path(a.home), Path(a.gpudata)
    index = json.loads((data / "index.json").read_text())
    luts = {x["name"]: x for x in index["luts"]}
    sets = json.loads((HERE / "paramsets.json").read_text())
    cam = CameraData(home)
    models: dict = {}
    timings = {}
    for photo in index["photos"]:
        name, unit = photo["name"], photo["unit"]
        if a.only and name not in a.only.split(","):
            continue
        meta = json.loads((data / name / "meta.json").read_text())
        dng_path = str(REPO / meta["raw"]["file"])
        if unit == "jlaunch":
            dng = open_dng(dng_path)
            (data / name / "scene.json").write_text(json.dumps(scene_affine(dng)))
            dng.release()
        codes = np.load(data / name / "proxy_f32.npy")
        codes16 = codes.astype(np.float16).astype(np.float32)
        model = models.setdefault(meta["model_iso"], calib.model_for(home, meta["model_iso"])[0])
        bakes = {}
        for slot in range(1, 9):
            bakes[slot] = chain.bake_chroma(model, cam.resolve(RecipeSel(unit, slot)).entry, PREVIEW_STEP)
        out = data / name / "ref"
        out.mkdir(exist_ok=True)
        for ps in sets:
            if ps.get("units") and unit not in ps["units"]:
                continue
            t0 = time.perf_counter()
            rgb = render_set(ps, codes, bakes, unit, luts, dng_path)
            ms = (time.perf_counter() - t0) * 1000
            Image.fromarray(rgb, "RGB").save(out / f"{ps['id']}.png", compress_level=1)
            # 同一组参数，但输入码值先量化成 float16（与显卡代理图相同），用来区分误差来源
            Image.fromarray(render_set(ps, codes16, bakes, unit, luts, dng_path), "RGB").save(out / f"{ps['id']}.f16in.png", compress_level=1)
            if ps.get("lut") and luts[ps["lut"]]["input_space"] in spaces.DISPLAY:
                Image.fromarray(render_set(ps, codes, bakes, unit, luts, dng_path, jpeg_base=True), "RGB").save(out / f"{ps['id']}.jpegbase.png", compress_level=1)
            timings[f"{name}/{ps['id']}"] = ms
            print(name, ps["id"], rgb.shape, f"{ms:.0f} ms", flush=True)
    (data / "ref_timings.json").write_text(json.dumps(timings, indent=1))


if __name__ == "__main__":
    main()
