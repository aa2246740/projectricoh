#!/usr/bin/env python3
"""Measured-noise and full JPEG+DNG input tests, without camera access."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
sp = importlib.util.spec_from_file_location("t1p2_analyzer", Path(__file__).with_name("analyze_probe2.py"))
a = importlib.util.module_from_spec(sp)
sp.loader.exec_module(a)
p, m = a.p, a.m
import numpy as np
from PIL import Image


def array_tests(engine, predictions, base, repeat):
    rng = np.random.default_rng(20261020)
    rows = []
    for h in engine.hyps:
        correct = 0
        margins = []
        for _ in range(20):
            noise = repeat[rng.permutation(len(repeat))] * rng.choice([-1, 1], (len(repeat), 1))
            probe = base + predictions[h["id"]] + noise
            verdict = a.score_arrays(engine, base, probe, base + repeat, predictions)
            correct += verdict["best_hypothesis"]["id"] == h["id"]
            margins.append(verdict["margin_codes"])
        p.require(correct == 20, f"noise recovery failed: {h['id']}")
        rows.append({"id": h["id"], "recovered": correct, "trials": 20, "min_margin_codes": min(margins)})
    nochange = a.score_arrays(engine, base, base, base + repeat, predictions)
    p.require(nochange["best_hypothesis"]["id"] == "no_effect" and nochange["result"] == "not_confirmed",
              "no-change falsely passed")
    bad_return = base + repeat
    bad_return[engine.grey, 0] += 8
    bad = a.score_arrays(engine, base, base + predictions["absolute_BCD"], bad_return, predictions)
    p.require(bad["result"] == "abnormal", "failed restoration did not veto pass")
    badmeta = a.score_arrays(engine, base, base + predictions["absolute_BCD"], base + repeat,
                            predictions, {"pass": False, "errors": ["ISO mismatch"]})
    p.require(badmeta["result"] == "abnormal", "metadata did not veto pass")
    meta0 = json.loads((p.LOCAL / "baseline.json").read_text())["04a"]["meta"]
    metadata_cases = []
    for field, wrong in (("iso", 1600), ("selector", 3), ("t", 1 / 500), ("f", 5.6),
                          ("wb_record_0x26", 0), ("asn", [.7, 1., .9]),
                          ("program", 2), ("exposure_mode", 0), ("wb_exif", 0),
                          ("display", {}), ("raw13", [])):
        frames = [{"meta": copy.deepcopy(meta0), "metadata_errors": []} for _ in range(3)]
        frames[1]["meta"][field] = wrong
        check = a.metadata_checks(frames)
        p.require(not check["pass"], f"incorrect metadata accepted: {field}")
        if field in ("t", "f"):
            p.require(check["warnings"], "single-frame calibration deviation lost its warning")
        metadata_cases.append({"changed_field": field, "rejected": True})
    alternate = [{"meta": copy.deepcopy(meta0), "metadata_errors": []} for _ in range(3)]
    for frame in alternate:
        frame["meta"].update(t=1 / 30, f=5.6)
    check = a.metadata_checks(alternate)
    p.require(check["pass"] and len(check["warnings"]) == 2, "consistent alternate exposure failed or lost warnings")
    alternate_verdict = a.score_arrays(engine, base, base + predictions["absolute_BCD"], base + repeat,
                                      predictions, check)
    p.require(alternate_verdict["result"] == "functional_pass" and
              all(w in a.summary(alternate_verdict) for w in check["warnings"]),
              "exposure warnings failed the result or were omitted from SUMMARY")
    warning_frames = [{"meta": copy.deepcopy(meta0), "metadata_errors": []} for _ in range(3)]
    for frame in warning_frames:
        frame["meta"].update(t=None, f=None)
    p.require(not a.metadata_checks(warning_frames)["pass"], "missing exposure was accepted")
    scratch = p.SCRATCH / "revision/path_check"
    p.require(a.output_path(scratch) == a.output_path(scratch.resolve()), "resolved scratch alias rejected")
    for outside in (p.SCRATCH.parent / "t1p2-outside", p.SCRATCH / ".." / "outside"):
        try:
            a.output_path(outside)
        except ValueError:
            continue
        raise AssertionError(f"outside path accepted: {outside}")
    tiny_layout = {"patches": [
        {"group": "gray", "ring": None, "bbox_px": [0, 0, 1080, 81]},
        {"group": "white", "ring": None, "bbox_px": [0, 0, 1080, 81]}]}
    class PixelROI:
        @staticmethod
        def roi_mask(geo, rect, shape):
            return 0, 1, 0, 1000, np.ones((1, 1000), bool), None
    tiny = np.zeros((1, 1000, 3), dtype=np.uint8)
    tiny[0, :5] = 255
    edge = a.clipping_255(tiny, {}, tiny_layout, PixelROI)
    p.require(edge["fraction"] == .005 and not edge["warning"] and edge["ROI_pixels"] == 1000,
              "clipping threshold, channel union or white exclusion is wrong")
    tiny[0, 5, 2] = 255
    over = a.clipping_255(tiny, {}, tiny_layout, PixelROI)
    p.require(over["fraction"] == .006 and over["warning"] and over["per_channel_pixels_RGB"] == [5, 5, 6],
              "single-channel clipping above threshold was missed")
    p.dump(p.LOCAL / "tests/array_tests.json", {"cases": rows, "total_recovered": sum(r["recovered"] for r in rows),
           "total_trials": len(rows) * 20, "nochange": nochange["result"],
           "bad_restore": bad["result"], "bad_metadata": badmeta["result"], "metadata_cases": metadata_cases,
           "alternate_exposure_warning_only": True, "missing_exposure_rejected": True,
           "resolved_scratch_path_accepted": True, "outside_paths_rejected": True,
           "clipping_threshold_union_and_white_exclusion": True})
    print(f"array recovery {len(rows) * 20}/{len(rows) * 20}; no-change and two vetoes PASS", flush=True)


def synthetic_jpeg(engine, hypothesis, prediction, repeat, index):
    source = p.CAP / "R8051179.JPG"
    folder = p.LOCAL / "tests" / "images" / hypothesis
    jpg, dng = folder / "probe.JPG", folder / "probe.DNG"
    folder.mkdir(parents=True, exist_ok=True)
    im = Image.open(source)
    image = np.array(im.convert("RGB"), dtype=float)
    rgb = json.loads((p.LOCAL / "baseline.json").read_text())["04a"]
    H = np.array(rgb["H"])
    geo = {"H": H, "Hinv": np.linalg.inv(H)}
    rng = np.random.default_rng(20261020 + index)
    noise = repeat[rng.permutation(len(repeat))] * rng.choice([-1, 1], (len(repeat), 1))
    for i, patch in enumerate(engine.layout["patches"]):
        rect = patch["bbox_px"]
        ya, yb, xa, xb, mask, _ = engine.ar.roi_mask(geo, rect, image.shape)
        block = image[ya:yb, xa:xb]
        block[mask] = np.clip(block[mask] + prediction[i] + noise[i], 0, 255)
    Image.fromarray(np.rint(image).astype(np.uint8)).save(jpg, quality=98, subsampling=0, exif=im.info["exif"])
    shutil.copyfile(p.CAP / "R8051179.DNG", dng)
    p.ignored(jpg)
    p.ignored(dng)
    return jpg


def image_tests(engine, predictions, repeat, indices):
    for i in indices:
        hypothesis = engine.hyps[i]["id"]
        jpg = synthetic_jpeg(engine, hypothesis, predictions[hypothesis], repeat, i)
        output = p.LOCAL / "tests" / "image_results" / hypothesis
        verdict, _ = a.analyze([p.CAP / "R8051179.JPG", jpg, p.CAP / "R8051182.JPG"], output, engine)
        p.require(verdict["best_hypothesis"]["id"] == hypothesis,
                  f"image recovery failed: expected {hypothesis}, got {verdict['best_hypothesis']['id']}")
        p.require(verdict["metadata_checks"]["pass"] and verdict["grey_return_within_2_codes"],
                  f"synthetic image checks failed: {hypothesis}")
        expected_result = "not_confirmed" if hypothesis in ("broadcast_C", "broadcast_D", "no_effect") else "functional_pass"
        p.require(verdict["result"] == expected_result,
                  f"wrong image verdict for {hypothesis}: {verdict['result']}")
        clipping = verdict["clipping_255_08"]
        p.require(bool(verdict["warnings"]) == clipping["warning"], "clipping warning was not propagated")
        p.require(all(w in a.summary(verdict) for w in verdict["warnings"]), "SUMMARY omitted warnings")
        print(f"image {i + 1}/21 {hypothesis}: recovered, residual={verdict['best_hypothesis']['score_codes']:.2f}, "
              f"margin={verdict['margin_codes']:.2f}, {verdict['result']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arrays", action="store_true")
    parser.add_argument("--images", nargs="*", type=int, help="0-based hypothesis indices, default all 21")
    parser.add_argument("--nochange", action="store_true")
    args = parser.parse_args()
    p.preflight()
    raw = json.loads((p.LOCAL / "predictions.json").read_text())
    base = json.loads((p.LOCAL / "baseline.json").read_text())
    engine = m.Engine(base["04a"]["meta"]["display"])
    pred = {key: np.array(value) for key, value in raw["versions"]["probe2"]["delta"].items()}
    rgb = np.array(base["04a"]["rgb"])
    repeat = np.array(base["04b"]["rgb"]) - rgb
    if args.arrays:
        array_tests(engine, pred, rgb, repeat)
    if args.images is not None:
        indices = args.images or list(range(len(engine.hyps)))
        p.require(all(0 <= i < len(engine.hyps) for i in indices), "bad hypothesis index")
        image_tests(engine, pred, repeat, indices)
    if args.nochange:
        verdict, text = a.analyze([p.CAP / "R8051179.JPG", p.CAP / "R8051179.JPG", p.CAP / "R8051182.JPG"],
                                  p.LOCAL / "tests/no_change", engine)
        p.require(verdict["best_hypothesis"]["id"] == "no_effect" and verdict["result"] == "not_confirmed",
                  "image no-change falsely passed")
        print(text, end="")


if __name__ == "__main__":
    main()
