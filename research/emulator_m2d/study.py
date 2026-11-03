"""Read official instruction windows and checkpoint state without changing them."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
sys.path.insert(0, str(ROOT / "tools/gxr_emulator"))
from image import Image
from storage_run import Machine
from unit_peer import UnitImage


def window(start, end):
    image = Image()
    rows = []
    for section in image.sections:
        if section["load_address"] >= end or section["load_address"] + section["initialized_size"] <= start:
            continue
        paths = list((ROOT / "research/tooling_m32r/disasm").glob(
            f"ilaunch3-sec{section['index']:02d}-*.disasm.txt"))
        if len(paths) != 1:
            raise ValueError("one official section listing is required")
        for line in paths[0].read_text().splitlines():
            match = re.match(r"^\s*([0-9a-f]{7,8}):\s*((?:[0-9a-f]{2} )+)\s*(.*)$", line)
            if match and start <= int(match[1], 16) < end:
                address, data = int(match[1], 16), bytes.fromhex(match[2])
                offset = image.offset(address, len(data))
                if image.raw[offset:offset+len(data)] != data:
                    raise ValueError("official instruction bytes differ")
                rows.append(line)
    target = OUT / f"window-{start:08x}-{end:08x}.txt"
    target.write_text("\n".join(rows) + "\n")
    print(json.dumps({"file": str(target.relative_to(ROOT)), "instructions": len(rows)}))


def unit_window(start, end):
    image = UnitImage()
    rows = []
    for p in sorted((ROOT / "research/hw_mining_r2/gpt/disasm").glob("jlaunch3-sec*.asm")):
        for line in p.read_text().splitlines():
            match = re.match(r"^\s*([0-9a-f]{7,8}):\s*((?:[0-9a-f]{2} )+)\s*(.*)$", line)
            if match and start <= int(match[1], 16) < end:
                data = bytes.fromhex(match[2])
                if data != image.bytes_at(int(match[1], 16), len(data)):
                    raise ValueError("unit listing differs from the frozen image")
                rows.append(line)
    if not rows:
        raise ValueError("unit instruction window is empty")
    target = OUT / f"unit-window-{start:08x}-{end:08x}.txt"
    target.write_text("\n".join(rows) + "\n")
    print(json.dumps({"file": str(target.relative_to(ROOT)), "instructions": len(rows)}))


def state(checkpoint, name, budget):
    machine = Machine(resume=checkpoint)
    cpu = machine.cpu
    samples, counts = [], Counter()
    previous = cpu.step_hook
    def sample(c):
        task = machine.task()
        if task == 6 and c.get_reg("psw") & 0x80:
            pc = c.get_reg("pc")
            counts[pc] += 1
            if len(samples) < 512:
                samples.append({"step": c.steps, "pc": pc, "lr": c.get_reg("lr"),
                                "spu": c.get_reg("spu"),
                                "r": [c.get_reg(f"r{i}") for i in range(16)]})
        previous(c)
    cpu.step_hook = sample
    try:
        start = cpu.steps
        stop = cpu.run(budget)
        result = {"checkpoint": str(checkpoint.relative_to(ROOT)), "start_step": start,
                  "steps": cpu.steps, "stop": stop.to_dict(), "samples": samples,
                  "Task6_user_pc_counts": [[pc, n] for pc, n in counts.most_common(128)],
                  "observations": machine.observer.summary(),
                  "registers": {f"r{i}": cpu.get_reg(f"r{i}") for i in range(16)},
                  "stack": [int.from_bytes(cpu.read(cpu.get_reg("spu") + 4*i, 4), "big")
                            for i in range(48)],
                  "hid_table": cpu.read(0x200C5338, 0xB40).hex(),
                  "key_map": cpu.read(0x200C5E78, 0x140).hex(),
                  "pin_map": cpu.read(0x200C212C, 0x200).hex()}
        (OUT / (name + ".json")).write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"steps": cpu.steps, "stop": stop.to_dict(),
                          "Task6_top": [[hex(pc), n] for pc, n in counts.most_common(15)]}))
    finally:
        machine.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["window", "unit-window", "state"])
    parser.add_argument("values", nargs="*")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    if args.command == "window":
        window(*(int(v, 0) for v in args.values))
    elif args.command == "unit-window":
        unit_window(*(int(v, 0) for v in args.values))
    else:
        state(ROOT / args.values[0], args.values[1], int(args.values[2], 0))


if __name__ == "__main__":
    main()
