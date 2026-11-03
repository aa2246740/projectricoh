"""M2b/M2c cumulative checks on tools/gxr_emulator_batch in batch mode.

Same routing as research/emulator_speed/cumulative.py: original check rules,
copies of the M2d entry scripts (m2d_*.py) bound to the batch tool copy, all
outputs in research/emulator_batch/local. Every Backend runs fast + batch.
"""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / "tools/gxr_emulator_batch"
OUT = HERE / "local"
SEED = ROOT / "research/emulator_speed/local/card-seed.img"
SERIES = "batch-r1"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TOOLS))
from scope_guard import enable
enable()
os.environ["GXR_EMULATOR_BATCH"] = "1"
import backend
import input_run
import storage_run
import file_calls

FROZEN_LIBRARY = "ba1efa53ce71dbd5632b2a540d0ca3ad02c395498688ce90089a41d85e8c07ff"
STATS = {}


def load(path):
    spec = importlib.util.spec_from_file_location("batch_" + Path(path).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare():
    # The batch copy has no default output or medium directory; give it ours.
    import outputs
    outputs.declare_media(OUT)
    input_run.OUT = storage_run.OUT = file_calls.OUT = OUT
    # As in emulator_speed: Machine runs use fast recording, so batch; direct
    # Backend() users (the four existing check groups) keep their debug
    # default, which always steps one instruction at a time.
    original_init = backend.Backend.__init__
    def init(cpu, **kw):
        original_init(cpu, **kw)
        cpu.set_batch(True)
        STATS.setdefault("backends", []).append(cpu.batch_stats)
    backend.Backend.__init__ = init
    storage_run.Backend = lambda **kw: backend.Backend(**{"mode": "fast", **kw})
    original_run = backend.Backend.run
    def reported(cpu, budget):
        result = original_run(cpu, budget)
        if cpu.steps % 5000000 < budget or result.reason != "max_steps":
            print(json.dumps({"cumulative_steps": cpu.steps, "stop": result.reason}),
                  file=sys.__stdout__, flush=True)
        return result
    backend.Backend.run = reported


def call(name, function):
    stream = io.StringIO()
    started = time.monotonic()
    STATS.clear()
    try:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            return function()
    finally:
        (OUT / (name + ".log")).write_text(stream.getvalue())
        totals = {}
        for stats in STATS.get("backends", []):
            for key, value in stats.items():
                totals[key] = totals.get(key, 0) + value
        record = {"command": name, "seconds": time.monotonic() - started, "batch_stats": totals}
        (OUT / (name + "-timing.json")).write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record), flush=True)


def old_main(module, argv):
    prior = sys.argv
    sys.argv = [str(module.__file__), *argv]
    try:
        try:
            return module.main()
        except SystemExit as error:
            if error.code:
                raise RuntimeError("existing check returned " + str(error.code))
    finally:
        sys.argv = prior


def regression(args):
    module = load(HERE / "m2d_regression.py")
    module.OUT = OUT
    call("existing-checks-" + SERIES, lambda: old_main(module, ["existing-checks-" + SERIES]))


def regression_fast(args):
    """Extra record, not the M2b input: the same four groups with every Backend in fast+batch.
    Cases that read the debug-only MMIO log cannot pass in fast mode by design."""
    original_init = backend.Backend.__init__
    def init(cpu, **kw):
        original_init(cpu, **{**kw, "mode": "fast"})
    backend.Backend.__init__ = init
    module = load(HERE / "m2d_regression.py")
    module.OUT = OUT
    name = "existing-checks-fast-batch-" + SERIES
    call(name, lambda: old_main(module, [name]))


def boot(args):
    card = None
    if args.profile == "card":
        card = OUT / ("cumulative-card-" + SERIES + ".img")
        shutil.copyfile(SEED, card)
    name = ("cold-card-" if card else "cold-") + SERIES
    values = SimpleNamespace(name=name, resume=None, card=card,
                             budget=55000000 if card else 50000000, segment=None,
                             stop_at=[], stop_task=6, stop_after=[], watch=[])
    call(name, lambda: input_run.run(values))
    if not card:
        values.name = "stable-" + SERIES
        values.resume = OUT / ("cold-" + SERIES + "-stop.pkl")
        values.budget = 5000000
        call(values.name, lambda: input_run.run(values))


def files(args):
    module = load(HERE / "m2d_file_regression.py")
    module.OUT = OUT
    from input_run import CheckpointReader
    def prepared_source(path, name, card=None):
        path = Path(path).resolve()
        permitted = (ROOT / "research/emulator_m2c/local", OUT)
        if not any(path.is_relative_to(base) for base in permitted):
            raise ValueError("prepared checkpoint path is outside declared evidence directories")
        metadata = json.loads(path.with_suffix(".json").read_text())
        if storage_run.sha(path) != metadata["sha256"]:
            raise ValueError("prepared checkpoint SHA differs")
        if metadata["library_sha256"] not in (FROZEN_LIBRARY, storage_run.sha(TOOLS / "build/libgxr_m32r.dylib")):
            raise ValueError("prepared library SHA differs")
        with path.open("rb") as stream:
            state = CheckpointReader(stream).load()
        medium = None
        for kind, data in zip(state["device_types"], state["devices"]):
            if kind == "SdHost" and data.get("medium_record"):
                record = data["medium_record"]
                medium = OUT / (name + "-model.img")
                shutil.copyfile(record["path"], medium)
                if storage_run.sha(medium) != record["sha256"]:
                    raise ValueError("prepared medium SHA differs")
                record["path"] = str(medium)
        machine = storage_run.Machine(card=medium)
        if machine.image.sha256 != metadata["image_sha256"]:
            machine.close()
            raise ValueError("prepared MAIN SHA differs")
        machine.cpu.restore(state)
        return machine
    module.machine_from = prepared_source
    argv = [args.case, "--name", args.case + "-" + SERIES]
    if args.case == "readback":
        argv += ["--resume", str(OUT / ("reboot-" + SERIES + "-stop.pkl"))]
    call(args.case + "-" + SERIES, lambda: old_main(module, argv))
    current_medium = OUT / (args.case + "-" + SERIES + "-model.img")
    if current_medium.is_file():
        shutil.copyfile(current_medium, OUT / (args.case + "-" + SERIES + "-medium.img"))


def restart(args):
    shutil.copyfile(OUT / ("files-" + SERIES + "-model.img"), OUT / ("files-" + SERIES + "-medium.img"))
    module = load(HERE / "m2d_restart_run.py")
    module.OUT = OUT
    call("reboot-" + SERIES, lambda: old_main(module, ["--name", "reboot-" + SERIES,
                                                      "--case", "files-" + SERIES]))


def model(args):
    module = load(TOOLS / "storage_checks.py")
    module.OUT = OUT
    from fat_image import inspect
    fixture_sources = []
    def frozen_fixture(path, full=False):
        source = ROOT / "research/emulator_m2c/local" / (
            "full-acceptance-r1.img" if full else "card-acceptance-r1.img")
        path = Path(path).resolve()
        if not path.is_relative_to(OUT):
            raise ValueError("model fixture must stay in the current study")
        shutil.copyfile(source, path)
        fixture_sources.append({"path": str(source.relative_to(ROOT)),
                                "sha256": storage_run.sha(source), "full": full})
        return inspect(path)
    module.create = frozen_fixture
    target = OUT / "storage-checks-r1.json"
    call("storage-checks-r1", lambda: old_main(module, ["--output", str(target)]))
    result = json.loads(target.read_text())
    result["fixture_factory"] = "frozen fixture copies; original assertion functions retained"
    result["fixture_sources"] = fixture_sources
    target.write_text(json.dumps(result, indent=2) + "\n")


def guard(args):
    """Inputs this study must not change: frozen inputs and the three sealed directories."""
    def sealed(directory, base):
        bad = []
        for line in (ROOT / directory / "SHA256SUMS").read_text().splitlines():
            digest, rel = line.split("  ", 1)
            path = (ROOT / directory / rel) if base == "dir" else (ROOT / rel)
            if not path.is_file() or storage_run.sha(path) != digest:
                bad.append(rel)
        return bad
    protected = json.loads((ROOT / "tools/gxr_emulator/local/protected-inputs.json").read_text())["files"]
    changed_inputs = [row["path"] for row in protected if Path(row["path"]).name != "decisions.tsv"
                      and storage_run.sha(ROOT / row["path"]) != row["sha256"]]
    history = {"tools/gxr_emulator": sealed("tools/gxr_emulator", "dir"),
               "research/emulator_speed": sealed("research/emulator_speed", "root")}
    original = (ROOT / "tools/gxr_emulator/CHANGES.md").read_bytes()
    copy = (TOOLS / "CHANGES.md").read_bytes()
    result = {"unchanged_inputs": not changed_inputs, "changed_inputs": changed_inputs,
              "changes_prefix_unchanged": copy[:len(original)] == original,
              "historical_inputs_unchanged": not any(history.values()),
              "historical_differences": history,
              "git_status_protected": subprocess.run(
                  ["git", "status", "--porcelain", "--", "tools/gxr_emulator", "research/emulator_speed",
                   "research/emulator_m2d", "research/unit28_stock", "firmware"],
                  cwd=ROOT, capture_output=True, text=True).stdout.count("\n")}
    (OUT / "final-input-guard.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "historical_differences"}))


def acceptance(args):
    module = load(HERE / "m2d_acceptance.py")
    module.OUT = OUT
    values = SimpleNamespace(cold="cold-" + SERIES, stable="stable-" + SERIES,
                             card="cold-card-" + SERIES, regression="existing-checks-" + SERIES,
                             cumulative="m2b-" + SERIES, file_series=SERIES)
    result = call(args.milestone + "-acceptance", lambda: getattr(module, args.milestone)(values))
    result["passed"] = sum(bool(x) for x in result["checks"].values())
    result["total"] = len(result["checks"])
    result["status"] = "passed" if result["passed"] == result["total"] else "failed"
    result["checker_sha256"] = storage_run.sha(HERE / "m2d_acceptance.py")
    result["current_sources"] = storage_run.sources()
    (OUT / (args.milestone + "-" + SERIES + ".json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"milestone": args.milestone, "passed": result["passed"],
                      "total": result["total"], "failed": [k for k, v in result["checks"].items() if not v]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("regression", "regression-fast", "boot", "files", "restart", "model",
                                            "guard", "acceptance"))
    parser.add_argument("--profile", choices=("card", "no-card"), default="no-card")
    parser.add_argument("--case", choices=("files", "full", "read-error", "write-error", "no-card", "readback"))
    parser.add_argument("--milestone", choices=("m2b", "m2c"), default="m2b")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    prepare()
    {"regression": regression, "regression-fast": regression_fast, "boot": boot, "files": files, "restart": restart, "model": model,
     "guard": guard, "acceptance": acceptance}[args.command](args)


if __name__ == "__main__":
    main()
