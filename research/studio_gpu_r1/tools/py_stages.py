"""Python 后台各环节实测（只读调用 studio/src/gxr_studio），并生成全尺寸导出的 Python 参考图。

  1. 冷打开：读文件 / TIFF+SHA / 12 位拆包 / 半分辨率码值 / 转正 / 存 float16 代理（每张 3 次，新对象）
  2. 烘焙：一个配方（预览 0.75、导出 0.5 网格），一个 .cube
  3. 全尺寸导出：去马赛克 + 配方链 / apply_extra / JPEG q95 编码（与 finish.serve.export_finish 同一组函数）
  4. 阻塞：后台批量生成代理图时，前台"读缓存代理"请求的延迟：无后台 / 同进程线程 / 进程池

用法：studio/.venv/bin/python py_stages.py <home> <gpudata> <输出 JSON> [--skip-refs]
"""

from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "studio/src"))

from gxr_studio.camdata import calib  # noqa: E402
from gxr_studio.finish.compose import encode_jpeg  # noqa: E402
from gxr_studio.finish.pixels import apply_base, apply_extra  # noqa: E402
from gxr_studio.lut import spaces  # noqa: E402
from gxr_studio.lut.cube import Cube  # noqa: E402
from gxr_studio.lut.photo import _apply  # noqa: E402
from gxr_studio.raw import Renderer, demosaic_full, half_res_codes, open_dng, orient_array, render_full  # noqa: E402
from gxr_studio.render import chain  # noqa: E402
from gxr_studio.render.params import RecipeSel, parse_adjust, parse_curve  # noqa: E402
from gxr_studio.render.recipes import CameraData  # noqa: E402
from gxr_studio.render.service import EXPORT_STEP, PREVIEW_STEP  # noqa: E402
from gxr_studio.render.tones import channel_gains, display_table  # noqa: E402

HERE = Path(__file__).resolve().parent


def ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)


def make_proxy(path: str) -> int:
    """后台任务：一张 DNG → float16 代理（与 bake.py 同一组函数），返回字节数。"""
    dng = open_dng(path)
    codes = np.ascontiguousarray(orient_array(half_res_codes(dng), dng.orientation), np.float32)
    rgba = np.zeros((*codes.shape[:2], 4), np.float16)
    rgba[..., :3] = codes
    dng.release()
    return rgba.nbytes


def cold_open(path: str) -> dict:
    t = {}
    t0 = time.perf_counter()
    data = Path(path).read_bytes()
    t["read_file"] = ms(t0)
    t0 = time.perf_counter()
    dng = open_dng(data, Path(path).name)
    t["parse_tiff_and_sha256"] = ms(t0)
    t0 = time.perf_counter()
    dng.mosaic()
    t["unpack_12bit"] = ms(t0)
    t0 = time.perf_counter()
    codes = half_res_codes(dng)
    t["half_res_codes"] = ms(t0)
    t0 = time.perf_counter()
    codes = np.ascontiguousarray(orient_array(codes, dng.orientation), np.float32)
    rgba = np.zeros((*codes.shape[:2], 4), np.float16)
    rgba[..., :3] = codes
    t["orient_and_to_float16"] = ms(t0)
    t0 = time.perf_counter()
    full = demosaic_full(dng)
    t["demosaic_full_mhc"] = ms(t0)
    del full
    dng.release()
    t["proxy_ready_total"] = round(t["read_file"] + t["parse_tiff_and_sha256"] + t["unpack_12bit"] + t["half_res_codes"] + t["orient_and_to_float16"], 1)
    return t


def export_full(path: str, model, entry: bytes, ps: dict, luts: dict) -> tuple[dict, np.ndarray]:
    t = {}
    adjust = parse_adjust(ps.get("adjust") or {})
    master = parse_curve({"master": ps["curve"]}) if ps.get("curve") else None
    t0 = time.perf_counter()
    bk = chain.bake_chroma(model, entry, EXPORT_STEP)
    t["bake_export_grid"] = ms(t0)
    lut = ps.get("lut")
    gains, table = (None, None) if lut else (channel_gains(adjust), display_table(adjust, master))
    renderer = Renderer("x", "x", "", False, lambda codes: chain.chroma_u8(codes, bk, gains, table))
    t0 = time.perf_counter()
    dng = open_dng(path)
    rgb = render_full(dng, renderer)  # 拆包 + 白平衡 + MHC 去马赛克 + 配方链（条带）
    dng.release()
    t["read_demosaic_and_recipe_chain"] = ms(t0)
    if lut:
        info = luts[lut]
        target = spaces.Target(Cube.read(str(REPO / info["path"])), info["input_space"], info["output_space"])
        t0 = time.perf_counter()
        rgb = _apply(target, rgb)
        t["lut_tetrahedral"] = ms(t0)
        t0 = time.perf_counter()
        rgb = apply_base(rgb, adjust, master)
        t["apply_base"] = ms(t0)
    t0 = time.perf_counter()
    rgb = apply_extra(rgb, adjust)
    t["apply_extra"] = ms(t0)
    t0 = time.perf_counter()
    jpeg = encode_jpeg(rgb, 95)
    t["jpeg_q95_encode"] = ms(t0)
    t["jpeg_bytes"] = len(jpeg)
    t["total"] = round(sum(v for k, v in t.items() if k not in ("jpeg_bytes", "bake_export_grid")), 1)
    return t, rgb


LISTING = [{"id": f"{i:016x}", "name": f"R80{i:05d}", "lens": "GR LENS A12 50mm F2.5 MACRO", "iso": 200, "files": {"dng": {"relpath": f"2026/11/02/R80{i:05d}.DNG", "sha256": "0" * 64}}} for i in range(1500)]


def foreground_probe(proxy_files: list[Path], seconds: float, stop=None) -> list[float]:
    """前台：每 50 ms 一个请求 = 生成 1500 张照片的列表 JSON（纯 Python，要拿 GIL）+ 读一张缓存代理图（24 MB），记延迟。
    `stop` 给了的话，跑到后台任务全部结束为止（至少 seconds）。"""
    lat = []
    end = time.perf_counter() + seconds
    i = 0
    while time.perf_counter() < end or (stop is not None and not all(f.done() for f in stop)):
        t0 = time.perf_counter()
        _ = json.dumps(LISTING)
        buf = proxy_files[i % len(proxy_files)].read_bytes()
        _ = np.frombuffer(buf, np.uint8)[:: 1 << 16].sum()
        lat.append((time.perf_counter() - t0) * 1000)
        i += 1
        rest = 0.05 - (time.perf_counter() - t0)
        if rest > 0:
            time.sleep(rest)  # 前台请求的节拍，不是轮询
    return lat


def pstats(xs: list[float]) -> dict:
    a = np.asarray(xs)
    return {"n": len(a), "p50": round(float(np.percentile(a, 50)), 1), "p95": round(float(np.percentile(a, 95)), 1), "max": round(float(a.max()), 1)}


def blocking(paths: list[str], proxy_files: list[Path]) -> dict:
    out = {"no_background": pstats(foreground_probe(proxy_files, 3.0))}
    for kind, pool_cls in (("threads_same_process", ThreadPoolExecutor), ("process_pool", ProcessPoolExecutor)):
        with pool_cls(max_workers=3) as pool:
            if kind == "process_pool":
                list(pool.map(int, range(3)))  # 先把子进程拉起来，不计入
            t0 = time.perf_counter()
            futs = [pool.submit(make_proxy, p) for p in paths * 4]
            lat = foreground_probe(proxy_files, 1.0, stop=futs)
            for f in futs:
                f.result()
            out[kind] = {**pstats(lat), "background_proxies": len(futs), "background_wall_ms": ms(t0)}
    return out


def main() -> None:
    home, data, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    skip_refs = "--skip-refs" in sys.argv
    if "--blocking-only" in sys.argv:
        index = json.loads((data / "index.json").read_text())
        paths = [str(REPO / json.loads((data / p["name"] / "meta.json").read_text())["raw"]["file"]) for p in index["photos"]]
        res = {"when": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "blocking": blocking(paths, [data / p["name"] / "proxy.f16" for p in index["photos"]])}
        print(res, flush=True)
        out.write_text(json.dumps(res, indent=1))
        return
    index = json.loads((data / "index.json").read_text())
    luts = {x["name"]: x for x in index["luts"]}
    sets = {s["id"]: s for s in json.loads((HERE.parent / "proto/paramsets.json").read_text())}
    cam = CameraData(home)
    res: dict = {"when": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "cold_open": {}, "bake": {}, "export": {}}
    photos = {p["name"]: p for p in index["photos"]}
    paths = {n: str(REPO / json.loads((data / n / "meta.json").read_text())["raw"]["file"]) for n in photos}

    for n in ("R8051410", "R8051691"):
        res["cold_open"][n] = [cold_open(paths[n]) for _ in range(3)]
        print("cold", n, res["cold_open"][n][-1], flush=True)

    model200 = calib.model_for(home, 200)[0]
    entry = cam.resolve(RecipeSel("jlaunch", 1)).entry
    for tag, step in (("preview_0.75", PREVIEW_STEP), ("export_0.5", EXPORT_STEP)):
        t = []
        for _ in range(3):
            t0 = time.perf_counter()
            chain.bake_chroma(model200, entry, step)
            t.append(ms(t0))
        res["bake"][f"recipe_{tag}"] = t
    t0 = time.perf_counter()
    entry_k = cam.resolve(RecipeSel("jlaunch", 1, (("contrast", 3), ("saturation", -2)))).entry
    chain.bake_chroma(model200, entry_k, PREVIEW_STEP)
    res["bake"]["recipe_knob_change_resolve_and_bake"] = ms(t0)
    for name, info in luts.items():
        t0 = time.perf_counter()
        Cube.read(str(REPO / info["path"]))
        res["bake"][f"cube_parse_{name}_{info['n']}"] = ms(t0)
    print("bake", res["bake"], flush=True)

    if not skip_refs:
        for n in ("R8051410", "R8051691"):
            unit = photos[n]["unit"]
            meta = json.loads((data / n / "meta.json").read_text())
            model = calib.model_for(home, meta["model_iso"])[0]
            (data / n / "ref_full").mkdir(exist_ok=True)
            for sid in ("s1_recipe01", "s2_recipe02_tone", "s3_recipe04_curve_extra", "s5_lut_display"):
                ps = sets[sid]
                e = cam.resolve(RecipeSel(unit, ps["recipe"])).entry
                t, rgb = export_full(paths[n], model, e, ps, luts)
                Image.fromarray(rgb, "RGB").save(data / n / "ref_full" / f"{sid}.png", compress_level=1)
                res["export"][f"{n}/{sid}"] = t
                print("export", n, sid, t, flush=True)

    proxy_files = [data / n / "proxy.f16" for n in photos]
    res["blocking"] = blocking(list(paths.values()), proxy_files)
    print("blocking", res["blocking"], flush=True)
    out.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
