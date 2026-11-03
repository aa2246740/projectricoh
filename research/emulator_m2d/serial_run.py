"""Run a declared BIOS input-level change through the original scanner."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
sys.path.insert(0, str(ROOT / "tools/gxr_emulator"))
import input_run
from dial import set_dial
from storage_run import sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--card", type=Path)
    parser.add_argument("--pin193", choices=("high", "low"))
    parser.add_argument("--pin225", choices=("high", "low"))
    parser.add_argument("--dial-code", type=int)
    parser.add_argument("--budget", type=int, default=5000000)
    parser.add_argument("--segment", action="append")
    parser.add_argument("--stop-at", action="append", type=lambda v: int(v, 0), default=[])
    parser.add_argument("--watch", action="append", type=lambda v: int(v, 0), default=[])
    parser.add_argument("--stop-task", type=int, default=6)
    parser.add_argument("--stop-after", action="append", default=[])
    args = parser.parse_args()
    original = input_run.machine_from
    changed = {}
    def machine_from(path, name, card=None):
        machine = original(path, name, card)
        if args.pin193:
            serial = machine.devices["serial"]
            mask, value = serial.input_bytes.get(0, (0, 0))
            after = value | 2 if args.pin193 == "high" else value & ~2
            serial.input_bytes[0] = (mask | 2, after)
            changed.update(pin=193, byte=0, mask=2, before=value, after=after)
        if args.pin225:
            serial = machine.devices["serial"]
            mask, value = serial.input_bytes.get(8, (0, 0))
            after = value | 2 if args.pin225 == "high" else value & ~2
            serial.input_bytes[8] = (mask | 2, after)
            changed["pin225"] = {"byte": 8, "mask": 2, "before": value, "after": after}
        if args.dial_code is not None:
            changed["dial"] = set_dial(machine.cpu, machine.devices, args.dial_code)
        changed.update(step=machine.cpu.steps, driver_sha256=sha(Path(__file__)))
        original_run = machine.cpu.run
        def observed_run(count):
            stop = original_run(count)
            def word(address):
                return int.from_bytes(machine.cpu.read(address, 4), "big")
            print(json.dumps({"mode_current": word(0x20412AB8), "mode_pending": word(0x20412ABC),
                              "key55": word(0x20410574), "Task6_state": word(0x200D25A8),
                              "UI_state": word(0x205D9C00), "steps": machine.cpu.steps}), flush=True)
            return stop
        machine.cpu.run = observed_run
        return machine
    input_run.machine_from = machine_from
    input_run.run(args)
    path = OUT / (args.name+".json")
    result = json.loads(path.read_text())
    result["board_input_change"] = changed
    path.write_text(json.dumps(result, indent=2)+"\n")


if __name__ == "__main__":
    main()
