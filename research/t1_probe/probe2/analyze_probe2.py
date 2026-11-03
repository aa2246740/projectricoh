#!/usr/bin/env python3
"""Score 04a/08/04b JPEG+DNG captures. Writes only authorized local outputs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sp = importlib.util.spec_from_file_location("t1p2_model", Path(__file__).with_name("model_probe2.py"))
m = importlib.util.module_from_spec(sp)
sp.loader.exec_module(m)
p = m.p
import numpy as np
from PIL import Image


def pair_path(path):
    jpg = Path(path).resolve()
    p.require(jpg.suffix.lower() in (".jpg", ".jpeg"), f"expected JPEG: {jpg}")
    p.require(not str(jpg).startswith("/Volumes/") or jpg.is_relative_to(Path("/Volumes/Workspace")),
              "input on another /Volumes path is forbidden")
    dngs = [q for q in (jpg.with_suffix(".DNG"), jpg.with_suffix(".dng")) if q.is_file()]
    p.require(dngs and jpg.is_file(), f"an adjacent DNG is required: {jpg}")
    p.require(all(q.samefile(dngs[0]) for q in dngs), f"ambiguous adjacent DNGs: {jpg}")
    return jpg, dngs[0]


def output_path(path=None):
    output = Path(path or p.LOCAL / "analysis/latest").resolve()
    p.require(any(output.is_relative_to(root.resolve()) for root in (p.LOCAL, p.SCRATCH)),
              "analysis output must be under probe2/local or /tmp/t1p2")
    return output


def clipping_255(rgb, geometry, layout, ar):
    pixels, clipped = 0, 0
    channels = np.zeros(3, dtype=np.int64)
    for patch in layout["patches"]:
        if patch["group"] != "gray" and not patch["ring"]:
            continue
        x0, y0, x1, y1 = patch["bbox_px"]
        ya, yb, xa, xb, mask, _ = ar.roi_mask(
            geometry, [x0 + 40, y0 + 40, x1 - 40, y1 - 40], rgb.shape)
        saturated = rgb[ya:yb, xa:xb][mask] == 255
        pixels += len(saturated)
        clipped += int(np.any(saturated, axis=1).sum())
        channels += saturated.sum(axis=0)
    return {"ROI_pixels": pixels, "any_channel_pixels": clipped,
            "per_channel_pixels_RGB": channels.tolist(), "fraction": clipped / pixels,
            "threshold": .005, "warning": clipped / pixels > .005,
            "scope": "144 ring and 9 grey patch ROIs, inset 40; whites excluded; each pixel counted once"}


def extract(path, ar, layout, seed_H=None):
    jpg, dng = pair_path(path)
    hashes = {"JPEG": p.sha(jpg), "DNG": p.sha(dng)}
    seed_digest = "" if seed_H is None else hashlib.sha256(np.asarray(seed_H).tobytes()).hexdigest()
    key = hashlib.sha256((hashes["JPEG"] + hashes["DNG"] + seed_digest + p.sha(Path(__file__)) +
                          p.sha(p.HERE / "calibration_geometry.py") +
                          p.sha(p.ROOT / "research/hue_ring/analyze_ring.py")).encode()).hexdigest()
    cache = p.LOCAL / "frame_cache" / f"{key}.json"
    if cache.exists():
        frame = json.loads(cache.read_text())
        frame["JPEG"], frame["DNG"] = str(jpg), str(dng)
        return frame
    jm = ar.read_meta(jpg, None, None)
    dm = ar.read_meta(jpg, dng, None)
    errors = [f"{label}: {meta[k]}" for label, meta in (("JPEG", jm), ("DNG", dm))
              for k in ("exif_error", "makernote_error") if k in meta]
    fields = ("program", "exposure_mode", "t", "f", "iso", "wb_exif", "selector",
              "wb_record_0x26", "display", "raw13", "when")
    errors += [f"JPEG/DNG {k} mismatch" for k in fields if jm.get(k) != dm.get(k)]
    rgb = np.asarray(Image.open(jpg).convert("RGB"))
    try:
        geometry = ar.locate_screen(rgb, layout)
    except ValueError:
        locator = p.load("t1p2_calibration_geometry", p.HERE / "calibration_geometry.py")
        try:
            geometry = locator.locate(ar, rgb, layout, seed_H)
        except ValueError:
            if seed_H is None:
                raise
            geometry = locator.locate(ar, rgb, layout)
    s = ar.s2d()
    crop, black, white, neutral, rawinfo = s.decode_raw(s.Tiff(dng.read_bytes()))
    p.require(crop.shape == rgb.shape[:2], f"DNG/JPEG geometry differs for {jpg.name}")
    raw = (crop, black, white, np.array(neutral), tuple(rawinfo["crop_origin_xy"]))
    patches = ar.sample_frame(rgb, geometry, layout, 40, raw)
    p.require(len(patches) == 155 and all(q["ok"] and "cam_wb" in q for q in patches),
              "missing JPEG or RAW patch")
    frame = {"JPEG": str(jpg), "DNG": str(dng), "hashes": hashes, "meta": dm,
             "metadata_errors": errors, "rgb": [q["rgb_trim"] for q in patches],
             "cam_wb": [q["cam_wb"] for q in patches], "patches": patches,
             "clipping_255": clipping_255(rgb, geometry, layout, ar),
             "geometry": {k: v for k, v in geometry.items() if k not in ("H", "Hinv")},
             "H": geometry["H"]}
    p.dump(cache, frame)
    return p.jsonable(frame)


def metadata_checks(frames):
    errors = [f"frame {i + 1}: {e}" for i, f in enumerate(frames) for e in f["metadata_errors"]]
    warnings = []
    warned_settings = set()
    metas = [f["meta"] for f in frames]
    first = metas[0]
    for i, meta in enumerate(metas):
        expected = {"program": 1, "exposure_mode": 1, "iso": 200, "wb_exif": 1,
                    "wb_record_0x26": 5, "selector": 1}
        errors += [f"frame {i + 1}: {k}={meta.get(k)}; expected {v}"
                   for k, v in expected.items() if meta.get(k) != v]
        for k, v in (("t", 1 / 60), ("f", 4.0)):
            value = meta.get(k)
            if not isinstance(value, (int, float)) or not np.isfinite(value) or value <= 0:
                errors.append(f"frame {i + 1}: {k} missing or invalid")
            elif not np.isclose(value, v, rtol=1e-5, atol=1e-8) and (k, value) not in warned_settings:
                warnings.append(f"曝光设置 {k}={value:g} 与标定值 {v:g} 不同，仅作提示")
                warned_settings.add((k, value))
        for k in ("program", "exposure_mode", "t", "f", "iso", "wb_exif", "wb_record_0x26", "display", "raw13"):
            if meta.get(k) != first.get(k):
                errors.append(f"frame {i + 1}: {k} differs from 04a")
        asn = meta.get("asn")
        if asn is None or first.get("asn") is None or not np.allclose(asn, first["asn"], rtol=1e-6, atol=1e-6):
            errors.append(f"frame {i + 1}: AsShotNeutral missing or changed")
    return {"pass": not errors, "errors": errors, "warnings": warnings,
            "selector_interpretation": "MakerNote record[0x28] is native colour mode, not recipe slot; all must be 1",
            "metas": metas}


def score_arrays(engine, a, probe, b, predictions, checks=None):
    delta, repeat = np.asarray(probe) - np.asarray(a), np.asarray(b) - np.asarray(a)
    noise = max(m.rms(repeat), .5)
    rows = []
    for h in engine.hyps:
        residual = delta - predictions[h["id"]]
        grey_error, ring_error = m.rms(residual[engine.grey]), m.rms(residual[engine.ring])
        score = float(np.sqrt(.5 * grey_error ** 2 + .5 * ring_error ** 2))
        rows.append({**h, "score_codes": score, "all_RMS_codes": m.rms(residual),
                     "grey_RMS_codes": grey_error, "ring_RMS_codes": ring_error})
    rows.sort(key=lambda x: x["score_codes"])
    best, second = rows[:2]
    margin = second["score_codes"] - best["score_codes"]
    grey_max = float(np.abs(repeat[engine.grey]).max())
    restored = grey_max <= 2.0
    threshold = max(4.0, 4 * noise)
    score_ok = best["score_codes"] <= threshold
    separated = margin >= max(5.0, 4 * noise)
    independent = best["id"].startswith(("absolute_", "offset_", "aux_offset_"))
    if not restored or (checks is not None and not checks["pass"]):
        result, zh = "abnormal", "异常"
    elif score_ok and separated and independent:
        result, zh = "functional_pass", "功能通过"
    else:
        result, zh = "not_confirmed", "未确认"
    return {"result": result, "result_zh": zh, "best_hypothesis": best, "second_best": second,
            "margin_codes": margin, "margin_over_repeatability": margin / noise,
            "grey_return_within_2_codes": restored, "grey_return_max_abs_codes": grey_max,
            "repeatability_RMS_codes": m.rms(repeat), "noise_floor_codes": noise,
            "fit_threshold_codes": threshold, "fit_pass": score_ok, "separation_pass": separated,
            "full_channel_mapping_identified": result == "functional_pass",
            "scores": rows, "delta_08_minus_04a": delta, "delta_04b_minus_04a": repeat,
            "grey_08_mean_delta_RGB": delta[engine.grey].mean(0), "metadata_checks": checks,
            "warnings": list(checks.get("warnings", [])) if checks else []}


def summary(verdict):
    best = verdict.get("best_hypothesis")
    if best is None:
        return f"结果：异常。{verdict['error']}\n"
    back = "是" if verdict["grey_return_within_2_codes"] else "否"
    return (f"结果：{verdict['result_zh']}（{verdict['result']}）。\n"
            f"最佳假设 {best['id']}，加权残差 {best['score_codes']:.2f} 码；"
            f"领先次选 {verdict['second_best']['id']} {verdict['margin_codes']:.2f} 码"
            f"（重复性噪声的 {verdict['margin_over_repeatability']:.1f} 倍）。\n"
            f"末张 04 的 9 个灰块是否全部回到 ±2 码：{back}；最大差 {verdict['grey_return_max_abs_codes']:.2f} 码。\n"
            + ("拍摄检查：" + "；".join(verdict["metadata_checks"]["errors"]) + "。\n"
               if verdict.get("metadata_checks") and not verdict["metadata_checks"]["pass"] else "")
            + "".join(f"警告：{warning}。\n" for warning in verdict.get("warnings", [])))


def analyze(paths, output=None, engine=None):
    output = output_path(output)
    p.ignored(output / "verdict.json") if output.is_relative_to(p.LOCAL.resolve()) else None
    ar = engine.ar if engine else p.load("t1p2_analysis_ring", p.ROOT / "research/hue_ring/analyze_ring.py")
    first = extract(paths[0], ar, ar.load_layout())
    frames = [first] + [extract(x, ar, ar.load_layout(), np.asarray(first["H"])) for x in paths[1:]]
    engine = engine or m.Engine(frames[0]["meta"]["display"])
    checks = metadata_checks(frames)
    a, probe, b = [np.array(f["rgb"]) for f in frames]
    raw = [np.array(f["cam_wb"]) for f in frames]
    raw_drifts = []
    for i in (1, 2):
        dr = np.median(np.log2(np.maximum(raw[i][engine.grey], 1e-8) /
                               np.maximum(raw[0][engine.grey], 1e-8)), axis=0)
        raw_drifts.append({"frame": i + 1, "median_channel_EV": dr})
        if np.max(np.abs(dr)) > .03:
            checks["errors"].append(f"frame {i + 1}: grey RAW exposure/WB drift exceeds 0.03 EV")
    checks["raw_drifts"] = raw_drifts
    checks["pass"] = not checks["errors"]
    prediction_key = frames[0]["hashes"]["JPEG"] + frames[0]["hashes"]["DNG"]
    if not hasattr(engine, "baseline_predictions"):
        engine.baseline_predictions = {}
    if prediction_key not in engine.baseline_predictions:
        engine.baseline_predictions[prediction_key] = engine.predict(a, raw[0])
    predictions, quality = engine.baseline_predictions[prediction_key]
    verdict = score_arrays(engine, a, probe, b, predictions, checks)
    clipping = frames[1]["clipping_255"]
    if clipping["warning"]:
        verdict["warnings"].append(
            f"08 彩块和灰块有 {100 * clipping['fraction']:.3f}% 像素至少一个通道削顶到 255，超过 0.5%，仅作提示")
    verdict.update(schema="gxr-t1-probe2-verdict-1", model_sha256=p.sha(p.MODEL),
                   inputs=[{k: f[k] for k in ("JPEG", "DNG", "hashes")} for f in frames],
                   chain="WB linear camera RGB -> per-channel curve -> type-28 matrix -> pre-lookup ring v2 -> JPEG",
                   inversion_quality=quality, patch_count=155, grey_count=9,
                   clipping_255_08=clipping,
                   interpretation="host image analysis; power-cycle/menu !4 is a separate manual observation")
    p.dump(output / "verdict.json", verdict)
    p.dump(output / "patches.json", frames)
    text = summary(verdict)
    p.save(output / "SUMMARY.txt", text)
    return verdict, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames", nargs=3, metavar="JPEG", help="04a, 08, 04b; each with adjacent DNG")
    parser.add_argument("--out", type=Path, help="output below probe2/local or /tmp/t1p2")
    args = parser.parse_args()
    p.preflight()
    try:
        verdict, text = analyze(args.frames, args.out)
    except (ValueError, KeyError, OSError, SystemExit) as ex:
        verdict = {"schema": "gxr-t1-probe2-verdict-1", "result": "abnormal", "result_zh": "异常",
                   "error": str(ex), "inputs": [str(x) for x in args.frames]}
        output = output_path(args.out)
        p.dump(output / "verdict.json", verdict)
        text = summary(verdict)
        p.save(output / "SUMMARY.txt", text)
    print(text, end="")


if __name__ == "__main__":
    main()
