"""Read native state and saved task stacks from SHA-bound local checkpoints."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "local"
sys.path.insert(0, str(ROOT / "tools/gxr_emulator"))
from input_run import CheckpointReader
from storage_run import sha


def read(path):
    metadata = json.loads(path.with_suffix(".json").read_text())
    if sha(path) != metadata["sha256"]:
        raise ValueError("checkpoint digest differs")
    with path.open("rb") as stream:
        state = CheckpointReader(stream).load()
    def integer(address, size=4):
        for base, data, _ in state["regions"]:
            if base <= address and address+size <= base+len(data):
                return int.from_bytes(data[address-base:address-base+size], "big")
        raise ValueError("native address is outside RAM")
    tasks = []
    for task in (3, 6, 7, 8, 9, 10, 28):
        stack = integer(0x200D2174+4*(task-1))
        stack_mapped = any(base <= stack and stack+512 <= base+len(data)
                           for base, data, _ in state["regions"])
        tasks.append({"id": task, "state": integer(0x200D2594+4*(task-1)),
                      "timeout_link_value": integer(0x200D2224+4*(task-1)),
                      "saved_spu": stack,
                      "saved_stack_mapped": stack_mapped,
                      "saved_words": [integer(stack+4*i) for i in range(128)] if stack_mapped else []})
    words = {hex(address): integer(address) for address in
             (0x200D183C, 0x200D6118, 0x2037FE00, 0x2041289C,
              0x20412AB8, 0x20412AC0, 0x2037FD00, 0x205D9C00,
              0x2037F800, 0x205DEFB8, 0x20410574, 0x2037F2F4)}
    mode = [integer(0x20412AB0+4*i) for i in range(6)]
    startup = [integer(0x205E436C+i, 1) for i in range(32)]
    peer = next(d for d in state["devices"] if "long_unit_notifications" in d)
    records = [{"length": len(packet), "type": packet[2],
                "identifier": int.from_bytes(packet[4:8], "big"),
                "sha256": hashlib.sha256(packet).hexdigest()}
               for packet in peer["long_unit_notifications"]]
    return {"checkpoint": str(path.relative_to(ROOT)), "sha256": metadata["sha256"],
            "steps": state["steps"], "registers": state["registers"],
            "current_task": integer(0x200D1838, 2), "tasks": tasks,
            "native_words": words, "mode_words": mode, "startup_bytes": startup,
            "recorded_unit_data": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("checkpoints", type=Path, nargs="+")
    args = parser.parse_args()
    if args.output.resolve().parent != OUT or args.output.exists():
        raise ValueError("use a fresh M2d local state record")
    rows = [read(p.resolve()) for p in args.checkpoints]
    args.output.write_text(json.dumps({"states": rows}, indent=2) + "\n")
    print(json.dumps([{"checkpoint": r["checkpoint"], "steps": r["steps"],
                       "tasks": [{k: t[k] for k in ("id", "state", "timeout_link_value")}
                                 for t in r["tasks"]]} for r in rows]))


if __name__ == "__main__":
    main()
