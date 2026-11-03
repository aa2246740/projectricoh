"""服务器端烘焙：只读调用 studio/src/gxr_studio 的现有函数，为显卡预览准备数据。

每张 DNG 产出（全部写到 scratch 的数据目录，不进仓库；配方表和第三方 LUT 是本机私有数据）：
  proxy.f16      半分辨率白平衡码值（与现有预览同一份 `half_res_codes` + 转正），RGBA float16，A=0
  meta.json      尺寸、方向、单元、ISO、RAW 条带位置（给显卡去马赛克用）、烘焙计时
  rec_<slot>_<p|x>.bin  配方烘焙：一维曲线 pre(4096×3) + 矩阵(9) + 偏移(3) + 色度增益网格(ny×nx×2)，float32
另外（与照片无关）：
  lut_<name>.bin  第三方 .cube 的 3D 表（float32，R 最快），以及输入/输出空间

用法：
  studio/.venv/bin/python research/studio_gpu_r1/proto/bake.py <home> <out_dir> <unit:dng> [<unit:dng> ...]
     [--lut name=space_in:space_out:path.cube ...]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "studio/src"))

from gxr_studio.camdata import calib  # noqa: E402
from gxr_studio.lut.cube import Cube  # noqa: E402
from gxr_studio.raw import half_res_codes, open_dng, orient_array  # noqa: E402
from gxr_studio.raw.codes import wb_gains  # noqa: E402
from gxr_studio.render import chain  # noqa: E402
from gxr_studio.render.params import RecipeSel  # noqa: E402
from gxr_studio.render.recipes import CameraData  # noqa: E402
from gxr_studio.render.service import EXPORT_STEP, ISO_SPLIT, PREVIEW_STEP  # noqa: E402

SLOTS = range(1, 9)


def write_bake(path: Path, bk: chain.ChromaBake) -> dict:
    ny, nx = bk.gain.shape[:2]
    arr = np.concatenate([bk.pre.reshape(-1), bk.matrix.reshape(-1), bk.offset.reshape(-1), bk.gain.reshape(-1)]).astype("<f4")
    path.write_bytes(arr.tobytes())
    return {"file": path.name, "nx": nx, "ny": ny, "origin": list(bk.origin), "step": bk.step, "floats": int(arr.size)}


def bake_photo(home: Path, out: Path, unit: str, dng_path: Path, cam: CameraData, models: dict) -> dict:
    t = {}
    t0 = time.perf_counter()
    data = dng_path.read_bytes()
    t["read_file_ms"] = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    dng = open_dng(data, dng_path.name)  # TIFF 解析 + 全文件 SHA-256
    t["parse_tiff_sha_ms"] = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    dng.mosaic()  # 12 位拆包
    t["unpack_12bit_ms"] = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    codes = half_res_codes(dng)  # 归一化 + 白平衡 + 2×2 合并（现有预览路径，不做去马赛克）
    t["half_res_codes_ms"] = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    codes = np.ascontiguousarray(orient_array(codes, dng.orientation), np.float32)
    t["orient_ms"] = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    h, w = codes.shape[:2]
    rgba = np.zeros((h, w, 4), np.float16)
    rgba[..., :3] = codes
    name = dng_path.stem
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "proxy.f16").write_bytes(rgba.astype("<f2").tobytes())
    np.save(d / "proxy_f32.npy", codes)  # Python 参考渲染用同一份码值
    t["proxy_f16_write_ms"] = (time.perf_counter() - t0) * 1000

    # RAW 条带布局（显卡去马赛克直接吃文件里的 12 位打包字节）
    offs, cnts = dng._strips
    y0, x0, ch, cw = dng.crop_window()
    raw = {
        "file": str(dng_path),
        "width": dng.width,
        "height": dng.height,
        "bps": dng.bps,
        "strip_offsets": [int(v) for v in offs],
        "strip_counts": [int(v) for v in cnts],
        "row_bytes": (dng.width * dng.bps + 7) // 8,
        "crop": [int(y0), int(x0), int(ch), int(cw)],
        "active": list(dng.active),
        "cfa": dng.cfa.tolist(),
        "phase": dng.crop_cfa_phase().tolist(),
        "black_pattern": dng.black_pattern.tolist(),
        "black_dh": None if dng.black_dh is None else "present",
        "black_dv": None if dng.black_dv is None else "present",
        "lin_table": None if dng.lin_table is None else "present",
        "white": dng.white,
        "wb_gains": wb_gains(dng).tolist(),
        "orientation": dng.orientation,
        "file_bytes": len(data),
        "strip_bytes": int(sum(cnts)),
    }
    iso = int(dng.exif.get("iso") or 200)
    model_iso = 1600 if iso >= ISO_SPLIT else 200
    model = models.setdefault(model_iso, calib.model_for(home, model_iso)[0])
    recipes = {}
    bake_ms = []
    for slot in SLOTS:
        res = cam.resolve(RecipeSel(unit, slot))
        for tag, step in (("p", PREVIEW_STEP), ("x", EXPORT_STEP)):
            t0 = time.perf_counter()
            bk = chain.bake_chroma(model, res.entry, step)
            ms = (time.perf_counter() - t0) * 1000
            if tag == "p":
                bake_ms.append(ms)
            info = write_bake(d / f"rec_{slot}_{tag}.bin", bk)
            info["bake_ms"] = ms
            recipes[f"{slot}_{tag}"] = info
    t["bake_one_recipe_preview_ms_each"] = bake_ms
    dng.release()
    meta = {"name": name, "unit": unit, "iso": iso, "model_iso": model_iso, "w": w, "h": h, "raw": raw, "recipes": recipes, "timing": t}
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    return meta


def bake_lut(out: Path, name: str, spec: str) -> dict:
    sin, sout, path = spec.split(":", 2)
    t0 = time.perf_counter()
    cube = Cube.read(path)
    parse_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    t3 = np.asarray(cube.table3, "<f4")
    n = t3.shape[0]
    rgba = np.zeros((n, n, n, 4), "<f4")
    rgba[..., :3] = t3
    (out / f"lut_{name}.bin").write_bytes(rgba.tobytes())
    write_ms = (time.perf_counter() - t0) * 1000
    info = {
        "name": name,
        "file": f"lut_{name}.bin",
        "n": n,
        "input_space": sin,
        "output_space": sout,
        "domain_min": np.asarray(cube.domain_min, float).tolist(),
        "domain_max": np.asarray(cube.domain_max, float).tolist(),
        "range3": list(map(float, cube.range3)),
        "has_1d": cube.table1 is not None,
        "path": path,
        "parse_ms": parse_ms,
        "texture_write_ms": write_ms,
    }
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("home")
    ap.add_argument("out")
    ap.add_argument("photos", nargs="+", help="unit:path.DNG")
    ap.add_argument("--lut", action="append", default=[], help="name=in:out:path.cube")
    a = ap.parse_args()
    home, out = Path(a.home), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cam = CameraData(home)
    models: dict = {}
    index = {"photos": [], "luts": []}
    for spec in a.photos:
        unit, path = spec.split(":", 1)
        meta = bake_photo(home, out, unit, Path(path), cam, models)
        index["photos"].append({"name": meta["name"], "unit": unit, "iso": meta["iso"], "w": meta["w"], "h": meta["h"]})
        print(meta["name"], json.dumps({k: (round(v, 1) if isinstance(v, float) else [round(x) for x in v]) for k, v in meta["timing"].items()}))
    for spec in a.lut:
        name, rest = spec.split("=", 1)
        info = bake_lut(out, name, rest)
        index["luts"].append(info)
        print("lut", name, info["n"], round(info["parse_ms"], 1), "ms")
    (out / "index.json").write_text(json.dumps(index, indent=1))


if __name__ == "__main__":
    main()
