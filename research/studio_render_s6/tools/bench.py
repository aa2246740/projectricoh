"""S6 基准：烘焙误差、预览延迟、全分辨率导出耗时、半分辨率 vs 去马赛克、相机 JPG 对照（诊断）。

理光字节现场提取到临时目录（`make_home.py` 同样的做法）；结果写 bench.json，数字抄进 REPORT.md。
用法：python bench.py <输出 json> [--quick]
"""

from __future__ import annotations

import json
import platform
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "studio/src"))
sys.path.insert(0, str(REPO / "studio/tests"))

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

import e0_support as t  # noqa: E402
from gxr_studio.app import create_app  # noqa: E402
from gxr_studio.camdata import calib, store  # noqa: E402
from gxr_studio.config import Settings  # noqa: E402
from gxr_studio.devtools.synthetic_card import make_card  # noqa: E402
from gxr_studio.engine import colour  # noqa: E402
from gxr_studio.engine.model import synthetic  # noqa: E402
from gxr_studio.raw import demosaic_full, half_res_codes, open_dng  # noqa: E402
from gxr_studio.render import chain, tones  # noqa: E402
from gxr_studio.render.params import parse_adjust  # noqa: E402

SAMPLES = REPO / "captures/a12-50/2026-10-19/stage2c-first-run"
QUICK = "--quick" in sys.argv


def de(a, b):
    return colour.delta_e00(colour.lab_from_codes(a), colour.lab_from_codes(b))


def pct(v, qs=(50, 90, 99, 99.9)):
    return {f"p{q}": round(float(np.percentile(v, q)), 4) for q in qs} | {"max": round(float(np.max(v)), 4)}


def stats_ms(v):
    v = sorted(v)
    return {"n": len(v), "p50": round(statistics.median(v), 1), "p95": round(v[min(len(v) - 1, int(0.95 * len(v)))], 1),
            "max": round(v[-1], 1)}


def pixels():
    out = []
    for n in (44, 45, 46, 47):
        out.append(half_res_codes(open_dng(SAMPLES / f"R80511{n}.DNG")).reshape(-1, 3)[::40])
    for s in t.SCENES:
        with np.load(t.SCENE_DIR / f"{s}_input.npz") as z:
            out.append(z["x"].copy())
    out.append(synthetic())
    return np.concatenate(out)


def bake_error(home, model, entries):
    x = pixels()
    res = {"pixels": int(len(x)), "methods": {}}
    refs = {k: chain.exact_float(model, e, x, None, None) for k, e in entries.items()}
    methods = {
        "chroma step 1.0": lambda e: chain.chroma_float(x, chain.bake_chroma(model, e, 1.0), None, None),
        "chroma step 0.75 (preview)": lambda e: chain.chroma_float(x, chain.bake_chroma(model, e, 0.75), None, None),
        "chroma step 0.5 (export)": lambda e: chain.chroma_float(x, chain.bake_chroma(model, e, 0.5), None, None),
    }
    for grid in (33, 49, 65):
        def run3(e, grid=grid):
            b = chain.bake_model(model, e, grid)
            return chain.apply_baked_float(x, b, b.folded(None), None)
        methods[f"lut3d {grid}^3 tetrahedral"] = run3
    for name, fn in methods.items():
        if QUICK and "65" in name:
            continue
        worst = {"p99": 0.0, "p99.9": 0.0, "max": 0.0, "code": 0, "flip_frac": 0.0}
        per = []
        for key, e in entries.items():
            got = fn(e)
            d = de(refs[key], got)
            qa, qb = chain.quantize(refs[key]).astype(int), chain.quantize(got).astype(int)
            dq = de(chain.quantize(refs[key]), chain.quantize(got))
            m = {"p99": float(np.percentile(d, 99)), "p99.9": float(np.percentile(d, 99.9)), "max": float(d.max()),
                 "code": int(np.abs(qa - qb).max()), "flip_frac": float((qa != qb).any(axis=1).mean()),
                 "q_p99": float(np.percentile(dq, 99))}
            per.append((key, m))
            for k in ("p99", "p99.9", "max", "code", "flip_frac"):
                worst[k] = max(worst[k], m[k])
        worst["q_p99"] = max(m["q_p99"] for _, m in per)
        res["methods"][name] = {k: round(v, 4) for k, v in worst.items()}
        res["methods"][name]["worst_recipe_p99"] = max(per, key=lambda kv: kv[1]["p99"])[0]
        print(name, res["methods"][name], flush=True)
    # 带曝光/白平衡/调子/曲线的同一组比较（预览网格）
    g = tones.channel_gains(parse_adjust({"exposure_ev": -0.7, "wb": {"warm": 40, "tint": -20}}))
    tab = tones.display_table(parse_adjust({"contrast": 30, "shadow": 40, "highlight": -30}), ((0, 0), (80, 70), (255, 255)))
    worst = 0.0
    for key, e in entries.items():
        ref = chain.exact_float(model, e, x, g, tab)
        got = chain.chroma_float(x, chain.bake_chroma(model, e, 0.75), g, tab)
        worst = max(worst, float(np.percentile(de(ref, got), 99)))
    res["with_adjustments_preview_grid_worst_p99"] = round(worst, 4)
    return res


def numerics_vs_exact_image(model, entry):
    """一整张半分辨率图（3.05 MP）：烘焙 vs 精确链，默认参数。"""
    codes = half_res_codes(open_dng(SAMPLES / "R8051144.DNG"))
    t0 = time.perf_counter()
    exact = chain.exact_u8(model, entry, codes, None, None)
    t_exact = time.perf_counter() - t0
    ref = model.predict(entry, codes.reshape(-1, 3), quantize=True).reshape(codes.shape) if not QUICK else exact
    bk = chain.bake_chroma(model, entry, 0.75)
    baked = chain.chroma_u8(codes, bk, None, None)
    d = de(exact.reshape(-1, 3), baked.reshape(-1, 3))
    return {"pixels": int(codes.shape[0] * codes.shape[1]), "exact_chain_seconds": round(t_exact, 1),
            "exact_equals_E0_predict_bytes": bool(np.array_equal(exact, ref)),
            "baked_vs_exact_quantized_dE00": pct(d), "baked_vs_exact_max_code_diff": int(np.abs(exact.astype(int) - baked.astype(int)).max()),
            "baked_vs_exact_pixels_differing": round(float((exact != baked).any(axis=2).mean()), 4)}


def demosaic_vs_half(model, entry):
    """ARCHITECTURE U3：半分辨率合并路径 vs 全分辨率去马赛克后缩小，经同一条配方链后的 ΔE00。"""
    dng = open_dng(SAMPLES / "R8051144.DNG")
    half = half_res_codes(dng)
    full = demosaic_full(dng)
    h, w = half.shape[:2]
    down = full[:2 * h, :2 * w].reshape(h, 2, w, 2, 3).mean(axis=(1, 3))
    bk = chain.bake_chroma(model, entry, 0.5)
    a, b = chain.chroma_float(half, bk, None, None), chain.chroma_float(down, bk, None, None)
    d = de(a, b)
    # 只看平坦区（局部码值变化小）：去马赛克与合并在高频边缘上本来就不同
    flat = np.abs(half - np.roll(half, 1, axis=1)).max(axis=2).reshape(-1) < 40
    return {"all_pixels": pct(d, (50, 90, 99)), "flat_pixels": pct(d[flat], (50, 90, 99)), "flat_fraction": round(float(flat.mean()), 3)}


def camera_jpg_diagnostic(model, cam_entry):
    """诊断，不是验收：04 电脑模拟 vs 相机 JPG（配方槽位和 ISO 标定未知；样本 ISO 400/500 都是未标定）。"""
    out = []
    bk = chain.bake_chroma(model, cam_entry, 0.5)
    for n in (44, 45, 46, 47):
        dng = open_dng(SAMPLES / f"R80511{n}.DNG")
        half = half_res_codes(dng)
        mine = chain.chroma_u8(half, bk, None, None)
        jpg = Image.open(SAMPLES / f"R80511{n}.JPG").convert("RGB").resize((half.shape[1], half.shape[0]), Image.Resampling.BOX)
        d = de(mine.reshape(-1, 3), np.asarray(jpg).reshape(-1, 3))
        out.append({"frame": f"R80511{n}", "iso": dng.exif.get("iso"), "dE00": pct(d, (50, 90))})
    return out


def latency(home, tmp):
    vol = tmp / "volumes"
    vol.mkdir()
    make_card(vol)
    h2 = tmp / "home2"
    shutil.copytree(home, h2)
    s = Settings(library_dir=tmp / "lib", home_dir=h2, export_dir=tmp / "exp", volumes_roots=(vol,), token="t", port=8765,
                 min_free_bytes=0)
    app = create_app(s)
    res = {}
    with TestClient(app, base_url="http://127.0.0.1:8765", headers={"X-GXR-Token": "t"}) as c:
        cid = c.get("/api/cards").json()[0]["id"]
        job = c.post("/api/import", json={"card_id": cid}).json()
        while c.get(f"/api/jobs/{job['id']}").json()["running"]:
            time.sleep(0.1)
        p = next(x for x in c.get("/api/photos").json() if x["name"] == "R8051144")
        url = f"/api/photos/{p['id']}/render"
        svc = app.state.ctx.render
        c.get(url)  # 解码 + 第一次烘焙（冷启动单独记）

        def run(label, bodies, n):
            ts = []
            for body in bodies[:n]:
                t0 = time.perf_counter()
                r = c.post(url, json=body)
                assert r.status_code == 200, r.text
                ts.append((time.perf_counter() - t0) * 1000)
            res[label] = stats_ms(ts)
            print(label, res[label], flush=True)

        N = 12 if QUICK else 40
        run("exposure slider (HTTP, half-res 2144x1424)", [{"adjust": {"exposure_ev": round(-2 + 0.1 * i, 2)}} for i in range(N)], N)
        run("white balance slider", [{"adjust": {"wb": {"warm": i - N // 2}}} for i in range(N)], N)
        run("curve / tone slider", [{"adjust": {"contrast": i - N // 2, "shadow": i}, "curve": {"master": [[0, 0], [100 + i, 90], [255, 255]]}}
                                    for i in range(N)], N)
        # 旋钮：每次换一个没算过的条目（档位组合不重复），要重新烘焙
        combos = [{"recipe": {"unit": "jlaunch", "slot": 1, "levels": {"contrast": a, "highlight": b, "shadow": (a + b) % 9 - 4}}}
                  for a in range(-9, 10) for b in range(-9, 10)]
        run("knob change (new entry each time, rebake)", combos, N)
        run("recipe switch (8 slots x 3 units)", [{"recipe": {"unit": "jlaunch", "slot": 1 + i % 8, "levels": {"contrast": 1 + i // 8}}}
                                                   for i in range(N)], N)
        # 同一组参数再来一遍：结果缓存
        same = {"adjust": {"exposure_ev": 0.25}}
        c.post(url, json=same)
        ts = []
        for _ in range(N):
            t0 = time.perf_counter()
            c.post(url, json=same)
            ts.append((time.perf_counter() - t0) * 1000)
        res["same params again (result cache)"] = stats_ms(ts)
        # 拖动期更小的预览
        ts = []
        for i in range(N):
            t0 = time.perf_counter()
            c.post(url, json={"adjust": {"exposure_ev": 0.01 * i}}, params={"max_edge": 800})
            ts.append((time.perf_counter() - t0) * 1000)
        res["exposure slider at max_edge=800"] = stats_ms(ts)
        # 服务内部耗时拆分（无 HTTP）
        shot = svc.lib.get_shot(p["id"])
        from gxr_studio.render.params import EditState, RecipeSel
        parts = {"decode": [], "bake": [], "apply": [], "encode": []}
        for i in range(10 if QUICK else 20):
            out = svc.render_preview(shot, EditState(RecipeSel("jlaunch", 2, (("saturation", i % 7 - 3), ("contrast", i % 5))),
                                                     parse_adjust({}), None))
            for k in parts:
                parts[k].append(out.ms.get(k, 0.0))
        res["service breakdown, knob change (ms, median)"] = {k: round(statistics.median(v), 1) for k, v in parts.items()}
        # 全分辨率导出
        t0 = time.perf_counter()
        r = c.post(f"/api/photos/{p['id']}/export", json={"size": "original", "source": "recipe"})
        res["export full-res 4288x2848 baked step 0.5 (s)"] = round(time.perf_counter() - t0, 2)
        assert r.status_code == 200
        t0 = time.perf_counter()
        r = c.post(f"/api/photos/{p['id']}/export", json={"size": "original", "source": "recipe", "format": "png"})
        res["export full-res PNG (s)"] = round(time.perf_counter() - t0, 2)
        if not QUICK:
            t0 = time.perf_counter()
            r = c.post(f"/api/photos/{p['id']}/export", json={"size": "original", "source": "recipe", "precise": True})
            res["export full-res exact chain (s)"] = round(time.perf_counter() - t0, 1)
            assert r.status_code == 200
    return res


def main(out_path: str):
    tmp = Path(tempfile.mkdtemp(prefix="s6-bench-"))
    home = tmp / "home"
    home.mkdir()
    store.import_from_dat(t.fixture_dat(127), home)
    calib.import_calibration(home, calib.dev_sources(REPO))
    model = calib.model_for(home, 200)[0]
    entries = {f"{u}/{s:02d}": store.load_entry(home, u, s) for u in range(3) for s in range(1, 9)}
    result = {"machine": {"platform": platform.platform(), "python": platform.python_version(),
                          "processor": platform.processor(), "workers": chain.WORKERS},
              "note": "单次实测，不是基准承诺；脚本 research/studio_render_s6/tools/bench.py"}
    result["bake_error"] = bake_error(home, model, entries)
    result["default_params_full_half_res_image"] = numerics_vs_exact_image(model, entries["0/04"])
    result["demosaic_vs_half_res"] = demosaic_vs_half(model, entries["0/04"])
    result["camera_jpg_diagnostic"] = camera_jpg_diagnostic(model, entries["0/04"])
    result["latency"] = latency(home, tmp)
    Path(out_path).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1])
