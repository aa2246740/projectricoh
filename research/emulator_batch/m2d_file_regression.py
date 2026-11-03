"""Copy of research/emulator_m2d/file_regression.py for tools/gxr_emulator_batch; changes are marked BATCH-COPY."""
"""Repeat the accepted native file cases in existing Task 8 contexts."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
sys.path.insert(0, str(ROOT / "tools/gxr_emulator_batch"))
import file_calls
from input_run import machine_from
from panel import Panel

CASES = {
    "files": ("cold-card-acceptance-r1-stop.pkl", "normal", False, False, False, "buffered", "response", "volume"),
    "full": ("full-prepare-final-r1-stop.pkl", "full", False, True, False, "buffered", "response", "volume"),
    "read-error": ("error-prepare-r1-stop.pkl", "read-error", False, False, True, "direct", "data", "volume"),
    "write-error": ("error-prepare-r1-stop.pkl", "write-error", False, True, True, "buffered", "data", "data"),
    "no-card": ("no-card-acceptance-r1-stop.pkl", "no-card", False, False, False, "buffered", "response", "volume"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=list(CASES)+["readback"])
    parser.add_argument("--name", required=True)
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    if args.case == "readback":
        if args.resume is None:
            raise ValueError("readback requires its new MAIN checkpoint")
        selected = (args.resume.name, "normal", True, False, False, "buffered", "response", "volume")
        resume = args.resume
    else:
        selected = CASES[args.case]
        resume = ROOT / "research/emulator_m2c/local" / selected[0]
    _, scenario, read_written, skip_read, unaligned, read_entry, error_stage, error_area = selected
    def prepared(card=None, resume=None):
        machine = machine_from(Path(resume).resolve(), args.name, card)
        if machine.task() != 8 or not machine.cpu.get_reg("psw") & 0x80:
            machine.close()
            raise ValueError("file regression requires an existing Task 8 user context")
        panel = Panel(machine.cpu, machine.devices)
        panel.chain(machine.cpu)  # BATCH-COPY: same tick, declared for batch mode
        return machine
    file_calls.Machine = prepared
    file_calls.OUT = OUT
    values = SimpleNamespace(
        name=args.name, resume=resume, card=None, scenario=scenario,
        error_stage=error_stage, error_area=error_area, write_size=4099,
        read_entry=read_entry, write_entry="direct", unaligned=unaligned,
        call_budget=40000000, initialize=False, prepare_only=False,
        read_written=read_written, skip_read=skip_read, mount_again=False,
        volume_label=False)
    result = file_calls.run(values)
    print(json.dumps({"case": args.case, "status": result["status"]}), flush=True)
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
