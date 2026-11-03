"""Finalize report hashes, audit ignored outputs, then seal the local review.

Run after all numerical processes exit. No writes outside this review directory.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
if os.getpriority(os.PRIO_PROCESS, 0) < 15:
    os.nice(15-os.getpriority(os.PRIO_PROCESS,0))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def main():
    active = subprocess.check_output(["ps", "-axo", "pid,ni,command"], text=True)
    forbidden = ("isolated.py fit", "isolated.py gate", "probe_solver.py", "probe_neighbors.py",
                 "score_case.py", "check_original_counterexample.py", "check_confirmation.py", "check_fallback.py")
    ongoing = [line for line in active.splitlines() if
               "review_fit_fast_r2/" in line and any(name in line for name in forbidden)
               and "/bin/zsh -c" not in line and "rg " not in line]
    assert not ongoing, "Review numerical processes remain active: " + repr(ongoing)
    verification = json.loads((HERE/"verification.json").read_text())
    assert verification["full_rebuild_passed"] and verification["independent_serial_parallel_rerun_passed"]
    inputs = [line.split("  ",1) for line in (HERE/"INPUT_SHA256SUMS").read_text().splitlines()]
    changed = [name for value,name in inputs if sha(ROOT/name) != value]
    core_changed = [name for name in changed if not name.startswith("research/recipe_redo_r1/")]
    assert not core_changed, core_changed
    private = sorted(path for path in (HERE/"artifacts").rglob("*") if path.is_file())
    names = [str(path.relative_to(ROOT)) for path in private]
    audit = subprocess.run(["git", "check-ignore", "-z", "-v", "--stdin"], cwd=ROOT,
                           input=("\0".join(names)+"\0").encode(), capture_output=True, check=True)
    fields = audit.stdout.decode().strip("\0").split("\0")
    assert len(fields) == 4*len(names)
    ignored = []
    for index in range(0,len(fields),4):
        rule, line, pattern, name = fields[index:index+4]
        assert not pattern.startswith("!")
        ignored.append(dict(path=name, rule=rule, line=line, pattern=pattern))
    assert {row["path"] for row in ignored} == set(names)
    (HERE/"ignore_audit.json").write_text(json.dumps(dict(passed=True, files=len(names), records=ignored), indent=2)+"\n")
    selected = [
        ROOT/"tools/fit_fast/run.py", ROOT/"tools/fit_fast/solver.py",
        ROOT/"tools/fit_fast/guarded.py", ROOT/"tools/fit_fast/round2/quality_gate.py",
        HERE/"round2/quality_independent-full.json", HERE/"verification.json",
        HERE/"artifacts/solver_probes/neighbor-start-07-3-1/states.npz",
        HERE/"artifacts/counterexample_original_reference.json",
        HERE/"artifacts/scored_neighbor-start-07-3-1.json",
        HERE/"artifacts/gate_negative_cases.json", HERE/"artifacts/parallel-independent/summary.json",
    ]
    report = HERE/"REVIEW.md"
    text = report.read_text().split("## SHA256SUMS",1)[0]
    text += "## SHA256SUMS\n\n```text\n"
    text += "".join(sha(path)+"  "+str(path.relative_to(ROOT))+"\n" for path in selected)
    text += "```\n\n完整清单 [SHA256SUMS](SHA256SUMS) 绑定本文、评审脚本、主审源码和忽略目录中的数值证据。清单自身的 SHA 单列在 [seal.json](seal.json)，避免自引用。全部路径相对仓库根。复跑会产生新证据，应另行封存。\n\n"
    text += "```sh\nshasum -a 256 -c research/review_fit_fast_r2/SHA256SUMS\n```\n"
    report.write_text(text)
    paths = {ROOT/name for _, name in inputs if not name.startswith("research/recipe_redo_r1/")}
    paths.update(path for path in HERE.rglob("*") if path.is_file() and path.name not in ("SHA256SUMS", "seal.json"))
    manifest = HERE/"SHA256SUMS"
    manifest.write_text("".join(sha(path)+"  "+str(path.relative_to(ROOT))+"\n" for path in sorted(paths)))
    now = datetime.datetime.now(datetime.timezone.utc)
    result = dict(sealed_utc=now.isoformat(), first_clock_utc="2026-11-03T09:20:51+00:00",
                  elapsed_seconds=(now-datetime.datetime(2026,11,3,9,20,51,tzinfo=datetime.timezone.utc)).total_seconds(),
                  timebox_seconds=9000, manifest_sha256=sha(manifest), files=len(paths),
                  input_files_checked=len(inputs), core_input_drift=core_changed,
                  companion_drift_since_last_extension=changed,
                  initial_companion_drift_receipt="companion_drift.json",
                  ignored_artifacts=len(private), all_artifacts_ignored=True,
                  write_root=str(HERE), numerical_process_cap=2, actual_nice=15,
                  forbidden_numerical_processes_active=ongoing,
                  no_live_studio=True, no_network=True, no_card_or_camera=True,
                  notes="Manifest excludes itself and seal.json; companion recipe-redo sources are observational only, not approved by this review")
    assert result["elapsed_seconds"] < result["timebox_seconds"]
    (HERE/"seal.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result),flush=True)


if __name__ == "__main__":
    main()
