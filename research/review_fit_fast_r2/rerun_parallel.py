"""Review-local 90-fit serial/two-process check through the original worker.

This coordinator imports no numerical libraries. Run only after the other
review numerical processes exit. Cold restoration uses only this review cache.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARTIFACTS = HERE / "artifacts"
BASE = ARTIFACTS / "parallel-independent"
PYTHON = "/opt/homebrew/bin/python3"


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
    assert not BASE.exists(), "Use a fresh acceptance directory"
    BASE.mkdir(parents=True)
    active = subprocess.check_output(["ps", "-axo", "pid,command"], text=True)
    relevant = [line for line in active.splitlines() if
                ("isolated.py gate" in line or "probe_solver.py" in line or "probe_gate.py" in line)
                and "/bin/zsh -c" not in line and "rg " not in line]
    assert not relevant, "Other review computations are still running: " + repr(relevant)
    started = time.monotonic()
    for mode, assignments in (("serial", ["0,36,44"]), ("parallel", ["0,44", "36"])):
        if mode == "parallel":
            snapshot = ARTIFACTS / "scratch/studio_snapshot"
            snapshot.rename(snapshot.with_name("serial_snapshot_review"))
        for phase in ("base", "full"):
            children = []
            for worker, indices in enumerate(assignments):
                log = BASE / f"{mode}-{phase}-{worker}.log"
                stream = log.open("w")
                env = dict(os.environ, REVIEW_RUN="parallel-independent/"+mode,
                           REVIEW_TIMEOUT="1700", FIT_FAST_JOB_CAP=str(len(assignments)))
                command = ["nice", "-n", "15", PYTHON, "-I", "-B", str(HERE / "isolated.py"),
                           "fit", "--indices", indices, "--phase", phase]
                proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                        start_new_session=True)
                children.append((proc, stream, log))
            try:
                for proc, stream, log in children:
                    code = proc.wait(timeout=1700)
                    stream.close()
                    if code:
                        raise RuntimeError(str(log) + " exited " + str(code))
            except BaseException:
                import signal
                for proc, stream, log in children:
                    if proc.poll() is None:
                        os.killpg(proc.pid, signal.SIGTERM)
                    stream.close()
                raise
            print("Completed", mode, phase, flush=True)
    failures, records = [], []
    serial = BASE / "serial"
    parallel = BASE / "parallel"
    for path in sorted((serial / "fits").glob("*/*.json")):
        old = json.loads(path.read_text())
        if old["config"]["level"] >= 2 and not old["config"].get("full_fields"):
            continue
        relative = path.relative_to(serial)
        peer = parallel / relative
        if normalize(old) != normalize(json.loads(peer.read_text())):
            failures.append(dict(path=str(relative), kind="json"))
        if sha(path.with_suffix(".npz")) != sha(peer.with_suffix(".npz")):
            failures.append(dict(path=str(relative), kind="npz"))
        records.append(dict(path=str(relative), serial_sha256=sha(path), parallel_sha256=sha(peer),
                            prediction_sha256=sha(path.with_suffix(".npz"))))
    assert len(records) == 90
    # Check the original worker output values for each target. The reviewer
    # orchestrator does not claim to retest run.main's own stdout scheduling.
    for phase in ("base", "full"):
        def lines(mode):
            result = []
            for log in BASE.glob(f"{mode}-{phase}-*.log"):
                for line in log.read_text().splitlines():
                    if re.match(r"^(0|36|44) ", line):
                        result.append(re.sub(r"seconds [0-9.]+", "seconds <elapsed>", line))
            return sorted(result)
        if lines("serial") != lines("parallel"):
            failures.append(dict(phase=phase, kind="worker_output_values"))
    summary = dict(passed=not failures, fits=90, indices=[0, 36, 44], numerical_processes=[1, 2],
                   cold_review_dependency_cache=True, actual_nice=15,
                   original_worker_used=True, main_cli_scheduler_retested=False,
                   failures=failures, elapsed_seconds=time.monotonic()-started, records=records)
    (BASE / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print(json.dumps({key: val for key, val in summary.items() if key != "records"}), flush=True)
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
