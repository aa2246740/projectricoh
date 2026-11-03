#!/usr/bin/python3
"""Build the standalone host and M32R modules, serially."""
import argparse
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = HERE / "local"
GCC = ROOT / "research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc"
BIN = ROOT / "research/tooling_m32r_asm/prefix/bin"


def run(args, log):
    result = subprocess.run([str(x) for x in args], cwd=ROOT, env={**os.environ,
                            "TMPDIR": str(LOCAL)}, capture_output=True, text=True)
    log.write(" ".join(str(x) for x in args) + "\n")
    log.write(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("command failed; see local/build.log")
    return result.stdout


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    LOCAL.mkdir(exist_ok=True)
    common = ["-std=c11", "-Os", "-ffreestanding", "-fno-builtin",
              "-fno-stack-protector", "-fno-common", "-fno-unwind-tables",
              "-fno-asynchronous-unwind-tables", "-Wall", "-Wextra",
              "-Wno-misleading-indentation", "-Werror=vla"]
    target = ["-m32r", "-mmodel=medium", "-msdata=none", "-G0",
              "-fstack-usage", "-fno-partial-inlining", "-fno-ipa-sra",
              "-fno-inline-small-functions"]
    with (LOCAL / "build.log").open("w") as log:
        run(["clang", *common, "-dynamiclib", "-o", LOCAL / "kv_math.dylib",
             HERE / "kv_math.c", HERE / "kv_i64.c"], log)
        for name in ["kv_math", "kv_i64"]:
            run([GCC, *common, *target, "-c", HERE / (name + ".c"),
                 "-o", LOCAL / (name + ".o")], log)
        run([BIN / "m32r-elf-ld", "-r", "-o", LOCAL / "kv_math_all.o",
             LOCAL / "kv_math.o", LOCAL / "kv_i64.o"], log)
        run([BIN / "m32r-elf-ld", "-T", HERE / "standalone.ld", "-Map",
             LOCAL / "kv_math.map", "-o", LOCAL / "kv_math.elf",
             LOCAL / "kv_math.o", LOCAL / "kv_i64.o"], log)
        for option, output in [("-dr", "target.dis"), ("-h", "sections.txt"),
                               ("-t", "symbols.txt")]:
            (LOCAL / output).write_text(run([ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump", option,
                                             LOCAL / "kv_math.elf"], log))
        symbols = run([ROOT / "research/tooling_m32r/prefix/bin/m32r-elf-objdump", "-t", LOCAL / "kv_math_all.o"], log)
        undefined = "\n".join(x for x in symbols.splitlines() if "*UND*" in x)
        if undefined.strip():
            raise RuntimeError("undefined symbols: " + undefined)
        run([BIN / "m32r-elf-objcopy", "-O", "binary", LOCAL / "kv_math.elf",
             LOCAL / "kv_math.bin"], log)
    (LOCAL / "flags.json").write_text(json.dumps({"common": common,
                                                  "target": target}, indent=2) + "\n")
    print("Built host library, closed M32R object and standalone ELF.")


if __name__ == "__main__":
    main()
