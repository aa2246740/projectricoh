"""Read-only verification of original evidence anchors and review result counts."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIVATE = ROOT / "artifacts/downloads/fit-fast-r1"
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
if os.getpriority(os.PRIO_PROCESS, 0) < 15:
    os.nice(15-os.getpriority(os.PRIO_PROCESS, 0))


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalize(value):
    if isinstance(value, dict):
        return {key: normalize(val) for key, val in value.items() if key != "seconds"}
    if isinstance(value, list):
        return [normalize(val) for val in value]
    return value


def main():
    summary = read(HERE / "round2/quality_independent-full.json")
    original = read(ROOT / "research/fit_fast_r1/round2/quality_full-guard-final.json")
    assert summary["passed"] and summary["fits"] == 1530 and summary["artifact_rebuild_performed"]
    for field in ("per_fit_table_sha256", "per_photo_table_sha256", "noise_table_sha256"):
        assert summary[field] == original[field]
    rows = read(HERE / "artifacts/round2/quality/independent-full/per_fit.json")
    photo_rows = read(HERE / "artifacts/round2/quality/independent-full/per_photo.json")
    refs = {}
    for tag in ("full-ref-a-final", "full-ref-b2", "full-ref-c", "full-ref-d"):
        for path in (PRIVATE / "bench" / tag / "r0-reference").glob("**/fits/*/*.json"):
            if path.stem in ("L0", "L1") or path.stem.endswith("_fullfields"):
                key = int(path.parent.name), path.stem
                assert key not in refs
                refs[key] = path
    with tarfile.open(PRIVATE / "round2/round1_delivery.tar.gz", "r:gz") as archive:
        seal = json.loads(archive.extractfile("research/fit_fast_r1/seal.json").read())
    frozen = PRIVATE / "round2/frozen_round1_private.SHA256SUMS"
    assert sha(frozen) == seal["private_manifest_sha256"]
    frozen_hashes = {name: value for value, name in (line.split("  ", 1) for line in frozen.read_text().splitlines())}
    identical = 0
    for row in rows:
        path = refs[row["index"], row["key"]]
        for suffix, field in ((".json", "reference_json_sha256"), (".npz", "reference_npz_sha256")):
            artifact = path.with_suffix(suffix)
            digest = sha(artifact)
            assert digest == row[field] == frozen_hashes[str(artifact.relative_to(ROOT))]
        identical += row["actual_npz_sha256"] == row["reference_npz_sha256"]
    assert identical == 1530
    assert all(row["reference"] == row["actual"] for row in photo_rows)
    # Re-read the original serial/parallel evidence independently of its summary.
    base = PRIVATE / "parallel/r2-resume-parallel"
    old_parallel = []
    for path in sorted((base / "serial/fits").glob("*/*.json")):
        doc = read(path)
        if doc["config"]["level"] >= 2 and not doc["config"].get("full_fields"):
            continue
        peer = base / "parallel" / path.relative_to(base/"serial")
        assert normalize(doc) == normalize(read(peer))
        assert sha(path.with_suffix(".npz")) == sha(peer.with_suffix(".npz"))
        old_parallel.append(dict(path=str(path.relative_to(ROOT)), sha256=sha(path), peer_sha256=sha(peer)))
    assert len(old_parallel) == 90
    for phase in ("base", "full"):
        clean = lambda path: re.sub(r"seconds [0-9.]+", "seconds <elapsed>", path.read_text())
        assert clean(base/"serial"/(phase+".log")) == clean(base/"parallel"/(phase+".log"))
    rerun = read(HERE / "artifacts/parallel-independent/summary.json")
    assert rerun["passed"] and rerun["fits"] == 90
    counter = read(HERE / "artifacts/counterexample_original_reference.json")
    assert counter["original_and_accelerated_exact_predictions_equal"]
    assert counter["guarded_objective_increase"] > counter["training_noise"]
    dependencies = {}
    for receipt in (HERE/"artifacts/input_receipts").glob("*.json"):
        for name, expected in read(receipt).items():
            assert sha(ROOT/name) == expected, "Runtime input drift: " + name
            if name in dependencies:
                assert dependencies[name] == expected
            dependencies[name] = expected
    assert dependencies
    old_receipt = PRIVATE/"bench/full-ref-a-final/r0-reference/index07/input_hashes_fit_7.json"
    assert sha(old_receipt) == frozen_hashes[str(old_receipt.relative_to(ROOT))]
    old_inputs = read(old_receipt)
    common = set(old_inputs) & set(dependencies)
    implementation_differences = sorted(name for name in common if old_inputs[name] != dependencies[name])
    assert implementation_differences == ["tools/fit_fast/engine.py"]
    result = dict(full_rebuild_passed=True, fits=1530,
        frozen_reference_json_and_npz_checked=3060,
        round1_reference_anchor_sha256=sha(frozen),
        prediction_archives_identical_to_reference=identical,
        photo_rows_identical=len(photo_rows),
        training_objectives_identical=sum(row["objective_delta"] == 0 for row in rows),
        undefined_fits=sum(row["reference_photo_similarity_median"] is None for row in rows),
        min_noise=summary["min_noise"], max_noise=summary["max_noise"],
        old_serial_parallel_files_rechecked=len(old_parallel), old_stdout_order_rechecked=True,
        independent_serial_parallel_rerun_passed=True,
        rerun_scheduler_scope="Original run.worker with review I/O; own coordinator; original main CLI scheduler not rerun",
        fallback_checks=read(HERE/"artifacts/fallback_checks.json")["passed"],
        counterexample_original_reference_confirmed=True,
        runtime_read_dependencies_rechecked=len(dependencies),
        round1_shared_runtime_inputs=len(common),
        round1_shared_input_hash_matches=len(common)-len(implementation_differences),
        round1_implementation_input_differences=implementation_differences,
        artifact_notes="Numerical arrays and fits are under this review artifacts directory, covered by its .gitignore",
        nice=os.getpriority(os.PRIO_PROCESS,0))
    (HERE/"verification.json").write_text(json.dumps(result,indent=2)+"\n")
    (HERE/"artifacts/old_parallel_hashes.json").write_text(json.dumps(old_parallel,indent=2)+"\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
