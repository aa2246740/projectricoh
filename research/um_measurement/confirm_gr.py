#!/usr/bin/env python3
"""Check the current package's GR curve provenance without building any rows."""
import sys

sys.dont_write_bytecode = True

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    spec = importlib.util.spec_from_file_location("um_measure", HERE / "measure.py")
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.verify_volume()
    source = ROOT / "firmware/stage2j/tools/deep_sources.py"
    m = guard.load_module("um_gr_package_readonly", source)
    package = ROOT / "artifacts/stage2j-packages/tables-v1-preliminary/DEEPTBL0.DAT"
    paths = [package, source, m.CURVES, m.GR4,
             ROOT / "research/gr4_modes/rows.py",
             ROOT / "research/phase1_curves/fit_phase1.py"]
    before = {str(p): guard.sha(p) for p in paths}
    _, surface = m.surface_bank()
    records = m.parse(package.read_bytes(), surface)
    curves = json.loads(m.CURVES.read_text())
    gr4 = json.loads(m.GR4.read_text())
    expected = {1: curves["positive"], 2: curves["negative"],
                3: gr4["modes"]["hc_bw"]["row_jpeg_domain"]}
    matches = {}
    for slot, curve in expected.items():
        record = next(r for r in records if r["slot"] == slot)
        a, b = m.unpack_tone(*record["rows"][:2])
        matches[str(slot)] = a == curve["input31_u16"] and b == curve["output33_u8"]
    assert all(matches.values())
    after = {str(p): guard.sha(p) for p in paths}
    assert before == after
    result = {"package_tone_matches_registered_candidate": matches,
              "01_02_provenance": "GR III JPEG Standard-to-mode transfer on GXR stock response",
              "03_provenance": "GR IV row_jpeg_domain, not row_anchor or native GXR row20",
              "um_dependency": "none: all selected rows have target M(stock5(u))",
              "input_sha256_before": before, "input_sha256_after": after}
    guard.dump("gr_curve_confirmation.json", result)
    print(json.dumps({"matches": matches, "inputs_unchanged": before == after}))


if __name__ == "__main__":
    main()
