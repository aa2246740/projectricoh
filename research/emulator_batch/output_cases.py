"""The batch copy has no default output or medium directory and refuses frozen evidence.

Every case must raise ValueError before writing; nothing is created. Writes
only local/output-cases.json.
"""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from scope_guard import enable
enable()
sys.path.insert(0, str(ROOT / "tools/gxr_emulator_batch"))
import file_calls
import input_run
import m2
import outputs
import sdcard
import speed_snapshot
import storage_checks
import storage_run

FROZEN_IMAGE = ROOT / "research/emulator_speed/local/card-seed.img"


def refused(call):
    try:
        call()
    except ValueError as error:
        return {"refused": True, "message": str(error)[:160]}
    except Exception as error:
        return {"refused": False, "other": type(error).__name__ + ": " + str(error)[:160]}
    return {"refused": False}


def main():
    run_args = SimpleNamespace(name="never-written", budget=1, resume=None, card=None,
                               card_event=False, stop_at=[], task=None)
    cases = {
        "storage_run.run without OUT": lambda: storage_run.run(run_args),
        "input_run.run without OUT": lambda: input_run.run(SimpleNamespace(
            name="never-written", resume=None, card=None)),
        "file_calls.run without OUT": lambda: file_calls.run(SimpleNamespace(name="never-written")),
        "storage_checks without OUT": lambda: storage_checks.checks(),
        "m2.run without --output-dir": lambda: m2.run(SimpleNamespace(output_dir=None)),
        "m2.run into frozen M2b": lambda: m2.run(SimpleNamespace(
            output_dir=str(ROOT / "research/emulator_m2b/local"))),
        "medium undeclared": lambda: sdcard.BlockImage(HERE / "local/g145/card-0-placed.img"),
        "medium in frozen speed study": lambda: sdcard.BlockImage(FROZEN_IMAGE),
        "declare frozen medium directory": lambda: outputs.declare_media(FROZEN_IMAGE.parent),
        "storage_run.OUT set to frozen M2c": lambda: (setattr(storage_run, "OUT",
            ROOT / "research/emulator_m2c/local"), storage_run.run(run_args)),
    }
    result = {name: refused(call) for name, call in cases.items()}
    storage_run.OUT = None
    command = speed_snapshot.regeneration("no-card")
    result["regeneration command names this copy"] = {
        "refused": "tools/gxr_emulator_batch/speed_snapshot.py" in command
                   and "tools/gxr_emulator/speed_snapshot.py" not in command,
        "command": command}
    passed = all(row["refused"] for row in result.values())
    (HERE / "local/output-cases.json").write_text(json.dumps({"cases": result, "passed": passed},
                                                            indent=2) + "\n")
    for name, row in result.items():
        print("ok  " if row["refused"] else "FAIL", name, row.get("message", row.get("other", "")))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
