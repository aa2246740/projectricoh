"""Freeze and recheck only the reviewed sources and the evidence actually used."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
if os.getpriority(os.PRIO_PROCESS, 0) < 15:
    os.nice(15 - os.getpriority(os.PRIO_PROCESS, 0))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


manifest = BASE / "INPUT_SHA256SUMS"
mode = sys.argv[1] if len(sys.argv) > 1 else "freeze"
if mode in ("check", "extend"):
    rows = [line.split("  ", 1) for line in manifest.read_text().splitlines()]
    failed = [name for value, name in rows if digest(ROOT / name) != value]
    (BASE / "input_stability.json").write_text(json.dumps(dict(
        passed=not failed, checked=len(rows), changed=failed,
        manifest_sha256=digest(manifest), utc=datetime.datetime.now(datetime.timezone.utc).isoformat()), indent=2) + "\n")
    print(json.dumps(dict(passed=not failed, checked=len(rows), changed=failed)))
    companion_only = failed and all(name.startswith("research/recipe_redo_r1/") for name in failed)
    if mode == "extend" and companion_only:
        drift = [dict(path=name, before=next(value for value, key in rows if key == name),
                      after=digest(ROOT/name)) for name in failed]
        (BASE / "companion_drift.json").write_text(json.dumps(dict(
            note="Concurrent companion edits; no reviewed fit-fast source or frozen numerical input changed",
            changes=drift), indent=2)+"\n")
    if mode == "check" or (failed and not companion_only):
        raise SystemExit(bool(failed))
if mode == "extend":
    initial = BASE / "INPUT_SHA256SUMS.initial"
    if not initial.exists():
        initial.write_bytes(manifest.read_bytes())
else:
    assert not manifest.exists(), "Preserve the initial frozen manifest"
paths = set()
for path in (ROOT / "tools/fit_fast").rglob("*"):
    if path.is_file() and path.suffix in (".py", ".c", ".rs", ".json", ".md"):
        paths.add(path)
for name in ("REPORT.md", "REPRODUCE.md", "PROGRESS.md", "SHA256SUMS", "seal.json"):
    paths.add(ROOT / "research/fit_fast_r1" / name)
for path in (ROOT / "research/fit_fast_r1/round2").iterdir():
    if path.suffix in (".json", ".md", ".patch"):
        paths.add(path)
local = ROOT / "research/look_ceiling_r1/local"
paths.add(local / "hardware_constants.json")
for index in (0, 1, 6, 7, 20, 29, 35, 36, 37, 38, 43, 44):
    for key in ("L1", "L2_Y_post", "L2_Y_pre", "L2_C_post", "L2_C_pre"):
        paths.add(local / "fits" / f"{index:02d}" / (key+".json"))
for index in range(51):
    meta = local / f"target_{index:02d}.json"
    paths.update((meta, local / f"target_{index:02d}.npz"))
    doc = json.loads(meta.read_text())
    for group in ("train", "synthetic", "a12-50", "a12-28", "mount-a12"):
        paths.add(local / doc.get("group_files", {}).get(group, "samples_" + group + ".npz"))
private = ROOT / "artifacts/downloads/fit-fast-r1"
paths.add(private / "frozen_inputs/studio_source_snapshot.tar.gz")
paths.add(private / "round2/frozen_round1_private.SHA256SUMS")
paths.add(private / "bench/full-ref-a-final/r0-reference/index07/input_hashes_fit_7.json")
sweep = json.loads((ROOT / "research/fit_fast_r1/round2/paired_r2-full-guard.json").read_text())
roots = [ROOT / row["output"] for row in sweep["trials"]]
roots += [private / "bench" / tag / "r0-reference" for tag in
          ("full-ref-a-final", "full-ref-b2", "full-ref-c", "full-ref-d")]
for root in roots:
    for path in root.glob("**/fits/*/*.json"):
        if path.stem in ("L0", "L1") or path.stem.endswith("_fullfields"):
            paths.update((path, path.with_suffix(".npz")))
for name in ("per_fit.json", "per_photo.json", "per_target.json", "reference_noise.json"):
    paths.add(private / "round2/quality/full-guard-final" / name)
for receipt in (BASE/"artifacts/input_receipts").glob("*.json"):
    for name, expected in json.loads(receipt.read_text()).items():
        if name.startswith("research/review_fit_fast_r2/"):
            continue
        path = ROOT/name
        assert digest(path) == expected, "Runtime-read dependency changed: " + name
        paths.add(path)
redo = ROOT / "research/recipe_redo_r1"
for name in ("fast_backend.py", "guarded_problem.py", "fit_one.py", "runtime.py", "runtime_std.py", "entry_codec.py", "capabilities.py"):
    paths.add(redo / name)
for unit in ("a12-50", "a12-28", "mount-a12"):
    for index in (0, 3, 4, 5, 12, 20, 31, 34):
        for suffix in (".json", "_train.npz", "_synthetic.npz", "_photo_iso200.npz"):
            path = redo / "local/targets" / unit / (f"{index:02d}" + suffix)
            if path.is_file():
                paths.add(path)
manifest.write_text("".join(digest(path) + "  " + str(path.relative_to(ROOT)) + "\n" for path in sorted(paths)))
print(json.dumps(dict(files=len(paths), manifest_sha256=digest(manifest), nice=os.getpriority(os.PRIO_PROCESS, 0))))
