"""Rebuild the review's cases from read-only inputs and keep current decisions."""
import hashlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(OUT), str(ROOT / "studio/src"), str(ROOT / "studio/tests")]
from finish_evidence import current_source
import numpy as np
from PIL import Image
from scipy import ndimage
import hdr_support as hs
from gxr_studio import audit
from gxr_studio.hdr import gain as g
from gxr_studio.raw import open_dng

audit.forbid_volumes()
audit.forbid_network(True)
rows = []


def trial(case, kind, jpeg, dng, expected, previous=None):
    record = {"case": case, "kind": kind, "expected": expected}
    try:
        raw = g.raw_luma(open_dng(dng))
        output, stats = g.hdr_from_camera_jpeg(jpeg, raw)
        sha = hashlib.sha256(output).hexdigest()
        record.update(accepted=True, alignment=stats["alignment"], sha256=sha)
        if previous is not None:
            record["same_hdr_bytes_as_review"] = sha == previous
    except g.HdrUnsupported as error:
        record.update(accepted=False, reason=error.reason, detail=error.detail)
    record["passed"] = record["accepted"] == expected and record.get("same_hdr_bytes_as_review", True)
    rows.append(record)
    print(json.dumps(record, ensure_ascii=False), flush=True)


def main():
    source = current_source()
    review = [json.loads(line) for line in (ROOT / "research/review_studio_hdr/alignment_cases.jsonl").read_text().splitlines()]
    street = ROOT / "captures/street-g137-20261031"
    a12 = ROOT / "captures/a12-50/2026-10-24/stage2l-daily-R8051312-1473"
    for case in review:
        kind, name = case["kind"], case["case"]
        if kind in ("mount_correct", "50mm_correct", "50mm_adjacent", "mount_other"):
            jpg_name, _, raw_name = name.partition("+")
            raw_name = raw_name or jpg_name
            jpg = (street / "jpg" / f"{jpg_name}.JPG") if kind.startswith("mount") else a12 / f"{jpg_name}.JPG"
            dng = (street / "dng" / f"{raw_name}.DNG") if kind.startswith("mount") else a12 / f"{raw_name}.DNG"
            trial(name, kind, jpg.read_bytes(), dng, kind.endswith("correct"), case.get("hdr_sha256") if kind.endswith("correct") else None)
        elif kind == "local_motion":
            size, distance = case["object_wh"][0], case["known_motion_pixels"]
            first = hs.scene()
            second = first.copy()
            first[96:96+size, 420:420+size] = .035
            second[96:96+size, 420+distance:420+distance+size] = .035
            trial(name, kind, hs.camera_jpeg(second), hs.camera_dng(first), False)
        elif kind == "radial_correction":
            jpeg = (street / "jpg/R8051530.JPG").read_bytes()
            rgb = g.decode_rgb(jpeg)
            h, w = rgb.shape[:2]
            yy, xx = np.mgrid[:h, :w].astype(np.float32)
            rr = ((xx-(w-1)/2)/(w/2))**2 + ((yy-(h-1)/2)/(h/2))**2
            scale = 1 + case["coefficient"] * rr
            sx = (xx-(w-1)/2)*scale+(w-1)/2
            sy = (yy-(h-1)/2)*scale+(h-1)/2
            arr = np.stack([ndimage.map_coordinates(rgb[...,c],[sy,sx],order=1,mode="nearest") for c in range(3)],axis=-1)
            buf = io.BytesIO()
            Image.fromarray(arr).save(buf,"JPEG",quality=95)
            trial(name, kind, buf.getvalue(), street / "dng/R8051530.DNG", False)
    counts = {}
    for kind in sorted({row["kind"] for row in rows}):
        group = [row for row in rows if row["kind"] == kind]
        counts[kind] = {"total": len(group), "passed": sum(row["passed"] for row in group),
                        "accepted": sum(row["accepted"] for row in group)}
    name = sys.argv[1] if len(sys.argv)>1 else "alignment_results"
    with (OUT / (name+".json")).open("x") as stream:
        json.dump({"counts": counts, "cases": rows, "source_sha256": source}, stream, indent=2, ensure_ascii=False)
    print(json.dumps(counts),flush=True)
    assert audit.network_attempts() == []
    assert source == current_source()
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
