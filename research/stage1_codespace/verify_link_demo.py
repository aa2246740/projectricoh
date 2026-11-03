#!/usr/bin/env python3
"""Compile/link examples without writing or executing a firmware image."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "evidence"
GCC = ROOT / "research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc"
TOOLS = ROOT / "research/tooling_m32r_asm/prefix/bin"
OBJDUMP = ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump"
commands = []


def run(args, require_success=True):
    args = [str(a) for a in args]
    p = subprocess.run(args, text=True, capture_output=True)
    commands.append({"argv": args, "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr})
    if require_success and p.returncode:
        raise RuntimeError(p.stderr)
    return p


def main():
    flags = ["-std=c11", "-Os", "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
             "-fno-common", "-fno-pic", "-m32r", "-msdata=none", "-G0", "-fstack-usage",
             "-fno-unwind-tables", "-fno-asynchronous-unwind-tables"]
    run([GCC, *flags, "-mmodel=large", "-c", HERE / "link-demo.c", "-o", OUT / "link-demo.o"])
    run([GCC, *flags, "-mmodel=large", "-I", ROOT / "firmware/recipe_core", "-c",
         ROOT / "firmware/recipe_core/recipe_core.c", "-o", OUT / "recipe-core-large.o"])
    run([TOOLS / "m32r-elf-as", "-m32r", "-EB", HERE / "link-demo.S", "-o", OUT / "abi-adapters.o"])
    run([TOOLS / "m32r-elf-ld", "--no-undefined", "-T", HERE / "link-demo.ld",
         "-Map=" + str(OUT / "link-demo.map"), "-o", OUT / "link-demo.elf",
         OUT / "abi-adapters.o", OUT / "link-demo.o", OUT / "recipe-core-large.o"])
    run([TOOLS / "m32r-elf-objcopy", "-O", "binary", "--only-section=.payload",
         OUT / "link-demo.elf", OUT / "link-demo.bin"])
    for option, file in [("-dr", "link-demo.disasm.txt"), ("-h", "link-demo.headers.txt"),
                         ("-t", "link-demo.symbols.txt"), ("-r", "link-demo.relocations.txt")]:
        (OUT / file).write_text(run([OBJDUMP, option, OUT / "link-demo.elf"]).stdout)
    small = run([TOOLS / "m32r-elf-ld", "--no-undefined", "-T", HERE / "link-demo.ld",
                 "-o", OUT / "old-small-object-at-high-vma.elf", OUT / "abi-adapters.o",
                 OUT / "link-demo.o", ROOT / "artifacts/recipe-core/m32r/recipe_core.o"], False)
    (OUT / "small-model-link-result.txt").write_text(small.stdout + small.stderr)
    elf = (OUT / "link-demo.elf").read_bytes()
    assert elf[:6] == b"\x7fELF\x01\x02" and struct.unpack_from(">H", elf, 18)[0] == 88
    assert struct.unpack_from(">I", elf, 24)[0] == 0x2005276c
    payload = (OUT / "link-demo.bin").read_bytes()
    report = {"executed_target": False, "modified_firmware": False,
              "candidate_vma_approved": False, "entry": "0x2005276c", "payload_size": len(payload),
              "payload_sha256": hashlib.sha256(payload).hexdigest(),
              "input_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in [HERE / "link-demo.c", HERE / "link-demo.S", HERE / "link-demo.ld",
                                            ROOT / "firmware/recipe_core/recipe_core.c",
                                            ROOT / "firmware/recipe_core/recipe_core.h",
                                            ROOT / "firmware/recipe_core/recipe_storage.h"]},
              "tool_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in [GCC, TOOLS / "m32r-elf-as", TOOLS / "m32r-elf-ld",
                                           TOOLS / "m32r-elf-objcopy", OBJDUMP]},
              "small_model_link_returncode": small.returncode, "commands": commands}
    (OUT / "link-demo.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("commands", "input_sha256", "tool_sha256")}))


if __name__ == "__main__":
    main()
