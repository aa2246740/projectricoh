"""Route existing cumulative checks to this study without changing their rules."""
import argparse
import contextlib
from functools import partial
import io
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = ROOT / "tools/gxr_emulator"
OUT = HERE / "local"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TOOLS))
from run_existing import load, neutral
import backend
import input_run
import storage_run
import file_calls


def prepare():
    input_run.OUT = OUT
    storage_run.OUT = OUT
    file_calls.OUT = OUT
    storage_run.Backend = partial(backend.Backend, mode="fast")
    original = backend.Backend.run
    def reported(cpu, budget):
        result = original(cpu, budget)
        print(json.dumps({"cumulative_steps": cpu.steps, "stop": result.reason}),
              file=sys.__stdout__, flush=True)
        return result
    backend.Backend.run = reported


def call(name, function):
    stream = io.StringIO()
    started = time.monotonic()
    try:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            return function()
    finally:
        (OUT / (name + ".log")).write_text(neutral(stream.getvalue()))
        print(json.dumps({"command": name, "seconds": time.monotonic() - started}), flush=True)


def boot(args):
    card = None
    if args.profile == "card":
        card = OUT / "cumulative-card.img"
        shutil.copyfile(OUT / "card-seed.img", card)
    name = "cold-card-speed-r1" if card else "cold-speed-r1"
    values = SimpleNamespace(name=name, resume=None, card=card,
                             budget=55000000 if card else 50000000, segment=None,
                             stop_at=[], stop_task=6, stop_after=[], watch=[])
    call(name, lambda: input_run.run(values))
    if not card:
        values.name = "stable-speed-r1"
        values.resume = OUT / "cold-speed-r1-stop.pkl"
        values.budget = 5000000
        call(values.name, lambda: input_run.run(values))


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


def files(args):
    module = load(ROOT / "research/emulator_m2d/file_regression.py")
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
        if storage_run.sha(TOOLS / "build/libgxr_m32r.dylib") != metadata["library_sha256"]:
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
    argv = [args.case, "--name", args.case + "-speed-r1"]
    if args.case == "readback":
        argv += ["--resume", str(OUT / "reboot-speed-r1-stop.pkl")]
    call(args.case, lambda: old_main(module, argv))
    current_medium = OUT / (args.case + "-speed-r1-model.img")
    if current_medium.is_file():
        shutil.copyfile(current_medium, OUT / (args.case + "-speed-r1-medium.img"))


def restart(args):
    # The existing restart entry uses the established case-medium filename.
    shutil.copyfile(OUT / "files-speed-r1-model.img", OUT / "files-speed-r1-medium.img")
    module = load(ROOT / "research/emulator_m2d/restart_run.py")
    module.OUT = OUT
    call("reboot-speed-r1", lambda: old_main(module, ["--name", "reboot-speed-r1",
                                                    "--case", "files-speed-r1"]))


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
    call("storage-checks-r1", lambda: old_main(module, ["--output", str(OUT / "storage-checks-r1.json")]))
    result_path = OUT / "storage-checks-r1.json"
    result = json.loads(result_path.read_text())
    result["fixture_factory"] = "frozen fixture copies; original assertion functions retained"
    result["fixture_sources"] = fixture_sources
    result_path.write_text(json.dumps(result, indent=2) + "\n")


def acceptance(args):
    module = load(ROOT / "research/emulator_m2d/acceptance.py")
    module.OUT = OUT
    values = SimpleNamespace(cold="cold-speed-r1", stable="stable-speed-r1",
                             card="cold-card-speed-r1", regression="existing-checks",
                             cumulative="m2b-speed-r1", file_series="speed-r1")
    result = call(args.milestone, lambda: getattr(module, args.milestone)(values))
    result["passed"] = sum(bool(x) for x in result["checks"].values())
    result["total"] = len(result["checks"])
    result["status"] = "passed" if result["passed"] == result["total"] else "failed"
    result["checker_sha256"] = storage_run.sha(ROOT / "research/emulator_m2d/acceptance.py")
    result["current_sources"] = storage_run.sources()
    (OUT / (args.milestone + "-speed-r1.json")).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"milestone": args.milestone, "passed": result["passed"],
                      "total": result["total"], "failed": [k for k, v in result["checks"].items() if not v]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("boot", "files", "restart", "model", "acceptance"))
    parser.add_argument("--profile", choices=("card", "no-card"), default="no-card")
    parser.add_argument("--case", choices=("files", "full", "read-error", "write-error", "no-card", "readback"))
    parser.add_argument("--milestone", choices=("m2b", "m2c"), default="m2b")
    args = parser.parse_args()
    prepare()
    {"boot": boot, "files": files, "restart": restart, "model": model,
     "acceptance": acceptance}[args.command](args)


if __name__ == "__main__":
    main()
