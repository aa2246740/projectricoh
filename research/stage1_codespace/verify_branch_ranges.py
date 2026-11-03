#!/usr/bin/env python3
"""Exercise assembler/linker range checks; no firmware bytes are changed."""
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "evidence"
TOOLS = ROOT / "research/tooling_m32r_asm/prefix/bin"
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"


def main():
    base = 0x2028a000
    results = []
    for kind, bits in (("s", 8), ("l", 24)):
        source = OUT / f"branch-{kind}.S"
        source.write_text(f".text\n.align 2\n.global branch_probe\nbranch_probe:\n bl.{kind} destination\n nop\n")
        obj = OUT / f"branch-{kind}.o"
        subprocess.run([str(TOOLS / "m32r-elf-as"), "-m32r", "-EB", str(source), "-o", str(obj)], check=True)
        limit = (1 << (bits - 1)) * 4
        for delta in (-limit - 4, -limit, limit - 4, limit):
            expected = -limit <= delta <= limit - 4
            stem = f"branch-{kind}-{'neg' if delta < 0 else 'pos'}-{abs(delta):x}"
            elf = OUT / (stem + ".elf")
            command = [str(TOOLS / "m32r-elf-ld"), "--entry=branch_probe",
                       f"--section-start=.text=0x{base:x}", f"--defsym=destination=0x{base+delta:x}",
                       str(obj), "-o", str(elf)]
            p = subprocess.run(command, text=True, capture_output=True)
            decoded = ""
            observed_target = None
            if p.returncode == 0:
                decoded = subprocess.run([str(OBJDUMP), "-d", str(elf)], text=True, capture_output=True, check=True).stdout
                (OUT / (stem + ".txt")).write_text(decoded)
                match = re.search(r"\bbl\s+([0-9a-f]+)", decoded)
                assert match is not None
                observed_target = int(match[1], 16)
            # The long relocation can truncate silently. The builder needs both
            # an independent signed-distance check and a target readback.
            if expected:
                assert p.returncode == 0 and observed_target == base + delta
            guard_accepts = expected and p.returncode == 0 and observed_target == base + delta
            assert guard_accepts == expected
            results.append({"kind": kind, "pc": hex(base), "target": hex(base + delta),
                            "delta": delta, "in_architectural_range": expected, "returncode": p.returncode,
                            "decoded_target": hex(observed_target) if observed_target is not None else None,
                            "independent_guard_accepts": guard_accepts,
                            "stderr": p.stderr, "argv": command})
    (OUT / "branch-ranges.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"cases": len(results), "independent_guard_matched_range": True,
                      "out_of_range_linker_successes": sum(not x['in_architectural_range'] and x['returncode'] == 0 for x in results),
                      "target_executed": False}))


if __name__ == "__main__":
    main()
