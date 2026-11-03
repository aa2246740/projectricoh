#!/usr/bin/env python3
"""Verify final private artifacts, tests, public hygiene and read-only inputs."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sp = importlib.util.spec_from_file_location("probe2_core", Path(__file__).with_name("probe2_core.py"))
p = importlib.util.module_from_spec(sp)
sp.loader.exec_module(p)


def main():
    p.preflight()
    before = json.loads((p.LOCAL / "input_before.json").read_text())
    after = p.source_manifest([p.ROOT / name for name in before])
    p.require(before == after, "read-only input hashes changed")
    package_before = json.loads((p.LOCAL / "analyzer_revision_package_before.json").read_text())
    package_after = {str(f.relative_to(p.PACKAGE)): {"sha256": p.sha(f), "size": f.stat().st_size,
                      "mtime_ns": f.stat().st_mtime_ns} for f in sorted(p.PACKAGE.rglob("*")) if f.is_file()}
    p.require(package_before == package_after, "DAT package changed during analyzer revision")
    host = json.loads((p.LOCAL / "host_validation.json").read_text())
    for name, digest in host["inputs_sha256"].items():
        p.require(p.sha(p.ROOT / name) == digest, f"host source changed: {name}")
    src = p.generator()
    bank = (p.ROOT / "firmware/stage2j/examples/DEEPISP0.DAT").read_bytes()
    dat0, dat1 = [(p.RAW_PACKAGE / n).read_bytes() for n in src.TABLE_NAMES]
    p.require(dat0 == dat1 and p.sha(p.RAW_PACKAGE / src.TABLE_NAMES[0]) == host["dat_sha256"],
              "final DAT pair/hash differs")
    base = (p.BASE / "DEEPTBL0.DAT").read_bytes()
    old, new = src.parse(base, bank), src.parse(dat0, bank)
    entry_at = src.HEADER_BYTES + 7 * src.ENTRY_BYTES
    allowed = set(range(12, 16)) | set(range(entry_at + src.CRC_OFFSETS[6], entry_at + src.CRC_OFFSETS[6] + 4))
    allowed |= set(range(entry_at + src.ROW_OFFSETS[6], entry_at + src.ROW_OFFSETS[6] + 33))
    changed = {i for i, (a, b) in enumerate(zip(base, dat0)) if a != b}
    p.require(len(changed) == 33 and changed <= allowed and new[7]["rows"][6][33:] == old[7]["rows"][6][33:],
              "final C-only change invariant failed")
    document = json.loads((p.RAW_PACKAGE / "entry08_probe2.json").read_text())
    merge = p.load("t1p2_verify_original", p.HERE.parent / "build_validate.py").merge_entry
    p.require(merge(src, base, bank, document) == dat0, "saved entry JSON cannot reproduce final DAT")
    package_checks = []
    for line in (p.PACKAGE / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        p.require(p.sha(p.PACKAGE / name) == digest, f"package SHA mismatch: {name}")
        package_checks.append(name)
    private = [f for root in (p.LOCAL, p.RAW_PACKAGE) for f in root.rglob("*") if f.is_file()]
    names = [str(f.relative_to(p.ROOT)) for f in private]
    ignored = subprocess.run(["git", "check-ignore", "--stdin"], cwd=p.ROOT,
                             input="\n".join(names) + "\n", text=True, capture_output=True, check=True)
    p.require(set(ignored.stdout.splitlines()) == set(names), "some private file is not ignored")
    public = [f for root in (p.HERE, p.PACKAGE) for f in root.rglob("*") if f.is_file()
              and not f.is_relative_to(p.LOCAL) and not f.is_relative_to(p.RAW_PACKAGE)]
    for f in public:
        text = f.read_text()
        p.require(not re.search(r"(?<![0-9a-fA-F])[0-9a-fA-F]{96,}(?![0-9a-fA-F])", text),
                  f"long raw hex string in public file: {f}")
    pred = json.loads((p.LOCAL / "predictions.json").read_text())
    p.require(pred["model_sha256"] == p.sha(p.MODEL), "model changed after prediction")
    ids = {h["id"] for h in pred["hypotheses"]}
    results = []
    for name in sorted(ids):
        result = json.loads((p.LOCAL / f"tests/image_results/{name}/verdict.json").read_text())
        expected = "not_confirmed" if name in ("broadcast_C", "broadcast_D", "no_effect") else "functional_pass"
        p.require(result["best_hypothesis"]["id"] == name and result["result"] == expected and
                  result["metadata_checks"]["pass"] and result["grey_return_within_2_codes"] and
                  result["model_sha256"] == p.sha(p.MODEL), f"synthetic JPEG+DNG failed: {name}")
        p.require(bool(result["warnings"]) == result["clipping_255_08"]["warning"],
                  f"image clipping warning mismatch: {name}")
        results.append({"hypothesis": name, "result": result["result"],
                        "score_codes": result["best_hypothesis"]["score_codes"], "margin_codes": result["margin_codes"]})
    arrays = json.loads((p.LOCAL / "tests/array_tests.json").read_text())
    p.require(arrays["total_recovered"] == arrays["total_trials"] == 420 and
              arrays["bad_restore"] == arrays["bad_metadata"] == "abnormal" and
              all(x["rejected"] for x in arrays["metadata_cases"]), "numeric/noise/veto tests failed")
    revision_checks = ("alternate_exposure_warning_only", "missing_exposure_rejected",
                       "resolved_scratch_path_accepted", "outside_paths_rejected",
                       "clipping_threshold_union_and_white_exclusion")
    p.require(all(arrays[k] for k in revision_checks), "analyzer revision boundary test failed")
    dry = json.loads((p.LOCAL / "dry_run/verdict.json").read_text())
    no = json.loads((p.LOCAL / "tests/no_change/verdict.json").read_text())
    p.require(dry["result"] == no["result"] == "not_confirmed" and
              no["best_hypothesis"]["id"] == "no_effect", "dry/no-change false positive")
    scratch_dry = json.loads((p.SCRATCH / "analyzer_revision/dry_run/verdict.json").read_text())
    p.require(scratch_dry == dry and "error" not in scratch_dry, "CLI scratch-path dry run failed")
    pairs = pred["versions"]["probe2"]["separation"]
    p.require(len(pairs["pairs"]) == 210 and pairs["minimum_pair"]["repeatability_ratio"] > 10,
              "hypothesis separation is insufficient")
    verification = {"result": "PASS", "read_only_inputs_unchanged": len(before),
                    "host_inputs_unchanged": len(host["inputs_sha256"]), "private_files_all_ignored": len(private),
                    "public_files_no_long_raw_hex": len(public), "DAT_pair_and_C_only_diff": True,
                    "package_checksums_checked": package_checks, "synthetic_images_recovered": len(results),
                    "synthetic_numeric_recovered": arrays["total_recovered"], "metadata_negative_cases": len(arrays["metadata_cases"]),
                    "image_max_residual_codes": max(x["score_codes"] for x in results),
                    "image_min_margin_codes": min(x["margin_codes"] for x in results),
                    "minimum_pair_separation_codes": pairs["minimum_pair"]["RMS_codes"],
                    "minimum_pair_over_repeatability": pairs["minimum_pair"]["repeatability_ratio"],
                    "dry_run": dry["result"], "no_change": no["result"], "camera_acceptance": "pending"}
    verification.update(analyzer_sha256=p.sha(p.HERE / "analyze_probe2.py"), DAT_package_unchanged=True,
                        DAT_package_files_unchanged=len(package_after),
                        analyzer_revision_checks={k: arrays[k] for k in revision_checks},
                        CLI_scratch_path_dry_run=True)
    p.dump(p.HERE / "verification.json", verification)
    p.dump(p.HERE / "test_metrics.json", {"evidence": "synthetic JPEG+DNG, not camera acceptance", "cases": results})
    p.dump(p.LOCAL / "input_after.json", after)
    public = sorted(f for f in p.HERE.rglob("*") if f.is_file() and not f.is_relative_to(p.LOCAL)
                    and f.name != "SHA256SUMS")
    p.save(p.HERE / "SHA256SUMS", "".join(f"{p.sha(f)}  {f.relative_to(p.HERE)}\n" for f in public))
    print(f"PASS inputs={len(before)} private_ignored={len(private)} image_recovery={len(results)}/21 numeric=420/420")
    print(f"DAT {p.sha(p.RAW_PACKAGE / 'DEEPTBL0.DAT')}")


if __name__ == "__main__":
    main()
