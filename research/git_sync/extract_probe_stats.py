#!/usr/bin/env python3
"""Extract chart-v2 DNG/JPEG measurements without loading firmware tables or fits.

Inputs remain read-only. Output must be a new directory under this task's local/.
This reuses the existing chart-v2 detector and sampler, but does not construct its
model/target Chain, call its scoring CLI, or require the first Mac's volume UUID.
"""

import argparse
import ast
import inspect
import json
import os
from pathlib import Path
import sys
import textwrap
from types import SimpleNamespace

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CHART = ROOT / "research/chart_v2"
sys.path.insert(0, str(CHART))
import analyzer_runtime as rt
import analyze_chart_v2 as analyzer


def metadata(ar, jpg, dng):
    jm, dm = ar.read_meta(jpg, None, None), ar.read_meta(jpg, dng, None)
    errors = [f"{kind}: {value[key]}" for kind, value in (("JPEG", jm), ("DNG", dm))
              for key in ("exif_error", "makernote_error") if key in value]
    keys = ("program", "exposure_mode", "t", "f", "iso", "wb_exif", "selector",
            "wb_record_0x26", "raw13", "when")
    errors += [f"JPEG/DNG {key} differs" for key in keys if jm.get(key) != dm.get(key)]
    return dm, errors


def allow_unknown_lens_rationals(cls):
    """Preserve missing MOUNT aperture/focal length; do not turn 0/0 into a value."""
    original = cls.ifd
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))

    class Rational(ast.NodeTransformer):
        def visit_BinOp(self, node):
            if isinstance(node.op, ast.Div):
                return ast.copy_location(ast.Call(func=ast.Name(id="_ratio", ctx=ast.Load()),
                    args=[ast.Name(id="tag", ctx=ast.Load()), node.left, node.right], keywords=[]), node)
            return self.generic_visit(node)

    def ratio(tag, numerator, denominator):
        if denominator == 0 and tag in (33437, 37386, 50736, 42034):
            return None
        return numerator / denominator

    namespace = dict(original.__globals__, _ratio=ratio)
    exec(compile(ast.fix_missing_locations(Rational().visit(tree)), str(Path(__file__)), "exec"), namespace)
    cls.ifd = namespace["ifd"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--frame", action="append", help="optional repeated original frame stem")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    folder = rt.input_path(args.input)
    local = rt.input_path(HERE / "local")
    out = rt.input_path(args.out)
    rt.require(out.is_relative_to(local) and out != local and not out.exists(),
               "out must be a new directory under research/git_sync/local/")
    rt.require(folder.is_dir() and not out.is_relative_to(folder), "invalid input/output overlap")
    private = {"artifacts", "sources", "tools", "Scratch", "scratch"}

    def fence(event, values):
        if event != "open" or not isinstance(values[0], (str, bytes, Path)):
            return
        path = Path(os.fsdecode(values[0])).absolute().resolve()
        mode, flags = values[1:3]
        writing = isinstance(mode, str) and any(c in mode for c in "wax+")
        writing |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing:
            rt.require(path.is_relative_to(out), f"write outside output: {path}")
        elif path.is_relative_to(ROOT):
            parts = path.relative_to(ROOT).parts
            # The explicit photo directory and this run are the only private inputs allowed.
            if not path.is_relative_to(folder) and not path.is_relative_to(out):
                rt.require(not (set(parts) & private) and "local" not in parts,
                           f"private model/firmware input forbidden: {path}")

    sys.addaudithook(fence)
    pairs, errors = analyzer.pair_inventory(folder)
    if args.frame:
        selected = {name.upper() for name in args.frame}
        rt.require(selected <= {pair["frame"] for pair in pairs}, "selected frame is missing or unpaired")
        pairs = [pair for pair in pairs if pair["frame"] in selected]
        errors = [error for error in errors if error["frame"] in selected]
    manifest = rt.input_path(args.manifest) if args.manifest else None
    # A manifest is small owner-authored frame metadata, not a model or a table.
    if manifest and manifest.is_relative_to(local) and not manifest.is_relative_to(out):
        raise ValueError("put the manifest with the explicit input photos or in a public directory")
    entries, config = analyzer.manifest_entries(manifest, pairs)
    provenance = rt.Provenance()
    provenance.add(Path(__file__))
    for rel in ("research/chart_v2/analyze_chart_v2.py", "research/chart_v2/analyzer_runtime.py",
                "research/chart_v2/analyzer_geometry.py", "research/chart_v2/patches.json",
                "research/hue_ring/analyze_ring.py", "research/hue_ring/sector_model.py",
                "research/hue_ring/pilplot.py", "research/stage2d_verification/analyze.py",
                "research/stage2e_verification/analyze_2e.py", "research/color_calibration/analyze_capture.py",
                "research/color_table_fit/dng_scene.py"):
        provenance.add(ROOT / rel)
    for page in sorted((CHART / "pages").glob("*.png")):
        provenance.add(page)
    if manifest:
        provenance.add(manifest)
    out.mkdir(parents=True)
    ar = rt.load("stats_ring", ROOT / "research/hue_ring/analyze_ring.py")
    dng = rt.load("stats_dng", ROOT / "research/color_table_fit/dng_scene.py")
    physical = rt.load("stats_physical", ROOT / "research/stage2e_verification/analyze_2e.py")
    # jpeg_tiff retains its defining globals, which need not be S.Tiff.
    for cls in {ar.s2d().Tiff, ar.s2d().jpeg_tiff.__globals__["Tiff"], dng.analyze_capture().Tiff}:
        allow_unknown_lens_rationals(cls)
    original_read_meta = ar.read_meta

    def read_meta(jpg, dng_path, sidecar):
        from PIL import Image
        value = original_read_meta(jpg, dng_path, sidecar)
        with Image.open(jpg) as image:
            model = str(image.getexif().get(272, ""))
        if "MOUNT" in model and value.get("f") in (None, 0):
            value["f"] = None
            value["aperture_status"] = "unknown; EXIF zero or 0/0 is not a ring aperture measurement"
        return value

    ar.read_meta = read_meta
    original_lens_meta = analyzer.lens_meta

    def lens_meta(path):
        try:
            return original_lens_meta(path)
        except ZeroDivisionError:
            from PIL import Image
            with Image.open(path) as image:
                tags = image.getexif()
                exif = tags.get_ifd(34665)
                return {"model": str(tags.get(272)).strip("\x00 "),
                        "lens_model": exif.get(42036), "focal_length_mm": None}

    analyzer.lens_meta = lens_meta
    chain = SimpleNamespace(ar=ar, dng=dng, physical=physical,
                            measure=SimpleNamespace(metadata=metadata), p=provenance)
    frames = []
    for pair in pairs:
        try:
            frame = analyzer.analyze_pair(pair, entries.get(pair["frame"], {}), layout, chain, out)
            frame["evidence_kind"] = config.get("evidence_kind", "camera")
            frames.append(frame)
        except Exception as exc:
            errors.append({"frame": pair["frame"], "error": f"{type(exc).__name__}: {exc}"})
    analyzer.write_csv(out, frames)
    for frame in frames:
        dump(out / "frames" / (frame["frame"] + ".json"), frame)
    dump(out / "extraction.json", {"schema": "probe-statistics/1", "frames": len(frames),
         "errors": errors, "extraction_pass": not errors and all(f["status"] == "ok" for f in frames),
         "scoring": "not-run", "model_or_firmware_tables_loaded": False})
    dump(out / "provenance.json", provenance.finish())
    rt.write_sums(out)
    print(json.dumps({"out": str(out), "frames": len(frames), "errors": len(errors)}))
    return 2 if errors or any(f["status"] != "ok" for f in frames) else 0


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rt.jsonable(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    layout = json.loads((CHART / "patches.json").read_text())
    raise SystemExit(main())
